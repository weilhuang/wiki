#!/usr/bin/env python3
import copy
import unittest
from unittest import mock
import cleanup
import budgets

class CleanupTests(unittest.TestCase):
 def run_cleanup(self,overrides=None,budget=None):
  run_id='abc123review';container='reservation-'+run_id;network=container+'-net';calls=[]
  normal={
   'container-owner':(0,(run_id+'\n').encode()),'mysql-diagnostics':(0,b'diagnostics\n'),
   'container-remove':(0,(container+'\n').encode()),'container-absent':(1,('[]\nError: No such object: '+container+'\n').encode()),
   'network-owner':(0,(run_id+'\n').encode()),'network-remove':(0,(network+'\n').encode()),
   'network-absent':(1,('[]\nError response from daemon: network '+network+' not found\n').encode())}
  normal.update(overrides or {})
  def run(label,cmd,**kw):
   calls.append(label);value=normal[label]
   if isinstance(value,Exception):raise value
   code,raw=value
   if budget is not None:
    reserved=kw.get('cleanup_run',False)
    if len(raw)>budget.remaining(reserved):raise ValueError('output quota exhausted')
    budget.add(len(raw),len(raw),reserved)
   if kw.get('expected_exit',0) is not None and code!=kw.get('expected_exit',0):raise ValueError(label+' failed')
   return {'exitCode':code},raw
  return cleanup.owned_cleanup(run,run_id,container,network),calls
 def test_exact_removal(self):
  report,calls=self.run_cleanup();self.assertEqual(report['status'],'pass');self.assertEqual(report['container'],report['network'],'absent');self.assertIn('network-absent',calls)
 def test_initial_absence(self):
  report,calls=self.run_cleanup({'container-owner':(1,b'Error: No such object: reservation-abc123review\n'),'network-owner':(1,b'Error response from daemon: network reservation-abc123review-net not found\n')})
  self.assertEqual(report['status'],'pass');self.assertEqual(calls,['container-owner','network-owner'])
 def test_unrelated_no_such(self):
  for raw in [b'Error: No such file or directory: /tmp/daemon-config\n',b'Error: No such object: reservation-another\n',b'permission denied\n',b'Cannot connect to the Docker daemon\n']:
   report,calls=self.run_cleanup({'container-owner':(1,raw),'network-owner':(1,raw)})
   self.assertEqual(report['status'],'fail');self.assertEqual(calls,['container-owner','network-owner'])
 def test_wrong_network_name(self):
  report,_=self.run_cleanup({'network-absent':(1,b'Error response from daemon: network wrong not found\n')});self.assertEqual(report['status'],'fail')
 def test_diagnostics_failure_continues(self):
  report,calls=self.run_cleanup({'mysql-diagnostics':(1,b'logs failed\n')});self.assertEqual(report['status'],'fail');self.assertEqual(report['container'],report['network'],'absent');self.assertIn('container-remove',calls);self.assertIn('network-remove',calls)
 def test_container_remove_failure_continues(self):
  report,calls=self.run_cleanup({'container-remove':(1,b'remove failed\n'),'container-absent':(0,b'[]\n')});self.assertEqual(report['status'],'fail');self.assertIn('network-remove',calls);self.assertEqual(report['network'],'absent');self.assertEqual(len(report['errors']),2)
 def test_owner_mismatch_never_deletes(self):
  report,calls=self.run_cleanup({'container-owner':(0,b'other\n')});self.assertEqual(report['status'],'fail');self.assertNotIn('container-remove',calls);self.assertIn('network-remove',calls)
 def test_reserved_logs_survive_normal_exhaustion(self):
  b=budgets.EvidenceBudget();b.add(budgets.NORMAL_BYTES,budgets.NORMAL_BYTES)
  self.assertEqual(b.remaining(),0);self.assertEqual(b.remaining(True),budgets.RESERVED_BYTES)
  with self.assertRaises(ValueError):b.add(1,1)
  report,calls=self.run_cleanup(budget=b);self.assertEqual(report['status'],'pass');self.assertIn('container-remove',calls);self.assertIn('network-remove',calls)
  b.add(3*1024*1024,3*1024*1024,True)
  self.assertLess(b.raw,budgets.NORMAL_BYTES+budgets.RESERVED_BYTES)
 def test_wrapper_includes_cleanup_and_final(self):
  d=budgets.Deadlines(1000,wall_now=1300,monotonic_now=20)
  self.assertEqual(d.wrapper-20,650);self.assertEqual(d.work-20,530);self.assertEqual(d.cleanup-d.work,90);self.assertEqual(d.final-d.cleanup,15)
  with self.assertRaises(TimeoutError):d.command(5,now=d.work)
  self.assertEqual(d.command(5,cleanup=True,now=d.work),5)
 def test_late_job_reduces_wrapper_budget(self):
  d=budgets.Deadlines(1000,wall_now=1800,monotonic_now=20)
  self.assertEqual(d.wrapper-20,400)
  with self.assertRaises(ValueError):budgets.Deadlines(1000,wall_now=2300,monotonic_now=20)
 def test_network_nonzero_not_absence(self):
  for code in [0,2,125]:self.assertFalse(cleanup.absent('network','n',{'exitCode':code},b'Error response from daemon: network n not found'))

if __name__=='__main__':unittest.main(verbosity=2)
