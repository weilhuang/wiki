#!/usr/bin/env python3
"""Verify recorded execution against exact current sources, outcomes and snapshots."""
from pathlib import Path
import argparse,hashlib,json
from result_validation import validate_result
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--run',default='proof/run-3');args=parser.parse_args()
run=ROOT/args.run;record=json.loads((run/'result.json').read_text());assert record['status']=='pass'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for item in record['sourceFiles']:
 p=ROOT/item['path']
 if args.run=='proof/run-1' and item['path']=='run.py':p=ROOT/'history/run-1/run.py'
 if args.run in ('proof/run-1','proof/run-2') and item['path']=='src/lab/AopLab.java':p=ROOT/'history/pre-cache-fix/AopLab.java'
 assert sha(p)==item['sha256'],('stale source',item['path'])
expected_names=['java-version','javac-version','compile','aop','boot','negative-bypass','negative-cache','negative-backoff']
assert [c['name'] for c in record['commands']]==expected_names
for command in record['commands']:
 text=(run/command['log']).read_text()
 validate_result(command['exitCode'],text,command['expectedExitCode'],command.get('expectedAssertion'),command.get('expectedMarker'),command['timedOut'],command['cleanupError'])
assert '21.0.12.1' in (run/'java-version.txt').read_text()
assert json.loads((run/'termination.json').read_text())['matchingLabJavaProcesses']==0
for item in json.loads((ROOT/'source-lock.json').read_text()):assert sha(ROOT/item['path'])==item['sha256']
assert not (run/'classes').exists()
if args.run=='proof/run-3':
 assert 'OBSERVE cache result=cached targetEntries=0 events=[cache.hit]' in (run/'aop.txt').read_text()
 assert 'OBSERVE cache result=cached targetEntries=1 events=[cache.hit, target.inner]' in (run/'negative-cache.txt').read_text()
print(json.dumps({'status':'pass','run':args.run,'scope':'exact source hashes, recorded exits and complete logs, upstream snapshot hashes, recorded no-lab-process observation'},indent=2))
