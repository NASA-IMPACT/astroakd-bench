#!/usr/bin/env python3
"""Verify the historical 0.6.7.11.2 dataset TAR.GZ against release SHA-256 manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive',type=Path)
    parser.add_argument('--manifest',type=Path,default=Path('archives/historical_datasets_manifest_0_6_7_11_3.json'))
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf-8'))
    originals=manifest['files']
    with tarfile.open(args.archive,'r:gz') as tar:
        members={m.name:m for m in tar.getmembers() if m.isfile()}
        missing=[v['path'] for v in originals if v['path'] not in members]
        if missing:
            parser.error('Missing archived files: '+', '.join(missing[:5]))
        for item in originals:
            data=tar.extractfile(members[item['path']]).read()
            if len(data)!=item['bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:
                parser.error('Fingerprint mismatch: '+item['path'])
        internal=tar.extractfile('ARCHIVE_MANIFEST.json').read()
        if internal != args.manifest.read_bytes():
            parser.error('Internal manifest differs from source release')
    print(f"VERIFIED {len(originals)} historical datasets from {args.archive}")

if __name__=='__main__':main()
