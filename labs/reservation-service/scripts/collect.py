#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import evidence

def main():
 p=argparse.ArgumentParser();p.add_argument('--private',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 result=evidence.collect(Path(a.private),Path(a.output),Path(os.environ['RUNNER_TEMP']))
 github_output=evidence.safe_path(os.environ['GITHUB_OUTPUT'])
 with github_output.open('a') as f:f.write('upload_ready=true\n')
 print('validated bounded evidence:',result['files'],'files,',result['bytes'],'bytes')
if __name__=='__main__':main()
