#!/usr/bin/env python3
"""Finite Python-only adversarial fixtures; does not execute JVMs or mutate source."""
import json
from result_validation import validate_result
label='cache hit must skip business'
good='Exception in thread "main" java.lang.AssertionError: '+label+'\n\tat lab.AopLab.require(AopLab.java:42)\n'
validate_result(1,good,1,label)
validate_result(0,'PASS AOP complete\n',marker='PASS AOP complete')
cases={
 'unexpected-success':dict(exit_code=0,text=good,expected_exit=1,assertion=label),
 'wrong-exception-same-message':dict(exit_code=1,text=good.replace('AssertionError','IllegalStateException'),expected_exit=1,assertion=label),
 'nested-cause-only':dict(exit_code=1,text='Exception in thread "main" java.lang.RuntimeException: startup failed\nCaused by: java.lang.AssertionError: '+label,expected_exit=1,assertion=label),
 'compiler-failure':dict(exit_code=1,text='error: cannot find symbol '+label,expected_exit=1,assertion=label),
 'vm-start-failure':dict(exit_code=1,text='Error: Could not find or load main class lab.AopLab',expected_exit=1,assertion=label),
 'ordinary-thread-failure':dict(exit_code=0,text='Exception in thread "worker" java.lang.IllegalStateException: boom\nPASS AOP complete\n',marker='PASS AOP complete'),
 'child-and-expected-main':dict(exit_code=1,text='Exception in thread "worker" java.lang.IllegalStateException: boom\n'+good,expected_exit=1,assertion=label),
 'missing-business-completion':dict(exit_code=0,text='started\n',marker='PASS AOP complete'),
 'timeout':dict(exit_code=1,text=good,expected_exit=1,assertion=label,timed_out=True),
 'cleanup-failure':dict(exit_code=1,text=good,expected_exit=1,assertion=label,cleanup_error='remove failed')}
for name,args in cases.items():
 try: validate_result(**args)
 except AssertionError: pass
 else: raise AssertionError('accepted invalid fixture: '+name)
print(json.dumps({'status':'pass','accepted':['valid-counterexample','valid-completion'],'rejected':list(cases),'scope':'Python classifier fixtures; not live JVM/thread/cleanup fault injection'},indent=2))
