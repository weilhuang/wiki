#!/usr/bin/env python3
"""Check frozen diagnostic observations and exercise the actual negative-output checker.
SPDX-License-Identifier: MIT
No JVM is launched by this script.
"""
import ast, hashlib, json, pathlib, re, tempfile, types
ROOT = pathlib.Path(__file__).resolve().parent
proof = ROOT/'proof/run-r4'
before = (proof/'threads-before.txt').read_text()
after = (proof/'threads-after.txt').read_text()
gc = (proof/'gc.log').read_text()
assert 'state=BLOCKED' in before and 'owner=lab-monitor-holder' in before
holder = before.split('SNAPSHOT name=lab-monitor-holder ',1)[1].split('SNAPSHOT name=',1)[0]
blocked = before.split('SNAPSHOT name=lab-monitor-blocked ',1)[1].split('\n',1)[0]
assert 'state=WAITING' in holder and 'locked monitor ' in holder
lock = re.search(r'lock=(\S+)', blocked).group(1)
assert 'locked monitor '+lock+' ' in holder
assert 'Pause Young (Allocation Failure)' in gc
attempt = json.loads((ROOT/'proof/jcmd-attempt.json').read_text())
assert attempt['status'] == 'fail' and attempt['reason'] == 'timeout-after-8-seconds'
rejected = {
    'waiting-holder-holds-no-monitor': 'Rejected: actual WAITING holder owns monitor matched by blocked thread',
    'small-retained-set-means-no-gc': 'Rejected: actual young GC pause records exist',
    'external-jcmd-succeeded': 'Rejected: attach attempt timed out; successful snapshots are ThreadMXBean observations'
}
# Extract the real function, replace only its subprocess dependency with a deterministic stub.
# This tests the actual exact-type/first-exception check without spawning another JVM.
module = ast.parse((ROOT/'run.py').read_text())
functions = [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name in ('run','diagnostic_ok')]
code = compile(ast.Module(body=functions,type_ignores=[]), 'run.py::output-checks', 'exec')
token = 'VOLATILE_COMPOUND_CLAIM expected=2 actual=1'
cases = [
    ('matching', 1, 'Exception in thread "main" java.lang.AssertionError: '+token+'\n', True),
    ('same-text-wrong-type', 1, 'Exception in thread "main" java.lang.RuntimeException: '+token+'\n', False),
    ('wrong-thread', 1, 'Exception in thread "worker" java.lang.AssertionError: '+token+'\n', False),
    ('compile-failure', 1, 'error: cannot find symbol\n'+token, False),
    ('startup-failure', 1, 'Error: Could not find or load main class JmmLab\n'+token, False),
    ('unexpected-success', 0, 'Exception in thread "main" java.lang.AssertionError: '+token+'\n', False),
    ('wrong-first-exception', 1, 'Exception in thread "main" java.lang.RuntimeException: first\nException in thread "main" java.lang.AssertionError: '+token+'\n', False)
]
checks = []
with tempfile.TemporaryDirectory(prefix='java-evidence-check-') as output:
    for name, exitcode, stdout, accepted in cases:
        ns = {'ROOT':ROOT,'out':pathlib.Path(output),'records':[], 'subprocess':types.SimpleNamespace(PIPE=-1,STDOUT=-2,run=lambda *a, **k: types.SimpleNamespace(returncode=exitcode,stdout=stdout))}
        exec(code,ns)
        try: ns['run'](['stub'],name+'.txt',expected=1,token=token); actual=True
        except AssertionError: actual=False
        assert actual == accepted, name+' produced wrong acceptance'
        checks.append({'case':name,'accepted':actual})
# Exercise the same positive and interactive validators, including previously false-green output.
with tempfile.TemporaryDirectory(prefix='java-positive-check-') as output:
    positives = [
        ('complete-positive', 'JMM_OK\n', True),
        ('ordinary-child-exception', 'Exception in thread "atomic-a" java.lang.IllegalStateException: REVIEWER_CHILD_ATOMIC_FAILURE\nJMM_OK\n', False),
        ('missing-completion', 'atomic increment result=2\n', False),
        ('duplicate-completion', 'JMM_OK\nJMM_OK\n', False)
    ]
    for name,stdout,expected in positives:
        ns={'ROOT':ROOT,'out':pathlib.Path(output),'records':[], 'subprocess':types.SimpleNamespace(PIPE=-1,STDOUT=-2,run=lambda *a,**k:types.SimpleNamespace(returncode=0,stdout=stdout))}
        exec(code,ns)
        try: ns['run'](['stub'],name+'.txt',required=('JMM_OK',));actual=True
        except AssertionError:actual=False
        assert actual==expected,name
        checks.append({'case':name,'accepted':actual})
    complete='\n'.join(['READY cpu=RUNNABLE blocked=BLOCKED latch=WAITING','ALLOCATED payloadBytes=268435456 retainedSlots=16','SAMPLED','CLEANUP all four workers joined; watchdog joined','DIAGNOSTIC_OK'])+'\n'
    for name,exitcode,text,expected in [
        ('complete-diagnostic',0,complete,True),
        ('diagnostic-child-exception',0,complete+'Exception in thread "lab-cpu-busy" java.lang.IllegalStateException: REVIEWER_CHILD_DIAGNOSTIC_FAILURE\n',False),
        ('diagnostic-missing-ok',0,complete.replace('DIAGNOSTIC_OK\n',''),False),
        ('diagnostic-nonzero',1,complete,False)]:
        try:ns['diagnostic_ok'](exitcode,text);actual=True
        except AssertionError:actual=False
        assert actual==expected,name
        checks.append({'case':name,'accepted':actual})
report = {'status':'pass','scope':'static artifact judgment and actual runner-output parser regression; no JVM execution','rejectedClaims':rejected,'outputChecker':checks,'sourceFiles':[{'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [ROOT/'run.py',ROOT/'check_evidence.py',proof/'threads-before.txt',proof/'threads-after.txt',proof/'gc.log',ROOT/'proof/jcmd-attempt.json']]}
(ROOT/'proof/evidence-check.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: actual artifacts reject unsupported claims; output checker rejects wrong attribution')
