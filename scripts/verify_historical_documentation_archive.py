"""Verify the external historical Markdown archive against SHA-256 manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def verify(archive: Path, manifest: Path) -> dict:
    spec=json.loads(manifest.read_text())
    expected=spec['files']
    with tarfile.open(archive,'r:gz') as tf:
        members=[m for m in tf.getmembers() if m.isfile()]
        actual={m.name:hashlib.sha256(tf.extractfile(m).read()).hexdigest() for m in members}
    if len(actual)!=len(members) or actual != expected:
        raise ValueError('Historical documentation archive does not match SHA-256 manifest')
    return {'status':'PASS','verified_files':len(actual),'archive':str(archive)}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('archive',type=Path)
    parser.add_argument('--manifest',type=Path,default=Path(__file__).resolve().parents[1]
        / 'archives/historical_documentation_manifest_0_6_7_11_4.json')
    args=parser.parse_args()
    print(json.dumps(verify(args.archive,args.manifest),indent=2))
