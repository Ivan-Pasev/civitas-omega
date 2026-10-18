#!/usr/bin/env python3
"""Offline, fail-closed R3 ZIP staging. No Git/network operations."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import sys
import zipfile

CANDIDATES = {
    "public": ("CIVITAS_OMEGA_R3_CANDIDATE.zip", "8c04a4c364faa600aa28f254e89ab7d6186f7e91c7b83af1bc3bfaf1aa12c6dd", "civitas-omega", 43),
    "private": ("CIVITAS_OMEGA_LAB_R3_CANDIDATE.zip", "d2b2fd09ad1da0de75e82022f97e0a46d1c37a7301855abcb259f8acdbd7826c", "civitas-omega-lab", 53),
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def read_checked(archive: Path, scope: str) -> dict[str, bytes]:
    name, digest, root, count = CANDIDATES[scope]
    if archive.name != name or sha(archive.read_bytes()) != digest:
        raise ValueError("archive name or SHA256 mismatch")
    output: dict[str, bytes] = {}
    with zipfile.ZipFile(archive) as z:
        if len(z.infolist()) != count:
            raise ValueError("unexpected archive member count")
        for entry in z.infolist():
            p = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if (entry.flag_bits & 1) or stat.S_ISLNK(mode):
                raise ValueError("encrypted or symlink member")
            if entry.is_dir() or len(p.parts) < 2 or p.parts[0] != root or any(x in (".", "..") for x in p.parts):
                raise ValueError("invalid path or archive layout")
            name = p.relative_to(root).as_posix()
            if name in output:
                raise ValueError("duplicate member")
            output[name] = z.read(entry)
    manifest = json.loads(output["SOURCE_SHA256.json"])
    expected = manifest["files"]
    if set(expected) != set(output) - {"SOURCE_SHA256.json"}:
        raise ValueError("manifest path mismatch")
    if any(sha(output[path]) != digest for path, digest in expected.items()):
        raise ValueError("member hash mismatch")
    return output

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", required=True, choices=CANDIDATES)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--checkout", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="stage bytes into checkout (never commit or push)")
    args = parser.parse_args(argv)
    files = read_checked(args.archive, args.scope)
    checkout = args.checkout.resolve()
    expected_repo = CANDIDATES[args.scope][2]
    if not checkout.is_dir() or not (checkout / ".git").exists() or checkout.name != expected_repo:
        raise ValueError("checkout must be an existing git clone named " + expected_repo)
    for path in files:
        dest = checkout / path
        if dest.is_symlink() or any(parent.is_symlink() for parent in dest.parents if parent != checkout and checkout in parent.parents):
            raise ValueError("refusing existing symlink in target path")
        if not dest.resolve().is_relative_to(checkout):
            raise ValueError("destination escape")
    if args.apply:
        for path, payload in files.items():
            dest = checkout / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
    print(json.dumps({"scope": args.scope, "files_checked": len(files), "staged": args.apply, "archive_sha256": sha(args.archive.read_bytes()), "source_parity": "STAGED_NOT_REMOTELY_VERIFIED"}, sort_keys=True))
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as e:
        print(f"FAIL_CLOSED: {e}", file=sys.stderr)
        sys.exit(2)
