#!/usr/bin/env python3
"""Exact Docker absence classification and independent owned cleanup attempts."""
import re

def absent(kind,name,record,raw):
 if type(record.get('exitCode')) is not int or record['exitCode']!=1:return False
 try:text=raw.decode('utf-8').strip()
 except UnicodeDecodeError:return False
 # docker inspect may print its empty JSON result before the one diagnostic.
 if text.startswith('[]\n'):text=text[3:]
 if kind=='container':
  patterns=[r'Error: No such object: '+re.escape(name),r'Error response from daemon: No such container: '+re.escape(name)]
 elif kind=='network':patterns=[r'Error response from daemon: network '+re.escape(name)+r' not found']
 else:return False
 return any(re.fullmatch(pattern,text) for pattern in patterns)

def owned_cleanup(run,run_id,container,network):
 report={'container':'unverified','network':'unverified','diagnostics':'not_collected','errors':[]}
 def failed(stage,error):report['errors'].append({'stage':stage,'type':type(error).__name__,'message':str(error)})
 container_owned=False
 try:
  rec,raw=run('container-owner',['docker','inspect',container,'--format','{{index .Config.Labels "reservation-run"}}'],expected_exit=None,cleanup_run=True,timeout=10)
  if rec['exitCode']==0:
   if raw.decode().strip()!=run_id:raise ValueError('container ownership mismatch')
   container_owned=True
  elif absent('container',container,rec,raw):report['container']='absent';report['diagnostics']='not_applicable_absent'
  else:raise ValueError('container absence/ownership unverified')
 except Exception as error:failed('container-owner',error)
 if container_owned:
  try:
   run('mysql-diagnostics',['docker','logs','--tail','80',container],cleanup_run=True,timeout=10)
   report['diagnostics']='collected'
  except Exception as error:failed('mysql-diagnostics',error)
  # Diagnostic failure does not remove the ownership proof or cancel deletion.
  try:run('container-remove',['docker','rm','-f',container],cleanup_run=True,timeout=15)
  except Exception as error:failed('container-remove',error)
  try:
   rec,raw=run('container-absent',['docker','inspect',container],expected_exit=None,cleanup_run=True,timeout=10)
   if not absent('container',container,rec,raw):raise ValueError('container absence unverified')
   report['container']='absent'
  except Exception as error:failed('container-absent',error)
 # Network processing always occurs, even if container diagnostics/removal failed.
 network_owned=False
 try:
  rec,raw=run('network-owner',['docker','network','inspect',network,'--format','{{index .Labels "reservation-run"}}'],expected_exit=None,cleanup_run=True,timeout=10)
  if rec['exitCode']==0:
   if raw.decode().strip()!=run_id:raise ValueError('network ownership mismatch')
   network_owned=True
  elif absent('network',network,rec,raw):report['network']='absent'
  else:raise ValueError('network absence/ownership unverified')
 except Exception as error:failed('network-owner',error)
 if network_owned:
  try:run('network-remove',['docker','network','rm',network],cleanup_run=True,timeout=10)
  except Exception as error:failed('network-remove',error)
  try:
   rec,raw=run('network-absent',['docker','network','inspect',network],expected_exit=None,cleanup_run=True,timeout=10)
   if not absent('network',network,rec,raw):raise ValueError('network absence unverified')
   report['network']='absent'
  except Exception as error:failed('network-absent',error)
 report['status']='pass' if not report['errors'] and report['container']==report['network']=='absent' else 'fail'
 return report
