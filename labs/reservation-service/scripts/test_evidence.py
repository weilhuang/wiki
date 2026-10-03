#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import evidence as e

class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def stage(self):
  private=self.base/'private';private.mkdir();(private/'raw').mkdir();(private/'stage').mkdir()
  (private/'redaction-rules.json').write_text(json.dumps([['secret','xxxxxx']]))
  index={}
  for name in ['result.json','source-before.json','source-after.json']:
   raw=b'{"value":"secret"}\n';public=b'{"value":"xxxxxx"}\n'
   (private/'raw'/name).write_bytes(raw);(private/'stage'/name).write_bytes(public)
   index[name]=dict(rawSHA256=e.sha(raw),publicSHA256=e.sha(public),rawBytes=len(raw),publicBytes=len(public),changed=True)
  (private/'stage/evidence-index.json').write_text(json.dumps(index))
  return private
 def test_fresh_destination(self):
  p=self.stage();result=e.collect(p,self.base/'upload',self.base);self.assertEqual(result['files'],4)
 def test_existing_destination(self):
  p=self.stage();(self.base/'upload').mkdir()
  with self.assertRaisesRegex(ValueError,'pre-existing'):e.collect(p,self.base/'upload',self.base)
 def test_symlink_destination(self):
  p=self.stage();(self.base/'upload').symlink_to(self.base/'other')
  with self.assertRaisesRegex(ValueError,'symlink'):e.collect(p,self.base/'upload',self.base)
 def test_outside_destination(self):
  p=self.stage()
  with self.assertRaisesRegex(ValueError,'outside'):e.collect(p,self.base/'child/upload',self.base)
 def test_symlink_input(self):
  p=self.stage();f=p/'stage/result.json';f.unlink();f.symlink_to(p/'raw/result.json')
  with self.assertRaisesRegex(ValueError,'symlink'):e.collect(p,self.base/'upload',self.base)
 def test_equal_length_changed_content(self):
  p=self.stage();index=json.loads((p/'stage/evidence-index.json').read_text());index['result.json']['changed']=False;(p/'stage/evidence-index.json').write_text(json.dumps(index))
  with self.assertRaisesRegex(ValueError,'metadata'):e.collect(p,self.base/'upload',self.base)
 def test_unexplained_transform(self):
  p=self.stage();f=p/'stage/result.json';public=b'{"value":"yyyyyy"}\n';f.write_bytes(public);index=json.loads((p/'stage/evidence-index.json').read_text());index['result.json']['publicSHA256']=e.sha(public);(p/'stage/evidence-index.json').write_text(json.dumps(index))
  with self.assertRaisesRegex(ValueError,'unexplained'):e.collect(p,self.base/'upload',self.base)
 def test_total_bound(self):
  p=self.stage()
  with mock.patch.object(e,'TOTAL',10):
   with self.assertRaisesRegex(ValueError,'total'):e.collect(p,self.base/'upload',self.base)
 def test_count_bound(self):
  p=self.stage()
  with mock.patch.object(e,'MAX_FILES',3):
   with self.assertRaisesRegex(ValueError,'count'):e.collect(p,self.base/'upload',self.base)
 def test_unexpected_file(self):
  p=self.stage();(p/'stage/unexpected.txt').write_text('x')
  with self.assertRaisesRegex(ValueError,'unexpected'):e.collect(p,self.base/'upload',self.base)
 def test_output_bound_terminates(self):
  record,raw=e.capture([sys.executable,'-c','import os; os.write(1,b"x"*4096)'],self.base,os.environ.copy(),2,maximum=128)
  self.assertTrue(record['outputBoundExceeded']);self.assertEqual(len(raw),128)
 def test_command_pass(self):
  record,raw=e.capture([sys.executable,'-c','print("ok")'],self.base,os.environ.copy(),2)
  self.assertEqual(raw,b'ok\n');self.assertEqual(record['exitCode'],0);self.assertTrue(record['processGroupClear'])
 def test_raw_total_independent_of_public(self):
  p=self.stage();secret='x'*600;(p/'redaction-rules.json').write_text(json.dumps([[secret,'r']]))
  index={}
  for name in ['result.json','source-before.json','source-after.json','go-version.log','unit.log']:
   raw=secret.encode();public=b'r';(p/'raw'/name).write_bytes(raw);(p/'stage'/name).write_bytes(public)
   index[name]=dict(rawSHA256=e.sha(raw),publicSHA256=e.sha(public),rawBytes=len(raw),publicBytes=len(public),changed=True)
  (p/'stage/evidence-index.json').write_text(json.dumps(index))
  with mock.patch.object(e,'TOTAL',2500):
   with self.assertRaisesRegex(ValueError,'raw'):e.collect(p,self.base/'upload',self.base)
  self.assertFalse((self.base/'upload').exists())
 def test_capture_has_wall_deadline(self):
  started=time.monotonic()
  record,raw=e.capture([sys.executable,'-c','import time; time.sleep(10)'],self.base,os.environ.copy(),.05)
  self.assertTrue(record['timeout']);self.assertLess(time.monotonic()-started,2.5);self.assertNotEqual(record['exitCode'],0)
 def test_wrapper_omission(self):
  (self.base/'labs').mkdir();(self.base/'labs/reservation-service-reviewed.json').write_text(json.dumps({'scope':'real-mysql-http-grpc-reservation-service','sourceSHA256':{}}))
  with self.assertRaisesRegex(ValueError,'wrapper'):e.source_identity(self.base)

if __name__=='__main__':unittest.main(verbosity=2)
