#!/usr/bin/env python3
"""Read-only CIVITAS source completeness gate: never fetch, stage, publish or grant access.
Exit 0 for a correctly classified HOLD/PASS; exit 2 for invalid registry/IO errors.
A GitHub job may report successful execution of the gate while source readiness=HOLD.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
SCHEMA = 'civitas-r3-source-readiness/v1'
VALID_SCOPES = {
    'public': ('Ivan-Pasev/civitas-omega', '8c04a4c364faa600aa28f254e89ab7d6186f7e91c7b83af1bc3bfaf1aa12c6dd', 43, 77),
    'private': ('Ivan-Pasev/civitas-omega-lab', 'd2b2fd09ad1da0de75e82022f97e0a46d1c37a7301855abcb259f8acdbd7826c', 53, 91),
}
class GateInputError(ValueError):
    pass
def validated_registry(registry: dict) -> tuple[str,dict[str,str],int]:
    if not isinstance(registry, dict) or registry.get('schema') != SCHEMA:
        raise GateInputError('unknown registry schema')
    scope = registry.get('scope')
    if scope not in VALID_SCOPES:
        raise GateInputError('unknown registry scope')
    repo, digest, count, tests = VALID_SCOPES[scope]
    if (registry.get('repository') != repo or registry.get('candidate_archive_sha256') != digest
            or registry.get('expected_file_count') != count or registry.get('expected_tests') != tests):
        raise GateInputError('source identity/scope/count mismatch')
    files = registry.get('files')
    if not isinstance(files, dict) or len(files) != count:
        raise GateInputError('wrong source inventory')
    for name, hexsha in files.items():
        if (not isinstance(name, str) or not name or name.startswith('/')
                or '\\' in name or '\x00' in name or not isinstance(hexsha, str)
                or not re.fullmatch(r'[0-9a-f]{64}', hexsha)):
            raise GateInputError('invalid path or content digest')
        parts = name.split('/')
        if any(x in ('', '.', '..') for x in parts) or parts[0] == '.git':
            raise GateInputError('unsafe path')
        if PurePosixPath(name).as_posix() != name:
            raise GateInputError('noncanonical path')
    if 'SOURCE_SHA256.json' not in files:
        raise GateInputError('self-contained source digest manifest required')
    return scope, files, tests
def evaluate(root: Path, registry: dict) -> dict:
    scope, files, expected_tests = validated_registry(registry)
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise GateInputError('root must be a directory')
    missing, altered, unsafe, matched = [], [], [], 0
    for path, digest in sorted(files.items()):
        dest = root / path
        if dest.is_symlink() or any(p.is_symlink() for p in dest.parents if p != root and root in p.parents):
            unsafe.append(path)
            continue
        if not dest.is_file():
            missing.append(path)
            continue
        if not dest.resolve().is_relative_to(root):
            unsafe.append(path)
            continue
        try:
            h = hashlib.sha256(dest.read_bytes()).hexdigest()
        except OSError:
            unsafe.append(path)
            continue
        if h != digest:
            altered.append(path)
        else:
            matched += 1
    state = 'READY_FOR_FULL_OFFLINE_SUITE' if not missing and not altered and not unsafe else 'HOLD_INCOMPLETE_OR_DIFFERENT_SOURCE'
    return {
        'schema': 'civitas-r3-readiness-receipt/v1',
        'scope': scope,
        'repository': VALID_SCOPES[scope][0],
        'candidate_archive_sha256': VALID_SCOPES[scope][1],
        'expected_files': len(files),
        'matched_files': matched,
        'missing_paths': missing,
        'altered_paths': altered,
        'unsafe_paths': unsafe,
        'source_readiness': state,
        'full_suite_expected_tests': expected_tests,
        'full_suite_executed': False,
        'full_suite_result': 'NOT_EXECUTED',
        'remote_head_authenticated': False,
        'provider_rights': 'OPEN',
        'production_authority': 'HOLD',
        'codexstation_authority_delta': 'NONE',
    }
def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--registry',type=Path,required=True)
    p.add_argument('--output',type=Path,default=None)
    p.add_argument('--github-output',type=Path,default=None)
    p.add_argument('--require-ready',action='store_true')
    args=p.parse_args(argv)
    try:
        data=json.loads(args.registry.read_text(encoding='utf-8'))
        result=evaluate(args.root, data)
        serialized=json.dumps(result,sort_keys=True,indent=2)+'\n'
        print(serialized,end='')
        if args.output: args.output.write_text(serialized,encoding='utf-8')
        if args.github_output:
            ready = result['source_readiness'] == 'READY_FOR_FULL_OFFLINE_SUITE'
            with args.github_output.open('a',encoding='utf-8') as f:
                f.write('source_ready='+str(ready).lower()+'\n')
        return 3 if args.require_ready and result['source_readiness'] != 'READY_FOR_FULL_OFFLINE_SUITE' else 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        print('FAIL_CLOSED: '+str(e),file=sys.stderr)
        return 2
if __name__ == '__main__':
    sys.exit(main())
