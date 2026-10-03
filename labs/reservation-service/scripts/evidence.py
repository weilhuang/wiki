#!/usr/bin/env python3
"""Bounded command output and independent upload staging for this package."""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time

PER_FILE=8*1024*1024
TOTAL=32*1024*1024
MAX_FILES=192
LABELS={'go-version','module-download','download-protoc','cleanup-self-test','mutant-verifier-self-test','module-verify','module-graph','install-go-generator','install-grpc-generator','protoc','protoc-gen-go','protoc-gen-go-grpc','regenerate','build','validator-self-test','evidence-self-test','unit','pull-mysql','mysql-architecture','network-create','mysql-start','mysql-image','mysql-port','integration','M01','M02','M03','M04','M05','M06','container-owner','mysql-diagnostics','container-remove','container-absent','network-owner','network-remove','network-absent'}

def require(ok,message):
 if not ok:raise ValueError(message)

def safe_path(path,exists=True):
 path=Path(path).absolute();require('..' not in path.parts,'parent traversal')
 for item in list(path.parents)[::-1]+[path]:require(not item.is_symlink(),'symlink in path')
 if exists:require(path.exists(),'required path absent')
 return path

def fresh_child(base,path):
 base=safe_path(base);path=safe_path(path,False)
 require(path.parent==base,'destination outside runner temp')
 require(not path.exists(),'pre-existing destination')
 return path

def bounded_read(path,maximum=PER_FILE):
 path=safe_path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_size<=maximum,'not a bounded regular file')
  blocks=[];n=0
  while True:
   block=os.read(fd,min(65536,maximum+1-n))
   if not block:break
   blocks.append(block);n+=len(block);require(n<=maximum,'file grew beyond bound')
  after=os.fstat(fd);require((before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'file changed during read')
  return b''.join(blocks)
 finally:os.close(fd)

def capture(argv,cwd,env,timeout,maximum=PER_FILE):
 """At most maximum bytes retained; excess terminates only our own process group."""
 started=time.monotonic();proc=subprocess.Popen(argv,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
 selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
 blocks=[];size=0;timed_out=False;overflow=False;failure=None;leaked=False
 try:
  while selector.get_map():
   left=timeout-(time.monotonic()-started)
   if left<=0:timed_out=True;raise TimeoutError('command deadline')
   for key,_ in selector.select(min(left,.1)):
    data=os.read(key.fd,65536)
    if not data:selector.unregister(key.fileobj);continue
    room=maximum-size;blocks.append(data[:room]);size+=min(room,len(data))
    if len(data)>room:overflow=True;raise ValueError('command output exceeded bound')
  proc.wait(timeout=max(.01,timeout-(time.monotonic()-started)))
 except (TimeoutError,subprocess.TimeoutExpired) as error:timed_out=True;failure=type(error).__name__
 except Exception as error:failure=type(error).__name__
 finally:
  selector.close();proc.stdout.close()
  try:os.killpg(proc.pid,0)
  except ProcessLookupError:pass
  else:
   leaked=proc.poll() is not None
   try:os.killpg(proc.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   try:proc.wait(timeout=1)
   except subprocess.TimeoutExpired:
    try:os.killpg(proc.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    proc.wait(timeout=1)
   # A leader may exit before a descendant. Kill the same owned group again.
   try:os.killpg(proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  try:os.killpg(proc.pid,0);group_clear=False
  except ProcessLookupError:group_clear=True
 return {'exitCode':proc.returncode,'timeout':timed_out,'outputBoundExceeded':overflow,'captureFailure':failure,'leftoverProcess':leaked,'processGroupClear':group_clear,'seconds':round(time.monotonic()-started,3)},b''.join(blocks)

def sha(raw):return hashlib.sha256(raw).hexdigest()
def source_id(values):return sha(json.dumps(values,sort_keys=True,separators=(',',':')).encode())

def source_identity(root):
 root=safe_path(root);contract=json.loads(bounded_read(root/'labs/reservation-service-reviewed.json'));expected=contract['sourceSHA256']
 required={'.github/workflows/reservation-service.yml','labs/reservation-service/scripts/run_ci.py','labs/reservation-service/scripts/evidence.py','labs/reservation-service/scripts/collect.py','labs/reservation-service/scripts/verify_results.py','labs/reservation-service/scripts/mutants.py','labs/reservation-service/scripts/cleanup.py','labs/reservation-service/scripts/budgets.py','labs/reservation-service/scripts/download_protoc.py','labs/reservation-service/pins.json','labs/reservation-service/acceptance-matrix.json'}
 require(contract.get('scope')=='real-mysql-http-grpc-reservation-service','wrong review scope')
 require(required<=set(expected),'critical wrapper source omitted')
 for name,value in expected.items():
  require(re.fullmatch(r'[A-Za-z0-9_./-]+',name) and not name.startswith('/') and '..' not in name.split('/'),'invalid source path')
  require(name.startswith('labs/reservation-service/') or name=='.github/workflows/reservation-service.yml','source outside package scope')
  require(re.fullmatch('[a-f0-9]{64}',value),'invalid source digest')
 actual={name:sha(bounded_read(root/name)) for name in sorted(expected)}
 lab=root/'labs/reservation-service';files=set()
 for path in lab.rglob('*'):
  require(not path.is_symlink(),'symlink in source')
  if path.is_file():files.add(path.relative_to(root).as_posix())
 require(files=={k for k in expected if k.startswith('labs/reservation-service/')},'unexpected or missing package source')
 require(actual==expected and source_id(actual)==contract.get('sourceID'),'reviewed source bytes changed')
 return actual

def allowed(name):
 if name in {'result.json','source-before.json','source-after.json'}:return True
 if name.endswith('.log') and name[:-4] in LABELS:return True
 return bool(re.fullmatch(r'mysql-ready-(?:[1-9]|[1-9][0-9]|1[01][0-9]|120)\.log',name))

def collect(private,output,temp):
 private=safe_path(private);require(private.parent==safe_path(temp),'private directory outside runner temp')
 output=fresh_child(temp,output)
 stage=safe_path(private/'stage');index=json.loads(bounded_read(stage/'evidence-index.json'))
 require(isinstance(index,dict) and 0<len(index)<=MAX_FILES-1,'invalid evidence count')
 require({'result.json','source-before.json','source-after.json'}<=set(index),'required provenance missing')
 found={p.name for p in stage.iterdir()};require(found==set(index)|{'evidence-index.json'},'unexpected or missing staged evidence')
 rules=json.loads(bounded_read(private/'redaction-rules.json'))
 require(isinstance(rules,list) and 1<=len(rules)<=12 and all(isinstance(r,list) and len(r)==2 and all(isinstance(s,str) and 0<len(s)<=4096 for s in r) for r in rules),'invalid private redaction rules')
 content={};total=0;raw_total=0
 for name,identity in sorted(index.items()):
  require(allowed(name),'unexpected evidence name')
  raw=bounded_read(private/'raw'/name);public=bounded_read(stage/name)
  raw_total+=len(raw);require(raw_total<=TOTAL,'total raw evidence size exceeded')
  expected_public=raw
  for before,after in rules:expected_public=expected_public.replace(before.encode(),after.encode())
  require(public==expected_public,'unexplained public evidence transformation')
  require(sha(raw)==identity['rawSHA256'] and sha(public)==identity['publicSHA256'],'evidence byte identity differs')
  require(len(raw)==identity['rawBytes'] and len(public)==identity['publicBytes'] and (public!=raw)==identity['changed'],'evidence size/content metadata differs')
  total+=len(public);require(total<=TOTAL,'total upload size exceeded');content[name]=public
 index_raw=bounded_read(stage/'evidence-index.json');total+=len(index_raw);require(total<=TOTAL,'total upload size exceeded')
 # All checks finish before the fresh public directory is created.
 output.mkdir(mode=0o700)
 for name,raw in content.items():(output/name).write_bytes(raw)
 (output/'evidence-index.json').write_bytes(index_raw)
 return {'files':len(content)+1,'bytes':total,'rawBytes':raw_total}
