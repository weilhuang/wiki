#!/usr/bin/env python3
"""Optional dependency preparation from locked Maven Central URLs; no Java execution."""
from pathlib import Path
import argparse,hashlib,json,urllib.request
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('deps'));args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
for item in json.loads(Path(__file__).with_name('dependencies.lock.json').read_text()):
    p=args.output/item['filename']
    data=p.read_bytes() if p.exists() else urllib.request.urlopen(item['url'],timeout=20).read()
    if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('hash mismatch: '+item['filename'])
    if not p.exists():p.write_bytes(data)
    print(item['filename']+' verified')
