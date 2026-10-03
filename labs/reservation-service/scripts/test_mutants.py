#!/usr/bin/env python3
import copy
import json
from pathlib import Path
import unittest
import mutants

def encoded(events):return b''.join(json.dumps(e).encode()+b'\n' for e in events)
def control(variant):
 unit=variant['case']=='G07';package='example.com/reservation-service/internal/grpcapi' if unit else 'example.com/reservation-service/tests'
 events=[{'Action':'start','Package':package}]
 def event(action,name=None,output=None,frame=False,error=False):
  e={'Action':action,'Package':package}
  if name:e['Test']=name
  if output:e['Output']=output
  if frame:e['OutputType']='frame'
  if error:e['OutputType']='error'
  events.append(e)
 def start(name):event('run',name);event('output',name,'=== RUN   '+name+'\n',True)
 def fail(name):event('output',name,'--- FAIL: '+name+' (0.01s)\n',True);event('fail',name)
 if not unit:start('TestIntegration')
 for backend in ([''] if unit else ['sql','gorm']):
  name='TestG07StreamSendError' if unit else 'TestIntegration/'+backend+'/'+variant['case']
  if not unit:start('TestIntegration/'+backend)
  start(name)
  if not unit:event('output',name,'    fixture_test.go:50: FIXTURE mysql=8.4.7 backend='+backend+'\n')
  event('output',name,'    contract_test.go:12: SEMANTIC_ASSERT '+json.dumps({'marker':variant['marker'],'got':'wrong','want':'contract'})+'\n',error=True)
  fail(name)
  if not unit:fail('TestIntegration/'+backend)
 if not unit:fail('TestIntegration')
 event('output',output='FAIL\n',frame=True);event('output',output='FAIL\t'+package+'\t0.01s\n',frame=True);event('fail')
 return events

def inject_before_fail(events,event):
 result=copy.deepcopy(events)
 index=next(i for i,e in enumerate(result) if e.get('Test')==event.get('Test') and e['Action']=='fail')
 result.insert(index,event)
 return result

class MutantVerifierTests(unittest.TestCase):
 def setUp(self):self.variant=mutants.VARIANTS[0];self.events=control(self.variant)
 def check(self,events):return mutants.verify_rejection(encoded(events),self.variant)
 def test_all_complete_controls(self):
  for v in mutants.VARIANTS:mutants.verify_rejection(encoded(control(v)),v)
 def test_extra_parent_assertion(self):
  e={'Action':'output','Package':'example.com/reservation-service/tests','Test':'TestIntegration','Output':'    database_test.go:50: PARENT_EXTRA_ASSERTION\n'}
  with self.assertRaisesRegex(ValueError,'parent'):self.check(inject_before_fail(self.events,e))
 def test_extra_leaf_cleanup_assertion(self):
  e={'Action':'output','Package':'example.com/reservation-service/tests','Test':'TestIntegration/sql/H10','Output':'    fixture_test.go:58: drop owned schema failed (*mysql.MySQLError)\n'}
  with self.assertRaisesRegex(ValueError,'leaf'):self.check(inject_before_fail(self.events,e))
 def test_missing_package_terminal(self):
  with self.assertRaisesRegex(ValueError,'terminal'):self.check(self.events[:-1])
 def test_duplicate_package_terminal(self):
  with self.assertRaisesRegex(ValueError,'terminal'):self.check(self.events+[self.events[-1]])
 def test_wrong_package(self):
  with self.assertRaisesRegex(ValueError,'package'):self.check([{**e,'Package':'example.org/wrong'} for e in self.events])
 def test_missing_backend(self):
  with self.assertRaisesRegex(ValueError,'inventory'):self.check([e for e in self.events if '/gorm' not in e.get('Test','')])
 def test_wrong_marker(self):
  events=copy.deepcopy(self.events)
  for e in events:
   if 'SEMANTIC_ASSERT' in e.get('Output',''):e['Output']=e['Output'].replace('HTTP_ERROR_BODY','OTHER_ASSERTION')
  with self.assertRaisesRegex(ValueError,'semantic'):self.check(events)
 def test_duplicate_assertion(self):
  assertion=next(e for e in self.events if 'SEMANTIC_ASSERT' in e.get('Output',''))
  with self.assertRaisesRegex(ValueError,'unique'):self.check(inject_before_fail(self.events,assertion))
 def test_unknown_leaf(self):
  with self.assertRaisesRegex(ValueError,'inventory'):self.check(self.events[:-1]+[{'Action':'fail','Package':'example.com/reservation-service/tests','Test':'TestOther'},self.events[-1]])
 def test_real_go127_m06_record(self):
  path=Path(__file__).resolve().parents[1]/'testdata/review-r2/m06-go127.jsonl'
  mutants.verify_rejection(path.read_bytes(),mutants.VARIANTS[-1])
 def test_logged_marker_without_error_attribution(self):
  events=copy.deepcopy(self.events)
  for event in events:
   if 'SEMANTIC_ASSERT' in event.get('Output',''):event.pop('OutputType')
  with self.assertRaisesRegex(ValueError,'attribution'):self.check(events)
 def test_legacy_bad_logs(self):
  base=Path(__file__).resolve().parents[1]/'testdata/review-r1'
  expected={'mutant_extra_parent_assertion.jsonl','mutant_extra_leaf_cleanup_failure.jsonl','mutant_missing_package_terminal.jsonl','mutant_wrong_package.jsonl','mutant_one_backend_missing.jsonl'}
  self.assertEqual({p.name for p in base.glob('*.jsonl')},expected)
  for path in sorted(base.glob('*.jsonl')):
   with self.assertRaises(ValueError,msg=path.name):mutants.verify_rejection(path.read_bytes(),self.variant)

if __name__=='__main__':unittest.main(verbosity=2)
