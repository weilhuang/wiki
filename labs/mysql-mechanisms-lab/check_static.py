#!/usr/bin/env python3
"""Static checks only. Passing this never constitutes MySQL execution."""
import ast
import hashlib
import json
from pathlib import Path
from safety import safe_path, verify_sources
ROOT=safe_path(Path(__file__).absolute().parent)

def require(value,message):
    if not value: raise RuntimeError(message)

def main():
    verify_sources(ROOT)
    files=[p for p in ROOT.rglob('*') if p.is_file() and 'results' not in p.relative_to(ROOT).parts]
    require(not any(p.is_symlink() for p in ROOT.rglob('*')), 'symlink rejected')
    for p in files:
        require(p.stat().st_size<=256*1024,'oversized source')
        if p.suffix=='.py': ast.parse(p.read_text(),filename=p.name)
    manifest=json.loads((ROOT/'source-manifest.json').read_text())
    actual={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.name!='source-manifest.json'}
    require(actual=={x['path']:x['sha256'] for x in manifest['files']},'exact source tree mismatch')
    compose=(ROOT/'compose.yaml').read_text()
    for text in ('image: mysql:8.4.7','internal: true','mem_limit: 1g','cpus: 1.0','pids_limit: 256'):
        require(text in compose,'missing runtime bound: '+text)
    for forbidden in ('ports:', 'network_mode:', 'privileged:', '/var/run/docker.sock', 'container_name:', 'build:'):
        require(forbidden not in compose,'forbidden compose option: '+forbidden)
    cases=(ROOT/'cases.py').read_text()
    for expected in ('EXPLAIN FORMAT=JSON','EXPLAIN ANALYZE','performance_schema.data_lock_waits','SELECT ROW_COUNT()',"'rr.repeat'","'own.mixed-view'"):
        require(expected in cases,'missing evidence path: '+expected)
    print(json.dumps({'status':'STATIC_CHECKED','source_files':len(actual),'mysql_execution':'NOT_RUN'}))
if __name__=='__main__': main()
