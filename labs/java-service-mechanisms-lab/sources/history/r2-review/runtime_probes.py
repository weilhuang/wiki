#!/usr/bin/env python3
"""Independent r2 regression of the r1 false-green failures, plus executor coverage."""
import hashlib,json,os,pathlib,shutil,signal,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parent
LAB=ROOT/'package/labs/java-service-mechanisms-lab'
records=[]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def execute(name,lab):
 out=ROOT/(name+'-run');cmd=['python3',str(lab/'run.py'),'--output',str(out)]
 start=time.monotonic();p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
 try:stdout,_=p.communicate(timeout=20)
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGKILL);stdout,_=p.communicate();raise
 (ROOT/(name+'-runner.txt')).write_text(stdout)
 result=json.loads((out/'result.json').read_text())
 rec={'case':name,'command':cmd,'exitCode':p.returncode,'resultStatus':result['status'],'seconds':time.monotonic()-start,'subprocessRecords':result['records'],'sourceFiles':{p.relative_to(lab).as_posix():digest(p) for p in sorted((lab/'src').glob('*.java'))},'runnerSha256':digest(lab/'run.py')}
 records.append(rec);return out,rec
mutations=[
 ('jmm-child-exception','JmmLab.java','Thread a = children.thread(total::incrementAndGet, "atomic-a");','Thread a = children.thread(() -> { total.incrementAndGet(); throw new IllegalStateException("REVIEWER_CHILD_ATOMIC_FAILURE"); }, "atomic-a");','jmm.txt','UNEXPECTED_CHILD_FAILURE thread=atomic-a','java.lang.IllegalStateException: REVIEWER_CHILD_ATOMIC_FAILURE','JMM_CLEANUP all workers joined','JMM_OK'),
 ('diagnostic-child-exception','DiagnosticLab.java','checksum = value;','checksum = value; throw new IllegalStateException("REVIEWER_CHILD_DIAGNOSTIC_FAILURE");','diagnostic.txt','UNEXPECTED_CHILD_FAILURE thread=lab-cpu-busy','java.lang.IllegalStateException: REVIEWER_CHILD_DIAGNOSTIC_FAILURE','CLEANUP all four workers joined; watchdog joined','DIAGNOSTIC_OK'),
 ('executor-child-exception','ExecutorLab.java','done.add("A");','done.add("A"); throw new IllegalStateException("REVIEWER_CHILD_EXECUTOR_FAILURE");','executor.txt','UNEXPECTED_CHILD_FAILURE thread=ordinary-worker-','java.lang.IllegalStateException: REVIEWER_CHILD_EXECUTOR_FAILURE','EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated','EXECUTOR_OK'),
 ('future-wrong-cause','ExecutorLab.java','throw new IllegalStateException("submit-boom");','throw new IllegalArgumentException("REVIEWER_FUTURE_WRONG_CAUSE");','executor.txt','wrong Future cause','java.lang.IllegalArgumentException: REVIEWER_FUTURE_WRONG_CAUSE','EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated','EXECUTOR_OK'),
 ('ordinary-future-child','ExecutorLab.java','Runnable b = () -> done.add("B");','Runnable b = new FutureTask<Void>(() -> { done.add("B"); throw new IllegalStateException("REVIEWER_ORDINARY_FUTURE_FAILURE"); }, null);','executor.txt','UNEXPECTED_CHILD_FAILURE thread=ordinary-worker-','java.lang.IllegalStateException: REVIEWER_ORDINARY_FUTURE_FAILURE','EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated','EXECUTOR_OK')]
for name,file,old,new,*_ in mutations:
 dst=ROOT/'mutants'/name;dst.mkdir(parents=True);shutil.copytree(LAB/'src',dst/'src');shutil.copyfile(LAB/'run.py',dst/'run.py');f=dst/'src'/file;t=f.read_text();assert t.count(old)==1;t=t.replace(old,new);f.write_text(t)
 (ROOT/(name+'.diff')).write_text(f'{file}\n- {old}\n+ {new}\n')
try:
 out,rec=execute('baseline',LAB)
 assert rec['exitCode']==0 and rec['resultStatus']=='pass'
 assert (out/'compile.txt').read_text()==''
 for name,marker in [('jmm.txt','JMM_OK'),('executor.txt','EXECUTOR_OK'),('diagnostic.txt','DIAGNOSTIC_OK')]:
  text=(out/name).read_text();assert text.splitlines().count(marker)==1;assert 'Exception in thread ' not in text
 for f,token in [('negative-volatile.txt','VOLATILE_COMPOUND_CLAIM expected=2 actual=1'),('negative-max-first.txt','MAX_FIRST_CLAIM expected=2 actual=1'),('negative-drain.txt','DRAIN_CANCEL_CLAIM Future remained NEW')]:
  text=(out/f).read_text();assert [l for l in text.splitlines() if l.startswith('Exception in thread ')]==['Exception in thread "main" java.lang.AssertionError: '+token];assert 'Caused by:' not in text and 'Suppressed:' not in text
 for name,file,old,new,artifact,main,cause,cleanup,success in mutations:
  out,rec=execute(name,ROOT/'mutants'/name);text=(out/artifact).read_text();lines=text.splitlines()
  assert rec['exitCode']==1 and rec['resultStatus']=='fail',name+' false green'
  assert (out/'compile.txt').read_text()=='',name+' compile failure'
  assert next(x for x in rec['subprocessRecords'] if x['artifact']==artifact)['exitCode']==1,name+' wrong child process exit'
  first=next(l for l in lines if l.startswith('Exception in thread '))
  assert first.startswith('Exception in thread "main" java.lang.AssertionError: '+main),(name,first)
  assert 'Caused by: '+cause in text,name+' wrong cause'
  assert lines.count(cleanup)==1 and success not in lines,name+' success/cleanup inconsistency'
  rec['expectedFailureVerified']=True;rec['mainException']=first;rec['exactCause']=cause;rec['cleanupObserved']=True
 finally_ps=subprocess.run(['ps','-eo','comm,args'],capture_output=True,text=True,check=True).stdout
 survivors=[l for l in finally_ps.splitlines() if l.split(maxsplit=1)[0]=='java' and any(' '+c in l for c in ['JmmLab','ExecutorLab','DiagnosticLab'])]
 assert not survivors
 report={'status':'pass','scriptSha256':digest(pathlib.Path(__file__)),'records':records,'survivingLabJvms':survivors,'cleanup':'temporary compiler directories removed; no relevant JVM remains'}
except BaseException as exc:
 report={'status':'fail','error':str(exc),'records':records};raise
finally:
 (ROOT/'runtime-probes.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'status':report['status'],'cases':[(r['case'],r['exitCode'],r['resultStatus']) for r in records],'survivingLabJvms':report.get('survivingLabJvms')},indent=2))
