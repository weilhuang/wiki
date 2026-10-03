#!/usr/bin/env python3
"""Bounded source mutations for the r1 independent review findings.
SPDX-License-Identifier: MIT
Sequential JVMs only. Run only while holding the shared Java execution lease.
"""
import argparse, difflib, hashlib, json, os, pathlib, shutil, signal, subprocess, tempfile
ROOT = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--output',required=True,type=pathlib.Path)
args=parser.parse_args();out=args.output.resolve()
if out.exists(): raise SystemExit('Refusing to overwrite regression evidence')
out.mkdir(parents=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
mutations=[
 ('atomic-child','JmmLab.java','Thread a = children.thread(total::incrementAndGet, "atomic-a");','Thread a = children.thread(() -> { total.incrementAndGet(); throw new IllegalStateException("REVIEWER_CHILD_ATOMIC_FAILURE"); }, "atomic-a");','jmm.txt','REVIEWER_CHILD_ATOMIC_FAILURE','java.lang.IllegalStateException','JMM_CLEANUP all workers joined'),
 ('diagnostic-child','DiagnosticLab.java','checksum = value;','checksum = value; throw new IllegalStateException("REVIEWER_CHILD_DIAGNOSTIC_FAILURE");','diagnostic.txt','REVIEWER_CHILD_DIAGNOSTIC_FAILURE','java.lang.IllegalStateException','CLEANUP all four workers joined; watchdog joined'),
 ('executor-child','ExecutorLab.java','done.add("A");','done.add("A"); throw new IllegalStateException("REVIEWER_CHILD_EXECUTOR_FAILURE");','executor.txt','REVIEWER_CHILD_EXECUTOR_FAILURE','java.lang.IllegalStateException','EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated'),
 ('ordinary-future-child','ExecutorLab.java','Runnable b = () -> done.add("B");','Runnable b = new FutureTask<Void>(() -> { done.add("B"); throw new IllegalStateException("REVIEWER_ORDINARY_FUTURE_FAILURE"); }, null);','executor.txt','REVIEWER_ORDINARY_FUTURE_FAILURE','java.lang.IllegalStateException','EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated'),
 ('future-wrong-cause','ExecutorLab.java','throw new IllegalStateException("submit-boom");','throw new IllegalArgumentException("REVIEWER_FUTURE_WRONG_CAUSE");','executor.txt','REVIEWER_FUTURE_WRONG_CAUSE','java.lang.IllegalArgumentException','EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated')]
records=[]
try:
 for name,file,old,new,artifact,marker,cause,cleanup in mutations:
  case=out/name;case.mkdir()
  with tempfile.TemporaryDirectory(prefix='java-mechanism-mutant-') as tmp:
   lab=pathlib.Path(tmp)
   shutil.copytree(ROOT/'src',lab/'src');shutil.copyfile(ROOT/'run.py',lab/'run.py')
   target=lab/'src'/file;before=target.read_text();assert before.count(old)==1,(name,old)
   target.write_text(before.replace(old,new))
   (case/'mutation.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),target.read_text().splitlines(True),fromfile='a/src/'+file,tofile='b/src/'+file)))
   # Exact mutant source is reviewable; no compiled artifacts are retained.
   shutil.copytree(lab/'src',case/'src');shutil.copyfile(lab/'run.py',case/'run.py')
   cmd=['python3',str(lab/'run.py'),'--output',str(case/'proof')]
   p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
   try: stdout,_=p.communicate(timeout=20)
   except subprocess.TimeoutExpired:
    os.killpg(p.pid,signal.SIGTERM)
    try: stdout,_=p.communicate(timeout=2)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);stdout,_=p.communicate(timeout=2)
    raise AssertionError(name+': runner timeout, not an accepted target failure')
   # Only private temp/workspace paths are replaced; Java artifact contents stay original.
   stdout=stdout.replace(str(lab),'<mutant-lab>').replace(str(out),'<regression-output>')
   (case/'runner.txt').write_text(stdout)
   result=json.loads((case/'proof/result.json').read_text())
   text=(case/'proof'/artifact).read_text()
   assert p.returncode != 0 and result['status']=='fail',name+' false green'
   assert 'Caused by: '+cause+': '+marker in text,name+' exact cause missing'
   assert 'CIRCULAR REFERENCE' not in text,name+' duplicate/circular cause graph'
   assert cleanup in text,name+' cleanup was not observed'
   assert 'compile.txt' in [r['artifact'] for r in result['records']] and (case/'proof/compile.txt').read_text()=='',name+' not a runtime mutation'
   assert not any(line in text.splitlines() for line in ['JMM_OK' if name=='atomic-child' else 'DIAGNOSTIC_OK' if name=='diagnostic-child' else 'EXECUTOR_OK']),name+' incorrectly completed'
   records.append({'case':name,'status':'expected-failure','runnerExitCode':p.returncode,'resultStatus':result['status'],'requiredCause':cause+': '+marker,'cleanupMarker':cleanup,'sourceFiles':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p)} for p in sorted((case/'src').glob('*.java'))]+[{'path':(case/'run.py').relative_to(out).as_posix(),'sha256':sha(case/'run.py')}]})
 ps=subprocess.run(['ps','-eo','comm,args'],capture_output=True,text=True,check=True).stdout
 survivors=[line for line in ps.splitlines() if line.split(maxsplit=1)[0]=='java' and any(' '+c in line for c in ['JmmLab','ExecutorLab','DiagnosticLab'])]
 assert not survivors,'surviving lab JVMs'
 (out/'result.json').write_text(json.dumps({'status':'pass','records':records,'sourceScriptSha256':sha(pathlib.Path(__file__)),'survivingLabJvms':survivors,'limits':'Five sequential source mutants; existing JDK; 64MiB heap/2 ActiveProcessorCount; no binary artifacts'},indent=2)+'\n')
 print('PASS: source-level child/future mutations fail for intended cause with cleanup')
except BaseException as e:
 (out/'result.json').write_text(json.dumps({'status':'fail','error':str(e),'records':records},indent=2)+'\n')
 raise
