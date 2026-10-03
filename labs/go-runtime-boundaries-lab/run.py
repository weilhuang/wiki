#!/usr/bin/env python3
"""Finite Go experiments. Only run with the machine owner's shared-slot grant."""
import argparse, hashlib, json, os, re, signal, subprocess, sys, time
from pathlib import Path

def target_rejection(code, text, test, marker):
    return code == 1 and f'--- FAIL: {test} ' in text and marker in text and '[build failed]' not in text and 'panic: test timed out' not in text

def verifier_regressions():
    cases=[
      ('target',1,'--- FAIL: TestPublishedPayload (0.00s)\nOWNERSHIP_REJECT',True),
      ('compile',1,'OWNERSHIP_REJECT\n[build failed]',False),
      ('wrong-test',1,'--- FAIL: Other (0.00s)\nOWNERSHIP_REJECT',False),
      ('wrong-marker',1,'--- FAIL: TestPublishedPayload (0.00s)\nOTHER',False),
      ('false-green',0,'--- FAIL: TestPublishedPayload (0.00s)\nOWNERSHIP_REJECT',False),
      ('timeout',1,'--- FAIL: TestPublishedPayload (0.00s)\nOWNERSHIP_REJECT\npanic: test timed out',False)]
    result=[]
    for name,code,text,want in cases:
        got=target_rejection(code,text,'TestPublishedPayload','OWNERSHIP_REJECT')
        if got!=want:raise RuntimeError(f'VERIFIER_REGRESSION {name}')
        result.append({'case':name,'acceptedAsTargetRejection':got})
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--go',default='go')
    p.add_argument('--cache')
    p.add_argument('--private',required=True)
    p.add_argument('--seconds',type=int,default=180)
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    private=Path(args.private).resolve();private.mkdir(parents=True,exist_ok=True)
    proof=root/'proof';proof.mkdir(exist_ok=True)
    env=os.environ.copy()
    env.update({'GOTOOLCHAIN':'local','GOWORK':'off','GOENV':'off','GOFLAGS':'','GOPROXY':'off','GOSUMDB':'off','GOMAXPROCS':'2'})
    if args.cache:env['GOCACHE']=args.cache
    deadline=time.monotonic()+args.seconds
    records=[]
    sourcefiles=[{'path':str(f.relative_to(root)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in sorted(root.rglob('*')) if f.is_file() and f.suffix in {'.go','.py'} or f.is_file() and f.name=='go.mod']
    (proof/'input-source-hashes.json').write_text(json.dumps(sourcefiles,indent=2)+'\n')
    def sanitize(s):
        for old,new in [(str(private),'PRIVATE'),(str(root),'.'),(str(Path(args.go).parent.parent),'GO_TOOLCHAIN')]:
            if len(old)>1:s=s.replace(old,new)
        return re.sub(r'/workspace/[^\s\"]+','PRIVATE_PATH',s)
    def save():
        (proof/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
    def run(name,cmd,expected=0,variant=None,binary=False,timeout=45):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise RuntimeError('GLOBAL_TIMEOUT')
        runenv=env.copy()
        if variant:runenv['LAB_VARIANT']=variant
        start=time.monotonic()
        proc=subprocess.Popen(cmd,cwd=root,env=runenv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        timedout=False
        try:out,err=proc.communicate(timeout=min(timeout,remaining))
        except subprocess.TimeoutExpired:
            timedout=True;os.killpg(proc.pid,signal.SIGKILL);out,err=proc.communicate()
        (private/(name+'.stdout')).write_bytes(out);(private/(name+'.stderr')).write_bytes(err)
        text=(out+err).decode('utf-8','replace')
        public_cmd=' '.join(['go' if n==0 and v==args.go else sanitize(v) for n,v in enumerate(cmd)])
        if variant:public_cmd='LAB_VARIANT='+variant+' '+public_cmd
        record={'name':name,'command':public_cmd,'exitCode':proc.returncode,'durationSeconds':round(time.monotonic()-start,3),'timedOut':timedout}
        if expected:record.update({'expectation':'expected-rejection','expectedExitCode':expected})
        records.append(record);save()
        if not binary:(proof/(name+'.txt')).write_text(sanitize(text))
        if timedout or proc.returncode!=expected:raise RuntimeError(f'STAGE_FAILED {name} exit={proc.returncode} timeout={timedout}')
        return out,text
    try:
        _,version=run('version',[args.go,'version'])
        if version.strip()!='go version go1.27.1 linux/amd64':raise RuntimeError('WRONG_TOOLCHAIN '+version.strip())
        run('tests',[args.go,'test','-p=1','-count=1','-v','-timeout=20s','./...'],timeout=60)
        run('race-clean',[args.go,'test','-p=1','-race','-count=1','-v','-timeout=20s','./...'],timeout=80)
        run('vet',[args.go,'vet','-p=1','./...'],timeout=45)
        for variant,test,marker in [('alias','TestPublishedPayload','OWNERSHIP_REJECT'),('cancel-join','TestCancellationIsNotJoin','CANCEL_JOIN_REJECT')]:
            _,txt=run('reject-'+variant,[args.go,'test','-p=1','-count=1','-run','^'+test+'$','-v','-timeout=20s','.'],expected=1,variant=variant)
            if not target_rejection(1,txt,test,marker):raise RuntimeError('WRONG_REJECTION '+variant)
        _,txt=run('reject-race',[args.go,'test','-p=1','-race','-count=1','-run','^TestRaceFixture$','-v','-timeout=20s','.'],expected=1,variant='race')
        if not target_rejection(1,txt,'TestRaceFixture','WARNING: DATA RACE') or 'RACE_FIXTURE_JOINED' not in txt:raise RuntimeError('RACE_NOT_DEMONSTRATED')
        executable=private/'diagnose'
        run('build',[args.go,'build','-p=1','-buildvcs=false','-trimpath','-o',str(executable),'./cmd/diagnose'],timeout=60)
        summaries={}
        for scenario in ['cpu','channel','network','backlog']:
            outdir=private/scenario
            run('run-'+scenario,[str(executable),'-scenario',scenario,'-out',str(outdir)],timeout=10)
            data=json.loads((outdir/'summary.json').read_text())
            if data['status']!='pass' or data['started']!=data['joined'] or data['completed']!=data['started']:raise RuntimeError('WORKER_ACCOUNTING '+scenario)
            if scenario=='network' and (data['networkBytes']!=1 or data['blockedObserved']!=1):raise RuntimeError('NETWORK_EVIDENCE')
            if scenario=='backlog' and (data['activeAtSnapshot']!=2 or data['waitingAtSnapshot']!=22):raise RuntimeError('BACKLOG_EVIDENCE')
            summaries[scenario]=data
            (proof/(scenario+'-summary.json')).write_text(json.dumps(data,indent=2)+'\n')
            (proof/(scenario+'-goroutines.txt')).write_text(sanitize((outdir/'goroutines.txt').read_text()))
            _,cpu=run(scenario+'-cpu-top',[args.go,'tool','pprof','-top','-nodecount=50',str(outdir/'cpu.pprof')])
            if scenario=='cpu' and 'main.cpuWork' not in cpu:raise RuntimeError('CPU_PROFILE_MISSING_WORKER')
            if scenario!='cpu':
                kind='net' if scenario=='network' else 'sync'
                data,_=run(scenario+'-trace-'+kind,[args.go,'tool','trace','-pprof='+kind,str(outdir/'trace.out')],binary=True)
                derived=outdir/(kind+'.pprof');derived.write_bytes(data)
                _,top=run(scenario+'-trace-top',[args.go,'tool','pprof','-top','-nodecount=50',str(derived)])
                target={'network':'main.networkWait','channel':'main.channelWait','backlog':'main.queuedWork'}[scenario]
                if target not in top:raise RuntimeError('TRACE_PROFILE_MISSING_WORKER '+scenario)
                _,block=run(scenario+'-block-top',[args.go,'tool','pprof','-top','-nodecount=50',str(outdir/'block.pprof')])
                if scenario in {'channel','backlog'} and target not in block:raise RuntimeError('BLOCK_PROFILE_MISSING_WORKER '+scenario)
            artifact_rows=[]
            for f in sorted(outdir.iterdir()):
                artifact_rows.append({'file':f.name,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size})
            (proof/(scenario+'-raw-artifact-hashes.json')).write_text(json.dumps(artifact_rows,indent=2)+'\n')
        outdir=private/'worker-error'
        run('reject-worker-error',[str(executable),'-scenario','network','-out',str(outdir),'-fail-worker'],expected=1,timeout=10)
        bad=json.loads((outdir/'summary.json').read_text())
        if not (bad['status']=='fail' and bad['started']==bad['joined']==1 and bad['completed']==0 and 'WORKER_ERROR' in bad['error'] and 'EOF' in bad['error']):raise RuntimeError('WRONG_WORKER_REJECTION')
        (proof/'worker-error-summary.json').write_text(json.dumps(bad,indent=2)+'\n')
        (proof/'verifier-regressions.json').write_text(json.dumps(verifier_regressions(),indent=2)+'\n')
        (proof/'result.json').write_text(json.dumps({'status':'pass','version':version.strip(),'scenarios':summaries,'checks':['normal tests','race clean for executed paths','vet','alias exact rejection','cancel-join exact rejection','actual race diagnostic','real CPU/channel/TCP/backlog profile and trace','worker error propagated','verifier rejection classification'],'limitations':['Finite Linux amd64 samples, not fairness or production throughput guarantees','No external network, HTTP load, C calls, disk IO or container scheduling tests','Raw profiles retained privately; source ZIP contains sanitized text observations and hashes only']},indent=2)+'\n')
        print('PASS: fixed Go tests, exact rejections and four finite diagnostic scenarios')
    except Exception as e:
        (proof/'result.json').write_text(json.dumps({'status':'fail','error':str(e)},indent=2)+'\n')
        print(str(e),file=sys.stderr);return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
