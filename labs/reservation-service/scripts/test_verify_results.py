#!/usr/bin/env python3
import copy
import unittest
import verify_results as v

class VerifyResultsTests(unittest.TestCase):
 def events(self):
  result=[]
  for name in sorted(v.INTEGRATION):
   result.extend([{'Action':'run','Package':v.MODULE+'/tests','Test':name},{'Action':'pass','Package':v.MODULE+'/tests','Test':name}])
  result.append({'Action':'pass','Package':v.MODULE+'/tests'})
  return result
 def check(self,events):return v.verify(events,v.INTEGRATION,v.MODULE+'/tests')
 def test_complete(self):self.assertEqual(len(self.check(self.events())),58)
 def test_missing_case(self):
  events=self.events();name=sorted(v.INTEGRATION)[0]
  with self.assertRaisesRegex(ValueError,'required case missing'):self.check([e for e in events if e.get('Test')!=name])
 def test_skip(self):
  events=self.events();events[1]['Action']='skip'
  with self.assertRaises(ValueError):self.check(events)
 def test_duplicate(self):
  events=self.events();events.insert(1,copy.deepcopy(events[0]))
  with self.assertRaisesRegex(ValueError,'duplicate'):self.check(events)
 def test_empty(self):
  with self.assertRaises(ValueError):self.check([{'Action':'pass','Package':v.MODULE+'/tests'}])
 def test_unknown_failure(self):
  events=self.events();events.append({'Action':'fail','Package':v.MODULE+'/tests','Test':'unexpected'})
  with self.assertRaises(ValueError):self.check(events)
 def test_wrong_version(self):
  actual=dict(v.PINNED,mysql_image='mysql@sha256:0426ec38c7a10aa45ba383887df7878f74ee70e2fd589c7b69207f3577901903',mysql_architecture='amd64');v.verify_versions(actual)
  actual['go']='go1.27.2'
  with self.assertRaises(ValueError):v.verify_versions(actual)
 def test_missing_terminal(self):
  with self.assertRaises(ValueError):self.check(self.events()[:-1])

if __name__=='__main__':unittest.main(verbosity=2)
