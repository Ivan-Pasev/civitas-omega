#!/usr/bin/env python3
"""Offline read-only Git commit-to-frozen-R3-source parity validator.
This does NOT validate GitHub Actions, provider policy, external sources, or CodexStation.
It never fetches a remote or writes into the checkout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import zipfile
EXPECTED = {
    'public': {
        'repo': 'Ivan-Pasev/civitas-omega',
        'root': 'civitas-omega',
        'archive': 'CIVITAS_OMEGA_R3_CANDIDATE.zip',
        'sha256': '8c04a4c364faa600aa28f254e89ab7d6186f7e91c7b83af1bc3bfaf1aa12c6dd',
        'files': 43,
        'tests': 77,
    },
    'private': {
        'repo': 'Ivan-Pasev/civitas-omega-lab',
        'root': 'civitas-omega-lab',
        'archive': 'CIVITAS_OMEGA_LAB_R3_CANDIDATE.zip',
        'sha256': 'd2b2fd09ad1da0de75e82022f97e0a46d1c37a7301855abcb259f8acdbd7826c',
        'files': 53,
        'tests': 91,
    }
}
class VerificationError(ValueError):
    pass
def sha256(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()
def checked_archive(archive:pathlib.Path,scope:str)->dict[str,bytes]:
    cfg=EXPECTED[scope]
    if archive.name!=cfg['archive'] or sha256(archive.read_bytes())!=cfg['sha256']:
        raise VerificationError('frozen archive identity or digest mismatch')
    out={}
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist())!=cfg['files']:
            raise VerificationError('frozen inventory count mismatch')
        for info in z.infolist():
            parts=info.filename.split('/')
            mode=info.external_attr>>16
            if (info.is_dir() or len(parts)<2 or parts[0]!=cfg['root']
                or any(part in ('','.','..') for part in parts)
                or chr(92) in info.filename or chr(0) in info.filename
                or info.flag_bits&1 or (mode & 0o170000)==0o120000):
                raise VerificationError('unsafe archive path/type')
            path='/'.join(parts[1:])
            if path in out or path=='.git' or path.startswith('.git/'):
                raise VerificationError('duplicate or git-control path')
            out[path]=z.read(info)
    if 'SOURCE_SHA256.json' not in out:
        raise VerificationError('manifest missing')
    m=json.loads(out['SOURCE_SHA256.json'])
    if not isinstance(m,dict) or not isinstance(m.get('files'),dict):
        raise VerificationError('manifest malformed')
    if set(m['files'])!=set(out)-{'SOURCE_SHA256.json'}:
        raise VerificationError('manifest/ZIP mismatch')
    if any(sha256(out[p])!=h for p,h in m['files'].items()):
        raise VerificationError('archive file digest mismatch')
    return out
def git(checkout:pathlib.Path,*args:str)->bytes:
    try:
        p=subprocess.run(['git','-C',str(checkout),*args],capture_output=True,check=False)
    except OSError as e:
        raise VerificationError('git unavailable') from e
    if p.returncode!=0:
        raise VerificationError(f'git {args[0]} failed; required object or index missing')
    return p.stdout.strip() if args[0]!='show' else p.stdout
def verify(checkout:pathlib.Path, archive:pathlib.Path, scope:str, expected_head:str)->dict:
    if scope not in EXPECTED:
        raise VerificationError('unknown scope')
    if not re.fullmatch(r'[0-9a-f]{40}',expected_head):
        raise VerificationError('exact 40-hex head required')
    cfg=EXPECTED[scope]
    checkout=checkout.resolve()
    if checkout.name!=cfg['root'] or not checkout.is_dir() or not (checkout/'.git').exists():
        raise VerificationError('scope checkout identity mismatch')
    origin=git(checkout,'remote','get-url','origin').decode()
    allowed={f'https://github.com/{cfg["repo"]}',f'https://github.com/{cfg["repo"]}.git',f'git@github.com:{cfg["repo"]}.git',f'ssh://git@github.com/{cfg["repo"]}.git'}
    if origin not in allowed:
        raise VerificationError('origin identity mismatch')
    if git(checkout,'rev-parse','HEAD').decode()!=expected_head:
        raise VerificationError('checked-out commit != expected head')
    if git(checkout,'rev-parse','--abbrev-ref','HEAD').decode()!='main':
        raise VerificationError('must inspect main branch')
    if git(checkout,'status','--porcelain'):
        raise VerificationError('worktree/index dirty or untracked (cannot certify HEAD)')
    files=checked_archive(archive,scope)
    errors=[]
    for path,payload in files.items():
        # git show reads committed objects, not mutable filesystem bytes.
        # --end-of-options supported on modern Git, and paths are frozen by digest.
        try:
            found=git(checkout,'show',f'{expected_head}:{path}')
        except VerificationError:
            errors.append({'path':path,'reason':'MISSING_FROM_COMMIT'})
            continue
        if sha256(found)!=sha256(payload):
            errors.append({'path':path,'reason':'COMMITTED_BYTES_DIFFER'})
    return {
        'schema':'civitas-gh04-offline-commit-parity/v1',
        'repository':cfg['repo'], 'scope':scope,
        'commit_sha':expected_head,'candidate_archive_sha256':cfg['sha256'],
        'expected_files':len(files),'matched_files':len(files)-len(errors),
        'mismatches':errors,'source_parity':'PASS_LOCAL_COMMIT_ONLY' if not errors else 'FAIL',
        'remote_head_authenticated':False,'github_actions_full_suite':'UNOBSERVED',
        'provider_rights':'OPEN','codexstation_authority_delta':'NONE'
    }
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scope',choices=EXPECTED,required=True)
    p.add_argument('--archive',type=pathlib.Path,required=True)
    p.add_argument('--checkout',type=pathlib.Path,required=True)
    p.add_argument('--expected-head',required=True)
    args=p.parse_args(argv)
    try:
        result=verify(args.checkout,args.archive,args.scope,args.expected_head)
    except (OSError,VerificationError,KeyError,zipfile.BadZipFile,json.JSONDecodeError) as e:
        print('FAIL_CLOSED: '+str(e),file=sys.stderr)
        return 2
    print(json.dumps(result,sort_keys=True,indent=2))
    return 0 if result['source_parity']=='PASS_LOCAL_COMMIT_ONLY' else 1
if __name__=='__main__':
    sys.exit(main())
