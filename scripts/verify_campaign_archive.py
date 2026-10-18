"""Verify a committed campaign snapshot offline without AWS/model calls."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    args=parser.parse_args()
    manifest=json.loads((args.archive/'checksums.json').read_text())
    for record in manifest['files']:
        relative=Path(record['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe archive path')
        raw=(args.archive/relative).read_bytes()
        if len(raw)!=record['bytes'] or hashlib.sha256(raw).hexdigest()!=record['sha256']:
            raise ValueError(f'Checksum mismatch: {relative}')
    print(f"Verified {len(manifest['files'])} archived artifacts")


if __name__=='__main__':main()
