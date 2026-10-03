#!/usr/bin/env python3
"""Reviewed public GitHub runner only. Owns exactly one bounded MySQL project."""
from __future__ import annotations
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from safety import ci_identity, safe_path, secure_read, verify_sources, validate_mode
ROOT=safe_path(Path(__file__).absolute().parent)
LIMIT=1024*1024

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def source_check():
    return verify_sources(ROOT)

def child_limits():
    resource.setrlimit(resource.RLIMIT_FSIZE,(LIMIT,LIMIT))

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or os.environ.get('RUNNER_OS')!='Linux':
        print('NOT_RUN: use the reviewed public Ubuntu PR runner',file=sys.stderr)
        return 64
    identity=ci_identity()
    manifest_sha=source_check()
    workflow_path=ROOT.parents[1]/'.github/workflows/mysql-mechanisms-lab.yml'
    workflow_sha=hashlib.sha256(secure_read(workflow_path,65536)).hexdigest()
    owner=uuid.uuid4().hex
    project='ks-mechanisms-'+owner
    results=ROOT/'results'
    results.mkdir(exist_ok=False) # A new checkout prevents stale or mixed evidence.
    out=results/owner
    out.mkdir()
    write_json(results/'index.json',{'owner':owner,'relative_run':owner})
    started=time.monotonic()
    env=os.environ.copy()
    env['MECHANISMS_OWNER']=owner
    env['COMPOSE_DISABLE_ENV_FILE']='true'
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['DOCKER_HOST']='unix:///var/run/docker.sock'
    for key in ('DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'):
        env.pop(key,None)
    compose=['docker','compose','--project-name',project,'-f',str(ROOT/'compose.yaml')]
    report={'status':'NOT_RUN','source_manifest_sha256':manifest_sha,'owner':owner,'project':project,'modes':[],'workflow_path':'.github/workflows/mysql-mechanisms-lab.yml','workflow_sha256':workflow_sha,**identity}
    command_records=[]
    def command(label, argv, timeout, check=True, cleanup=False):
        if not cleanup:
            remaining=420-(time.monotonic()-started)
            if remaining<=0: raise TimeoutError('main run budget exhausted')
            timeout=min(timeout,remaining)
        normalized_argv=[('<python3>' if value==sys.executable else value.replace(str(ROOT),'<lab-root>')) for value in argv]
        log=out/(label+'.log')
        record={'label':label,'argv':normalized_argv,'argv_sha256':hashlib.sha256(json.dumps(normalized_argv,separators=(',',':')).encode()).hexdigest(),
                'timeout_seconds':round(timeout,3),'exit_code':127,'actual_exit_code':None,'outcome':'launch_error','log_sha256':None}
        command_records.append(record)
        proc=None
        failure=None
        try:
            with log.open('wb') as f:
                try:
                    proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=f,stderr=subprocess.STDOUT,
                                          start_new_session=True,preexec_fn=child_limits)
                    record['exit_code']=proc.wait(timeout=timeout)
                    record['outcome']='normal_exit'
                except subprocess.TimeoutExpired:
                    record.update(exit_code=124,outcome='timeout')
                except BaseException as error:
                    record.update(exit_code=130 if isinstance(error,KeyboardInterrupt) else 127,
                                  outcome='interrupted' if isinstance(error,KeyboardInterrupt) else 'launch_error')
                    failure=error
                finally:
                    if proc is not None and proc.poll() is None:
                        try:
                            os.killpg(proc.pid,signal.SIGTERM)
                            try:proc.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                os.killpg(proc.pid,signal.SIGKILL)
                                proc.wait(timeout=3)
                        except BaseException as error:
                            record.update(exit_code=125,outcome='termination_error')
                            failure=error
                    if proc is not None:record['actual_exit_code']=proc.returncode
        finally:
            raw=secure_read(log,LIMIT) if log.is_file() else b''
            if len(raw)>=LIMIT:record.update(exit_code=125,outcome='output_limit')
            text=raw.decode('utf-8','replace').replace(str(ROOT),'<lab-root>')
            if failure:text+='\nCOMMAND_FAILURE '+type(failure).__name__+'\n'
            # Store and hash the same normalized bytes; no environment dump.
            data=text.encode()
            log.write_bytes(data)
            record['log_sha256']=hashlib.sha256(data).hexdigest()
        if failure:raise failure
        if check and record['exit_code']:raise RuntimeError('bounded command failed: '+label)
        return record['exit_code'],text.strip()
    def interrupted(signum,frame):
        raise KeyboardInterrupt('termination requested')
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGINT,interrupted)
    code=1
    try:
        command('docker-version',['docker','version','--format','{{.Server.Version}}'],15)
        command('compose-version',['docker','compose','version','--short'],15)
        _,commit=command('checkout-commit',['git','rev-parse','HEAD'],10)
        if not re.fullmatch('[0-9a-f]{40}',commit):
            raise RuntimeError('invalid checkout commit')
        report['checkout_commit']=commit
        command('start',compose+['up','-d','--wait','--wait-timeout','180'],240)
        _,container=command('container-id',compose+['ps','-q','mysql'],15)
        if not re.fullmatch('[a-f0-9]{64}',container):
            raise RuntimeError('expected exactly one full container ID')
        _,label=command('owner-label',['docker','inspect','--format','{{index .Config.Labels "knowledge-station.mechanisms-owner"}}',container],15)
        if label!=owner:
            raise RuntimeError('owner mismatch')
        _,image=command('image-id',['docker','inspect','--format','{{.Image}}',container],15)
        if not re.fullmatch('sha256:[a-f0-9]{64}',image):
            raise RuntimeError('invalid image identity')
        _,digests=command('image-digests',['docker','image','inspect','--format','{{json .RepoDigests}}',image],15)
        report['image']={'requested':'mysql:8.4.7','id':image,'repo_digests':json.loads(digests)}
        _,platform=command('image-platform',['docker','image','inspect','--format','{{.Os}}/{{.Architecture}}',image],15)
        if platform not in ('linux/amd64','linux/arm64'):
            raise RuntimeError('unexpected image platform')
        report['image']['platform']=platform
        if not report['image']['repo_digests']:
            raise RuntimeError('image repository digest missing')
        modes=[('baseline',0,None),('mutant-missing-tenant',42,'index.ordinary-covering.rows'),
               ('mutant-rc-for-rr',42,'rr.repeat'),('mutant-stale-write',42,'own.mixed-view'),
               ('control-sql-error',43,None)]
        for mode,expected_code,assertion in modes:
            rc,_=command(mode,[sys.executable,'-B','cases.py','--container',container,'--owner',owner,'--mode',mode,'--out',str(out/mode)],90,check=False)
            result_file=out/mode/'result.json'
            if not result_file.is_file() or result_file.is_symlink():
                raise RuntimeError('case process has no trusted result')
            result=json.loads(result_file.read_text())
            report['modes'].append(result)
            validate_mode(result,mode)
            if rc!=expected_code or result.get('exit_code')!=rc or not result.get('sessions_clean'):
                raise RuntimeError('mode outcome/cleanup mismatch: '+mode)
            if assertion and (result.get('status')!='SEMANTIC_MISMATCH' or result.get('assertion')!=assertion or result.get('expected')==result.get('observed')):
                raise RuntimeError('mutation did not reach the required semantic assertion')
            if mode=='baseline' and result.get('status')!='PASS':
                raise RuntimeError('baseline not pass')
            if mode=='control-sql-error' and (result.get('status')!='SQL_FAILURE' or 'ERROR 1064 ' not in result.get('error','')):
                raise RuntimeError('syntax control not classified as SQL failure')
        report['status']='PASS_PENDING_CLEANUP'
        code=0
    except BaseException as error:
        report['status']='FAIL'
        report['error_type']=type(error).__name__
        report['error']=str(error).replace(str(ROOT),'<lab-root>')[:1024]
    finally:
        signal.signal(signal.SIGTERM,signal.SIG_IGN)
        signal.signal(signal.SIGINT,signal.SIG_IGN)
        clean=True
        # Each command is scoped to this random project; never prune.
        for name,argv in [('service-log',compose+['logs','--no-color','--tail','200']),
                          ('cleanup',compose+['down','--volumes','--timeout','10'])]:
            try:
                rc,_=command(name,argv,20 if name=='service-log' else 40,check=False,cleanup=True)
                clean=clean and rc==0
            except BaseException:
                clean=False
        for kind,argv in [('containers',['docker','ps','-aq']),('volumes',['docker','volume','ls','-q']),('networks',['docker','network','ls','-q'])]:
            try:
                rc,text=command('remaining-'+kind,argv+['--filter','label=com.docker.compose.project='+project],10,check=False,cleanup=True)
                clean=clean and rc==0 and text==''
            except BaseException:
                clean=False
        report['cleanup_ok']=clean
        report['commands']=command_records
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        code=code if clean else 1
        report['status']='PASS' if code==0 else 'FAIL'
        report['exit_code']=code
        write_json(out/'result.json',report)
        print(json.dumps({'relative_run':owner,'status':report['status'],'exit_code':code}))
    return code
if __name__=='__main__':
    sys.exit(main())
