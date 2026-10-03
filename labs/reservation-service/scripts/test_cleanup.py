#!/usr/bin/env python3
import copy
from pathlib import Path
import re
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

# Deterministic scheduler model, not a MySQL or Go execution. The 100ms rule
# comes from mysql-8.4.7 trx0i_s.cc can_cache_be_updated/end_read; see contract.md.
class ProcessSamplerModelTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lab=Path(__file__).resolve().parents[1]
  cls.source=(cls.lab/'tests/process_test.go').read_text()
  cls.cache_idle=int(re.search(r'const processDBCacheIdle = (\d+) \* time.Millisecond',cls.source)[1])
  cls.live_poll=int(re.search(r'const processDBLivePoll = (\d+) \* time.Millisecond',cls.source)[1])
  cls.cache_cap=int(re.search(r'const processDBCacheSamples = (\d+)',cls.source)[1])
  cls.live_cap=int(re.search(r'const processDBLiveSamples = (\d+)',cls.source)[1])
  if 'const processDBDeadline = time.Second' not in cls.source:raise AssertionError('one second observation deadline changed')
  cls.deadline=1000
 def plan(self,last_completion=0,start=0,cost=0,deadline=None,cap=None):
  deadline=self.deadline if deadline is None else deadline
  cap=self.cache_cap if cap is None else cap
  out=[];now=start
  for _ in range(cap):
   begin=max(now,last_completion+self.cache_idle)
   if begin>=deadline or begin+cost>=deadline:break
   end=begin+cost;out.append((begin,end));now=end;last_completion=end
  return out
 def accept(self,reads,last_completion=0):
  if not reads:raise ValueError('no observations')
  if len(reads)>self.cache_cap:raise ValueError('sample cap')
  for begin,end in reads:
   if begin-last_completion<=100:raise ValueError('cache idle starvation')
   if begin>=self.deadline or end>=self.deadline:raise ValueError('deadline')
   if end<begin:raise ValueError('negative query duration')
   last_completion=end
 def mysql_cache_model(self,reads):
  # Authoritative transaction disappears at t=0. Only a refresh sees it.
  last_read=0;cached=1;seen=[]
  for begin,end in reads:
   if begin-last_read>100:cached=0
   seen.append(cached);last_read=end
  return seen
 def test_old_five_ms_schedule_starves(self):
  old=[(n,n) for n in range(5,1000,5)]
  self.assertEqual(set(self.mysql_cache_model(old)),{1})
  with self.assertRaisesRegex(ValueError,'cache idle starvation'):self.accept(old[:self.cache_cap])
 def test_exact_100ms_is_not_enough(self):
  reads=[(100,100),(200,200)]
  self.assertEqual(self.mysql_cache_model(reads),[1,1])
  with self.assertRaisesRegex(ValueError,'cache idle starvation'):self.accept(reads)
 def test_bound_125ms_schedule_refreshes(self):
  self.assertEqual((self.cache_idle,self.cache_cap,self.live_cap,self.live_poll),(125,8,200,5))
  reads=self.plan();self.accept(reads)
  self.assertEqual([a for a,_ in reads],[125,250,375,500,625,750,875])
  self.assertEqual(set(self.mysql_cache_model(reads)),{0})
 def test_interval_begins_at_query_completion(self):
  reads=self.plan(cost=40);self.accept(reads)
  self.assertEqual(reads[:2],[(125,165),(290,330)])
  wrong=[(125,165),(250,290)]
  with self.assertRaisesRegex(ValueError,'cache idle starvation'):self.accept(wrong)
 def test_deadline_is_not_extended_by_wait_or_query(self):
  self.assertEqual(self.plan(last_completion=900),[])
  self.assertEqual(self.plan(start=950,cost=60),[])
  with self.assertRaisesRegex(ValueError,'deadline'):self.accept([(1000,1000)])
  self.assertTrue(all(end<1000 for _,end in self.plan(start=200,cost=90)))
 def test_caps_and_live_sampling_are_bounded(self):
  self.assertEqual(len(self.plan(last_completion=-125,cap=100)),8)
  self.assertEqual(len(self.plan(deadline=5000)),8)
  with self.assertRaisesRegex(ValueError,'sample cap'):self.accept([(n*125,n*125) for n in range(1,10)])
  live=list(range(0,self.deadline,self.live_poll))[:self.live_cap]
  self.assertEqual((len(live),live[-1]),(200,995))
 def test_go_control_flow_and_global_cache_reader_ownership(self):
  s=self.source
  for fragment in ['lastCacheRead.Add(processDBCacheIdle)','completed := time.Now()','lastCacheRead = completed','sample < processDBCacheSamples','sample < processDBLiveSamples','context.WithTimeout(context.Background(), processDBDeadline)','f.waitProcessDBGone(ctx, target, lastCacheRead)','f.forcedFacts(ctx)']:
   self.assertIn(fragment,s)
  helper=s.split('func (f *fixture) waitDBObservation(',1)[1].split('\n}\n',1)[0]
  self.assertIn('case <-ctx.Done():',helper);self.assertIn('must(f.t, ctx.Err()',helper)
  live=s.split('func (f *fixture) processDBLive(',1)[1].split('\n}\n',1)[0]
  self.assertNotIn('INNODB_TRX',live)
  query_lines=[]
  for p in self.lab.rglob('*.go'):
   source=p.read_text()
   self.assertNotIn('t.Parallel(',source)
   query_lines.extend((p.relative_to(self.lab).as_posix(),line.strip()) for line in source.splitlines() if '"SELECT' in line and 'INNODB_TRX' in line)
  self.assertEqual(len(query_lines),1)
  self.assertEqual(query_lines[0][0],'tests/process_test.go')
  self.assertEqual(s.count('f.processDBTransactions('),2)
  self.assertEqual(s.count('f.waitProcessDBGone('),1)
  self.assertNotIn('time.Sleep(',s)

if __name__=='__main__':unittest.main(verbosity=2)
