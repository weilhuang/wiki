#!/usr/bin/env python3
"""One bounded standard-runner attempt. Requires independent review before dispatch."""
from contextlib import contextmanager
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

import evidence
import cleanup as cleanup_tools
import budgets
import mutants
import verify_results as verify

IMAGE='mysql@sha256:0426ec38c7a10aa45ba383887df7878f74ee70e2fd589c7b69207f3577901903'
PROTOC_URL='https://github.com/protocolbuffers/protobuf/releases/download/v36.2/protoc-36.2-linux-x86_64.zip'
PROTOC_SHA='121f6c7afe1d4d0e3ea6aab9432038599250134cbf4474cb1167d2c7decd4278'
LAB=Path(__file__).resolve().parents[1]

def digest(b):return hashlib.sha256(b).hexdigest()
ROOT=LAB.parents[1]
def inventory():return evidence.source_identity(ROOT)

@contextmanager
def private_workspace(path):
 evidence.require(not sys.flags.optimize and not os.environ.get('PYTHONOPTIMIZE'),'optimized Python forbidden')
 path=evidence.fresh_child(Path(os.environ['RUNNER_TEMP']),path)
 path.mkdir(mode=0o700)
 yield str(path)

def main():
 wrapper_started=time.monotonic();wall_started=time.time()
 args=argparse.ArgumentParser();args.add_argument('--private',required=True);a=args.parse_args()
 if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_OS')!='Linux':raise SystemExit('This reviewed proposal runs only on the standard Linux Actions job')
 # Raw logs and ephemeral credentials stay in a private temporary directory.
 with private_workspace(Path(a.private)) as temporary:
  work=Path(temporary);rawdir=work/'raw';rawdir.mkdir();output=work/'stage';output.mkdir();tools=work/'tools';tools.mkdir();(work/'tmp').mkdir()
  password=secrets.token_hex(24);run_id=secrets.token_hex(8);container='reservation-'+run_id;network=container+'-net'
  limits=budgets.Deadlines(int(os.environ.get('P2_JOB_STARTED_AT','0')),wall_now=wall_started,monotonic_now=wrapper_started)
  commands=[];source={};status='fail';reason=None;cleanup={};versions={};variant_results=[];contract_sha=None
  budget=budgets.EvidenceBudget()
  env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',GOWORK='off',GOENV='off',GOPATH=str(work/'gopath'),GOMODCACHE=str(work/'module-cache'),GOCACHE=str(work/'build-cache'),GOMAXPROCS='2',GOFLAGS='-p=1 -mod=readonly -buildvcs=false',GOMEMLIMIT='768MiB',GOTOOLCHAIN='local',GOBIN=str(tools),GOTMPDIR=str(work/'tmp'),TMPDIR=str(work/'tmp'),MYSQL_ROOT_PASSWORD=password,MYSQL_PWD=password)
  go=shutil.which('go');evidence.require(go is not None,'Go executable absent')
  replacements=[(str(Path(go).resolve().parents[1]).encode(),b'[GO_SDK]'),(password.encode(),b'[REDACTED]'),(str(work).encode(),b'[TASK]'),(str(LAB).encode(),b'[PACKAGE]')]
  for name in ('GITHUB_WORKSPACE','RUNNER_TEMP','HOME'):
   if os.environ.get(name):replacements.append((os.environ[name].encode(),('['+name+']').encode()))
  evidence_index={}
  def publish(name,raw,reserved=False):
   evidence.require(evidence.allowed(name) and name not in evidence_index,'unexpected or duplicate evidence name')
   evidence.require(len(raw)<=(1024*1024 if reserved else evidence.PER_FILE),'evidence size exceeds phase bound')
   public=raw
   for before,after in replacements:public=public.replace(before,after)
   evidence.require(len(public)<=evidence.PER_FILE,'redacted evidence size exceeds bound')
   evidence.require(len(evidence_index)<(evidence.MAX_FILES-1 if reserved else evidence.MAX_FILES-16),'file count reserve exhausted')
   budget.add(len(raw),len(public),reserved=reserved)
   (rawdir/name).write_bytes(raw);(output/name).write_bytes(public)
   identity={'file':name,'rawSHA256':digest(raw),'publicSHA256':digest(public),'rawBytes':len(raw),'publicBytes':len(public),'changed':public!=raw}
   evidence_index[name]=identity
   return identity
  def run(label,cmd,cwd=LAB,env=env,timeout=60,expected_exit=0,cleanup_run=False):
   seconds=limits.command(timeout,cleanup=cleanup_run)
   expansion=math.prod(max(1,math.ceil(len(after)/len(before))) for before,after in replacements)
   maximum=min(65536 if cleanup_run else evidence.PER_FILE,budget.remaining(reserved=cleanup_run)//expansion)
   if maximum<=0:raise ValueError('normal evidence budget exhausted; cleanup reserve retained')
   capture,raw=evidence.capture(cmd,cwd,env,seconds,maximum=maximum)
   record={'label':label,'argv':[Path(str(x)).name if i==0 else str(x).replace(str(work),'[TASK]').replace(str(LAB),'[PACKAGE]') for i,x in enumerate(cmd)],'cwd':'[PACKAGE]' if cwd==LAB else '[VARIANT]',**capture,'evidence':publish(label+'.log',raw,reserved=cleanup_run)}
   commands.append(record)
   if capture['timeout'] or capture['outputBoundExceeded'] or capture['captureFailure'] or capture['leftoverProcess'] or not capture['processGroupClear']:raise ValueError(label+' incomplete bounded command')
   if expected_exit is not None and capture['exitCode']!=expected_exit:raise ValueError(label+' unexpected exit '+str(capture['exitCode']))
   return record,raw
  try:
   source=inventory();publish('source-before.json',json.dumps(source,sort_keys=True).encode()+b'\n',reserved=True)
   contract_sha=digest(evidence.bounded_read(ROOT/'labs/reservation-service-reviewed.json'))
   pins=json.loads(evidence.bounded_read(LAB/'pins.json'))
   if pins['runtime']!=verify.PINNED or pins['mysql_image']!=IMAGE or pins['protoc_sha256']!=PROTOC_SHA:raise ValueError('frozen version contract differs')
   _,raw=run('go-version',[go,'version']);parts=raw.decode().strip().split();versions['go']=parts[2]
   if versions['go']!='go1.27.1':raise ValueError('wrong Go SDK')
   run('module-download',[go,'mod','download'],timeout=120)
   run('module-verify',[go,'mod','verify'],timeout=120)
   _,raw=run('module-graph',[go,'list','-m','-json','all'],timeout=120)
   decoder=json.JSONDecoder();remaining=raw.decode()
   while remaining.strip():
    item,offset=decoder.raw_decode(remaining.lstrip());remaining=remaining.lstrip()[offset:]
    if item.get('Path') in verify.PINNED:versions[item['Path']]=item.get('Version')
   archive=work/'protoc.zip'
   run('download-protoc',[sys.executable,'-B','scripts/download_protoc.py','--destination',str(archive)],timeout=40)
   data=evidence.bounded_read(archive)
   if digest(data)!=PROTOC_SHA:raise ValueError('protoc archive identity mismatch')
   with zipfile.ZipFile(archive) as z:
    for entry in z.infolist():
     p=Path(entry.filename)
     if p.is_absolute() or '..' in p.parts or stat.S_ISLNK(entry.external_attr>>16):raise ValueError('unsafe protoc archive entry')
    z.extractall(work/'protoc')
   protoc=work/'protoc/bin/protoc';protoc.chmod(0o755)
   env['PATH']=str(tools)+os.pathsep+env['PATH']
   run('install-go-generator',[go,'install','google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.11'],timeout=120)
   run('install-grpc-generator',[go,'install','google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.6.1'],timeout=120)
   for name,cmd in [('protoc',[str(protoc),'--version']),('protoc-gen-go',[str(tools/'protoc-gen-go'),'--version']),('protoc-gen-go-grpc',[str(tools/'protoc-gen-go-grpc'),'--version'])]:
    _,raw=run(name,cmd);versions[name]=raw.decode().strip()
   generated=work/'generated';generated.mkdir()
   run('regenerate',[str(protoc),'--go_out='+str(generated),'--go_opt=paths=source_relative','--go-grpc_out='+str(generated),'--go-grpc_opt=paths=source_relative','api/reservation/v1/reservation.proto'])
   for name in ('reservation.pb.go','reservation_grpc.pb.go'):
    rel=Path('api/reservation/v1')/name
    if (LAB/rel).read_bytes()!=(generated/rel).read_bytes():raise ValueError('generated output differs: '+name)
   run('build',[go,'build','-tags=nomsgpack','-o',str(work/'reservationd'),'./cmd/reservationd'],timeout=180)
   env['RESERVATION_BIN']=str(work/'reservationd')
   run('validator-self-test',[sys.executable,'-B','scripts/test_verify_results.py'])
   run('evidence-self-test',[sys.executable,'-B','scripts/test_evidence.py'])
   run('cleanup-self-test',[sys.executable,'-B','scripts/test_cleanup.py'])
   run('mutant-verifier-self-test',[sys.executable,'-B','scripts/test_mutants.py'])
   run('unit',[go,'test','-tags=nomsgpack','-json','-count=1','-timeout=20s','./internal/grpcapi'],timeout=120)
   run('pull-mysql',['docker','pull',IMAGE],timeout=120)
   _,raw=run('mysql-architecture',['docker','image','inspect',IMAGE,'--format','{{.Architecture}}']);versions['mysql_architecture']=raw.decode().strip()
   run('network-create',['docker','network','create','--label','reservation-run='+run_id,network])
   run('mysql-start',['docker','run','-d','--name',container,'--label','reservation-run='+run_id,'--network',network,'--cpus=2','--memory=1g','--pids-limit=128','--tmpfs','/var/lib/mysql:rw,size=512m','--tmpfs','/tmp:rw,size=64m','--tmpfs','/var/run/mysqld:rw,size=16m','-p','127.0.0.1::3306','-e','MYSQL_ROOT_PASSWORD','-e','MYSQL_ROOT_HOST=%',IMAGE])
   _,raw=run('mysql-image',['docker','inspect',container,'--format','{{.Config.Image}}']);versions['mysql_image']=raw.decode().strip()
   _,raw=run('mysql-port',['docker','port',container,'3306/tcp']);endpoint=raw.decode().strip()
   if not endpoint.startswith('127.0.0.1:') or not endpoint.split(':')[-1].isdigit():raise ValueError('non-loopback mysql port')
   # Readiness polls a server query; elapsed time is not evidence of readiness.
   ready_deadline=time.monotonic()+60;attempt=0
   while True:
    attempt+=1
    rec,raw=run('mysql-ready-'+str(attempt),['docker','exec','-e','MYSQL_PWD',container,'mysql','-uroot','-Nse','SELECT VERSION()'],timeout=5,expected_exit=None)
    if rec['exitCode']==0:versions['mysql']=raw.decode().strip();break
    if time.monotonic()>=ready_deadline or attempt>=120:raise TimeoutError('mysql readiness deadline')
    time.sleep(.5)
   verify.verify_versions(versions)
   env['RESERVATION_MYSQL_ADMIN_DSN']='root:'+password+'@tcp('+endpoint+')/'
   replacements.insert(0,(env['RESERVATION_MYSQL_ADMIN_DSN'].encode(),b'[REDACTED_DSN]'))
   run('integration',[go,'test','-tags=integration,nomsgpack','-json','-count=1','-timeout=90s','./tests'],timeout=180)
   verify.verify(verify.load_events(rawdir/'unit.log'),verify.UNIT,verify.MODULE+'/internal/grpcapi')
   verify.verify(verify.load_events(rawdir/'integration.log'),verify.INTEGRATION,verify.MODULE+'/tests')
   # Probe a saved successful record with one mandatory case removed.
   events=verify.load_events(rawdir/'integration.log');removed=sorted(verify.INTEGRATION)[0]
   try:verify.verify([e for e in events if e.get('Test')!=removed],verify.INTEGRATION,verify.MODULE+'/tests')
   except ValueError:pass
   else:raise ValueError('validator accepted a missing required case')
   if inventory()!=source:raise ValueError('tested source changed during execution')
   variant_results=mutants.run_variants(LAB,work,run,go,env)
   if len(variant_results)!=6:raise ValueError('missing semantic variant')
   if inventory()!=source:raise ValueError('mutant modified baseline source')
   status='pass'
  except Exception as error:
   reason=type(error).__name__+': '+str(error)
  finally:
   # Diagnostics, container and network cleanup are independent best-effort stages.
   # Their output has a separate reserve even when normal output hit its cap.
   cleanup=cleanup_tools.owned_cleanup(run,run_id,container,network)
   if cleanup['status']!='pass':status='fail'
   try:
    after=inventory()
    if after!=source or digest(evidence.bounded_read(ROOT/'labs/reservation-service-reviewed.json'))!=contract_sha:raise ValueError('source or review contract differs at final collection')
    publish('source-after.json',json.dumps(after,sort_keys=True).encode()+b'\n',reserved=True)
   except Exception as error:status='fail';reason='final source identity: '+type(error).__name__
   record={'status':status,'reason':reason,'versions':versions,'sourceSHA256':source,'commands':commands,'mutants':variant_results,'cleanup':cleanup,'requiredIntegrationCases':sorted(verify.INTEGRATION),'requiredUnitCases':sorted(verify.UNIT),'sourceCommit':os.environ.get('GITHUB_SHA'),'prHead':os.environ.get('PR_HEAD_SHA'),'prBase':os.environ.get('PR_BASE_SHA'),'sourceID':evidence.source_id(source),'protocArchiveSHA256':PROTOC_SHA,'runID':os.environ.get('GITHUB_RUN_ID'),'runAttempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'reviewContractSHA256':contract_sha,'timing':{'jobStartedAt':int(os.environ['P2_JOB_STARTED_AT']),'wrapperElapsedSeconds':round(time.monotonic()-wrapper_started,3),'wrapperInternalLimitSeconds':budgets.WRAPPER_SECONDS,'outerTerminationLimitSeconds':660,'workDeadlineOffset':round(limits.work-limits.started,3),'cleanupDeadlineOffset':round(limits.cleanup-limits.started,3),'finalDeadlineOffset':round(limits.final-limits.started,3)},'logBudget':vars(budget)}
   if time.monotonic()>=limits.final:record['status']='fail';status='fail';record['finalizationDeadlineExceeded']=True
   publish('result.json',json.dumps(record,indent=2).encode()+b'\n',reserved=True)
   (work/'redaction-rules.json').write_text(json.dumps([[a.decode(),b.decode()] for a,b in replacements]))
   index_raw=(json.dumps(evidence_index,indent=2)+'\n').encode()
   evidence.require(len(index_raw)<=256*1024 and budget.public+len(index_raw)<=evidence.TOTAL,'final index reserve exceeded')
   (output/'evidence-index.json').write_bytes(index_raw)
  print('reservation contract '+status)
  return 0 if status=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
