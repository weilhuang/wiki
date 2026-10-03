#!/usr/bin/env python3
"""Fresh dedicated CI artifacts; validate/read immutable bytes before writing."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from safety import (CLEANUP_COMMANDS, MODE_EXPECTED, TOP_COMMANDS, ci_identity, expected_command_argv,
                    read_json, require, safe_path, secure_read, validate_mode, validate_trace, verify_sources)
from trace_contract import validate_event
ROOT=safe_path(Path(__file__).absolute().parent)
MAX_BYTES=8*1024*1024

def sha(data):return hashlib.sha256(data).hexdigest()

def write_tree(dest,blobs):
    # Open every ancestor without following links, then create our one new dir.
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in dest.parent.parts[1:]:
            nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=nxt
        os.mkdir(dest.name,mode=0o700,dir_fd=fd)
        target_fd=os.open(dest.name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            for name,data in blobs.items():
                parts=Path(name).parts
                parent_fd=os.dup(target_fd)
                try:
                    for part in parts[:-1]:
                        try:os.mkdir(part,mode=0o700,dir_fd=parent_fd)
                        except FileExistsError:pass
                        nxt=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent_fd)
                        os.close(parent_fd);parent_fd=nxt
                    file_fd=os.open(parts[-1],os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent_fd)
                    with os.fdopen(file_fd,'wb') as stream:stream.write(data)
                finally:os.close(parent_fd)
        finally:os.close(target_fd)
    finally:os.close(fd)
    actual={p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()}
    require(actual==set(blobs),'final artifact tree differs')
    for name,data in blobs.items():require(secure_read(dest/name,MAX_BYTES)==data,'final artifact bytes differ')

def main():
    require(len(sys.argv)==2,'one dedicated destination required')
    identity=ci_identity()
    temp=safe_path(os.environ.get('RUNNER_TEMP',''))
    require(temp.is_dir(),'runner temp missing')
    dest=safe_path(sys.argv[1])
    require(dest==temp/'mysql-mechanisms-evidence' and not dest.exists(),'destination must be fresh dedicated runner directory')
    manifest_sha=verify_sources(ROOT)
    info=read_json(ROOT/'results/index.json',1024)
    require(isinstance(info,dict) and set(info)=={'owner','relative_run'},'index schema')
    owner=info['owner']
    require(isinstance(owner,str) and re.fullmatch('[a-f0-9]{32}',owner) and info['relative_run']==owner,'index ownership')
    run=safe_path(ROOT/'results'/owner)
    require(run.is_dir(),'run directory missing')
    require({p.name for p in (ROOT/'results').iterdir()}=={'index.json',owner},'mixed result runs')
    blobs={}
    for p in run.rglob('*'):
        safe_path(p)
        rel=p.relative_to(run)
        if p.is_dir():
            require(len(rel.parts)==1 and rel.name in MODE_EXPECTED,'unexpected evidence directory')
            continue
        allowed=(len(rel.parts)==1 and (rel.name=='result.json' or rel.suffix=='.log' and rel.stem in TOP_COMMANDS)) or (len(rel.parts)==2 and rel.parts[0] in MODE_EXPECTED and rel.name in {'result.json','trace.jsonl'})
        require(allowed,'unexpected evidence file')
        limit=512*1024 if rel.name=='trace.jsonl' else 65536 if rel.suffix=='.json' else 1024*1024
        blobs[rel.as_posix()]=secure_read(p,limit)
    require(sum(map(len,blobs.values()))<=MAX_BYTES and len(blobs)<=40,'input artifact budget')
    result=json.loads(blobs['result.json'])
    allowed_root={'status','source_manifest_sha256','owner','project','modes',*identity,'workflow_path','workflow_sha256','checkout_commit','image','error','error_type','cleanup_ok','commands','elapsed_seconds','exit_code'}
    require(isinstance(result,dict) and set(result)<=allowed_root,'result schema')
    require(result.get('owner')==owner and result.get('project')=='ks-mechanisms-'+owner,'result owner/project')
    require(result.get('source_manifest_sha256')==manifest_sha,'source binding')
    require(all(result.get(k)==v for k,v in identity.items()),'CI identity binding')
    workflow=secure_read(ROOT.parents[1]/'.github/workflows/mysql-mechanisms-lab.yml',65536)
    require(result.get('workflow_path')=='.github/workflows/mysql-mechanisms-lab.yml' and result.get('workflow_sha256')==sha(workflow),'workflow source binding')
    status=result.get('status')
    require(status in {'PASS','FAIL'} and type(result.get('exit_code')) is int and (result['exit_code']==0)==(status=='PASS'),'result status/exit')
    commands=result.get('commands')
    require(isinstance(commands,list) and 1<=len(commands)<=len(TOP_COMMANDS),'command list missing')
    def succeeded(label):return any(isinstance(c,dict) and c.get('label')==label and c.get('exit_code')==0 and c.get('outcome')=='normal_exit' for c in commands)
    container=blobs.get('container-id.log',b'').decode().strip() if succeeded('container-id') else None
    image_id=blobs.get('image-id.log',b'').decode().strip() if succeeded('image-id') else None
    if container:require(re.fullmatch('[a-f0-9]{64}',container),'container identity shape')
    if image_id:require(re.fullmatch('sha256:[0-9a-f]{64}',image_id),'image identity shape')
    labels=[]
    for c in commands:
        require(isinstance(c,dict) and set(c)=={'label','argv','argv_sha256','timeout_seconds','exit_code','actual_exit_code','outcome','log_sha256'},'command schema')
        label=c['label']
        require(label in TOP_COMMANDS and label not in labels and type(c['exit_code']) is int,'command identity')
        require(c['argv']==expected_command_argv(label,owner,container,image_id),'unapproved command arguments')
        require(c['argv_sha256']==sha(json.dumps(c['argv'],separators=(',',':')).encode()),'command argv hash')
        require(type(c['timeout_seconds']) in (int,float) and 0<c['timeout_seconds']<=240,'command timeout')
        require(c['actual_exit_code'] is None or type(c['actual_exit_code']) is int,'actual command exit')
        require(c['outcome'] in {'normal_exit','launch_error','timeout','interrupted','output_limit','termination_error'},'command classification')
        require(label+'.log' in blobs and c['log_sha256']==sha(blobs[label+'.log']),'command log identity')
        if c['outcome']=='normal_exit':require(c['actual_exit_code']==c['exit_code'],'normal exit differs')
        labels.append(label)
    require({name for name in blobs if '/' not in name and name.endswith('.log')}=={label+'.log' for label in labels},'unrecorded command log')
    require(labels==sorted(labels,key=TOP_COMMANDS.index),'command order')
    require(type(result.get('cleanup_ok')) is bool,'cleanup flag missing')
    if result['cleanup_ok']:
        require(all(x in labels for x in CLEANUP_COMMANDS),'cleanup commands missing')
        require(all(c['exit_code']==0 and c['outcome']=='normal_exit' for c in commands if c['label'] in CLEANUP_COMMANDS),'cleanup exit mismatch')
        require(all(blobs['remaining-'+x+'.log'].strip()==b'' for x in ('containers','volumes','networks')),'owned resources remain')
    modes=result.get('modes')
    require(isinstance(modes,list) and len(modes)<=5,'mode list schema')
    seen=[]
    for mr in modes:
        require(isinstance(mr,dict) and set(mr)<={'mode','status','sessions_clean','exit_code','assertion','expected','observed','error','error_type','prior_status'},'mode schema')
        mode=mr.get('mode')
        require(mode in MODE_EXPECTED and mode not in seen,'mode identity')
        require(json.loads(blobs[mode+'/result.json'])==mr,'mode result differs from run summary')
        require(mode in labels and next(c['exit_code'] for c in commands if c['label']==mode)==mr.get('exit_code'),'mode exit binding')
        seen.append(mode)
    require(seen==list(MODE_EXPECTED)[:len(seen)],'mode order')
    require({name.split('/')[0] for name in blobs if '/' in name and name.endswith('/result.json')}==set(seen),'unbound mode result file')
    for name,data in blobs.items():
        if '/' in name:require(name.split('/')[0] in labels,'unstarted mode evidence')
        if name.endswith('trace.jsonl'):
            for n,line in enumerate(data.decode().splitlines(),1):
                e=json.loads(line)
                require(isinstance(e,dict) and e.get('sequence')==n,'diagnostic trace sequence')
                validate_event(e)
    if status=='PASS':
        require(result['cleanup_ok'] is True and labels==TOP_COMMANDS and seen==list(MODE_EXPECTED),'incomplete PASS evidence')
        commit=result.get('checkout_commit','')
        require(re.fullmatch('[0-9a-f]{40}',commit) and blobs['checkout-commit.log'].decode().strip()==commit,'checkout log binding')
        actual_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,timeout=10).strip()
        require(actual_commit==commit,'checkout no longer matches run')
        require(blobs['owner-label.log'].decode().strip()==owner,'label log binding')
        image=result.get('image',{})
        require(set(image)=={'requested','id','repo_digests','platform'} and image['requested']=='mysql:8.4.7' and image['id']==image_id,'image identity')
        digests=image['repo_digests']
        require(isinstance(digests,list) and digests and all(re.fullmatch(r'(?:docker.io/library/)?mysql@sha256:[0-9a-f]{64}',d) for d in digests),'official image digest')
        require(json.loads(blobs['image-digests.log'])==digests and blobs['image-platform.log'].decode().strip()==image['platform'] and image['platform'] in ('linux/amd64','linux/arm64'),'image metadata binding')
        for c in commands:
            expected=MODE_EXPECTED[c['label']][0] if c['label'] in MODE_EXPECTED else 0
            require(c['exit_code']==expected and c['outcome']=='normal_exit','PASS command exit mismatch')
        for mr in modes:
            mode=mr['mode']
            validate_mode(mr,mode)
            # secure_read rejects any link swap since the first snapshot; equality
            # ensures validation and upload refer to the same captured bytes.
            require(secure_read(run/mode/'trace.jsonl',512*1024)==blobs[mode+'/trace.jsonl'],'trace changed during collection')
            validate_trace(blobs[mode+'/trace.jsonl'],mode,mr)
        classification='VALIDATED_PASS_EVIDENCE'
    else:classification='VALIDATED_FAILURE_DIAGNOSTIC'
    blobs['source-manifest.json']=secure_read(ROOT/'source-manifest.json',65536)
    require(sha(blobs['source-manifest.json'])==manifest_sha,'source manifest changed during collection')
    hashes=[{'path':name,'sha256':sha(data),'bytes':len(data)} for name,data in sorted(blobs.items())]
    manifest={'classification':classification,'source_manifest_sha256':manifest_sha,'workflow_sha256':sha(workflow),'files':hashes,'total_bytes':0,'file_count':len(blobs)+1}
    for _ in range(5):
        encoded=(json.dumps(manifest,indent=2)+'\n').encode()
        total=sum(map(len,blobs.values()))+len(encoded)
        if manifest['total_bytes']==total:break
        manifest['total_bytes']=total
    encoded=(json.dumps(manifest,indent=2)+'\n').encode()
    blobs['artifact-manifest.json']=encoded
    require(len(blobs)<=40 and sum(map(len,blobs.values()))<=MAX_BYTES,'final artifact budget including manifests')
    write_tree(dest,blobs)
    print(json.dumps({'upload_ready':True,'classification':classification,'run_status':status,'files':len(blobs),'bytes':sum(map(len,blobs.values()))}))
if __name__=='__main__':main()
