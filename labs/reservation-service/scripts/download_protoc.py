#!/usr/bin/env python3
"""Official fixed asset download; caller enforces a process-group wall deadline."""
import argparse
import hashlib
from pathlib import Path
import urllib.request

URL='https://github.com/protocolbuffers/protobuf/releases/download/v36.2/protoc-36.2-linux-x86_64.zip'
SHA='121f6c7afe1d4d0e3ea6aab9432038599250134cbf4474cb1167d2c7decd4278'

def main():
 p=argparse.ArgumentParser();p.add_argument('--destination',required=True);a=p.parse_args()
 path=Path(a.destination)
 if path.exists() or path.is_symlink():raise ValueError('download destination exists')
 size=0;h=hashlib.sha256()
 with urllib.request.urlopen(URL,timeout=10) as response,path.open('xb') as f:
  while True:
   block=response.read(65536)
   if not block:break
   size+=len(block)
   if size>8*1024*1024:raise ValueError('download size bound')
   f.write(block);h.update(block)
 if h.hexdigest()!=SHA:raise ValueError('download checksum mismatch')
 print('protoc36.2 bytes='+str(size)+' sha256='+SHA)
if __name__=='__main__':main()
