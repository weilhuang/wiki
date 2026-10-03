"""Fail-closed filesystem, source identity and report structure checks."""
import hashlib
import json
import os
import re
import stat
from pathlib import Path
MODE_EXPECTED={
    'baseline':(0,'PASS',None),
    'mutant-missing-tenant':(42,'SEMANTIC_MISMATCH','index.ordinary-covering.rows'),
    'mutant-rc-for-rr':(42,'SEMANTIC_MISMATCH','rr.repeat'),
    'mutant-stale-write':(42,'SEMANTIC_MISMATCH','own.mixed-view'),
    'control-sql-error':(43,'SQL_FAILURE',None),
}
CASE_NAMES=['index_cases','begin_is_not_snapshot','rr_retention','rc_refresh','current_and_own','lock_handoff']
TOP_COMMANDS=['docker-version','compose-version','checkout-commit','start','container-id','owner-label','image-id','image-digests','image-platform',*MODE_EXPECTED,'service-log','cleanup','remaining-containers','remaining-volumes','remaining-networks']
CLEANUP_COMMANDS=TOP_COMMANDS[-5:]

def require(ok,message):
    if not ok: raise RuntimeError(message)

def safe_path(value):
    raw=os.fspath(value)
    require(raw.startswith('/') and not any(x in ('.','..') for x in raw.split('/')),'absolute normalized path required')
    p=Path(raw)
    for item in [*reversed(p.parents),p]:
        require(not item.is_symlink(),'symlink ancestor rejected')
    return p

def secure_read(path,limit):
    path=safe_path(path)
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd)
            fd=next_fd
        file_fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        try:
            info=os.fstat(file_fd)
            require(stat.S_ISREG(info.st_mode) and info.st_size<=limit,'missing or oversized regular file')
            with os.fdopen(os.dup(file_fd),'rb') as stream: data=stream.read(limit+1)
            require(len(data)<=limit,'read size budget exceeded')
            return data
        finally:os.close(file_fd)
    finally:os.close(fd)

def read_json(path,limit=65536):
    return json.loads(secure_read(path,limit))

def verify_sources(root):
    root=safe_path(root)
    paths=list(root.rglob('*'))
    require(not any(p.is_symlink() for p in paths),'source symbolic link rejected')
    manifest=read_json(root/'source-manifest.json')
    entries=manifest.get('files')
    require(isinstance(entries,list) and 1<=len(entries)<=32,'invalid source manifest')
    expected={}
    for e in entries:
        require(isinstance(e,dict) and set(e)=={'path','sha256'},'invalid source entry')
        path=e['path']
        require(isinstance(path,str) and not path.startswith('/') and not any(x in ('','.','..') for x in path.split('/')),'invalid source path')
        require(path not in expected and re.fullmatch('[0-9a-f]{64}',e['sha256']),'duplicate or invalid hash')
        expected[path]=e['sha256']
    actual={}
    for p in paths:
        rel=p.relative_to(root)
        if p.is_file() and rel.parts[0]!='results' and p.name!='source-manifest.json':
            require(p.stat().st_size<=256*1024,'source size limit')
            actual[rel.as_posix()]=hashlib.sha256(secure_read(p,256*1024)).hexdigest()
    require(actual==expected,'exact source tree mismatch')
    return hashlib.sha256(secure_read(root/'source-manifest.json',65536)).hexdigest()

def ci_identity():
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_OS')=='Linux','reviewed Linux CI required')
    data={}
    for name,pattern in [('GITHUB_RUN_ID','[1-9][0-9]{0,19}'),('GITHUB_RUN_ATTEMPT','[1-9][0-9]{0,9}'),('PR_HEAD_SHA','[0-9a-f]{40}'),('PR_BASE_SHA','[0-9a-f]{40}')]:
        value=os.environ.get(name,'')
        require(re.fullmatch(pattern,value) is not None,'missing or malformed CI identity: '+name)
        data[name.lower()]=value
    for name,pattern in [('GITHUB_REPOSITORY',r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'),('GITHUB_REF',r'refs/pull/[1-9][0-9]*/merge'),('GITHUB_EVENT_NAME',r'pull_request')]:
        value=os.environ.get(name,'')
        require(re.fullmatch(pattern,value) is not None,'missing CI context: '+name)
        data[name.lower()]=value
    workflow_ref=os.environ.get('GITHUB_WORKFLOW_REF','')
    require(workflow_ref==data['github_repository']+'/.github/workflows/mysql-mechanisms-lab.yml@'+data['github_ref'],'workflow ref binding')
    data['github_workflow_ref']=workflow_ref
    return data

def validate_mode(result,mode):
    code,status,assertion=MODE_EXPECTED[mode]
    require(result.get('mode')==mode and result.get('exit_code')==code and result.get('status')==status and result.get('sessions_clean') is True,'mode result mismatch')
    if assertion:
        require(result.get('assertion')==assertion and isinstance(result.get('expected'),list) and isinstance(result.get('observed'),list) and result['expected']!=result['observed'],'wrong mutation failure')
    if mode=='control-sql-error':
        require(isinstance(result.get('error'),str) and re.match(r'^ERROR 1064 \(',result['error']) is not None,'not the deliberate syntax failure')

def validate_trace(path,mode,result):
    from trace_contract import validate_event, validate_assertion_sequence, normalized, required_assertions
    raw=path if isinstance(path,bytes) else secure_read(path,512*1024)
    require(len(raw)<=512*1024,'trace size budget')
    require(bool(raw),'empty trace')
    events=[]
    for index,line in enumerate(raw.decode().splitlines(),1):
        require(len(line.encode())<=256*1024,'trace line oversized')
        event=json.loads(line)
        require(isinstance(event,dict) and event.get('sequence')==index and isinstance(event.get('kind'),str),'trace sequence/schema')
        validate_event(event)
        events.append(event)
    allowed={'sql_send','sql_result','session_open','server_identity','session_close','assertion','case_begin','case_pass','statistics','index_statistics','explain','explain_analyze','barrier','cleanup_error'}
    require(all(e['kind'] in allowed for e in events),'unknown trace event')
    opens=[e for e in events if e['kind']=='session_open']
    require({e.get('session') for e in opens}=={'observer','A','B'} and len(opens)==3,'missing distinct sessions')
    require(all(re.fullmatch('[1-9][0-9]*',str(e.get('connection_id',''))) for e in opens) and len({e['connection_id'] for e in opens})==3,'invalid connection IDs')
    closes=[e for e in events if e['kind']=='session_close']
    require(len(closes)==3 and {e.get('session') for e in closes}=={'observer','A','B'} and all(e.get('clean') is True and e.get('exit_code')==0 for e in closes),'unclean session evidence')
    identities=[e for e in events if e['kind']=='server_identity']
    require(len(identities)==1 and len(identities[0].get('rows',[]))==1 and identities[0]['rows'][0].startswith('8.4.7\t'),'server identity missing')
    pending={}
    last={}
    connection_ids={e['session']:e['connection_id'] for e in opens}
    sql_errors=[]
    plan_queries={key.removeprefix('index.').removesuffix('.rows'):sql for key,session,sql,expected in required_assertions('baseline') if key.startswith('index.') and key.endswith('.rows')}
    for e in events:
        if e['kind']=='sql_send':
            s=e.get('session')
            require(s in {'observer','A','B'} and s not in pending and isinstance(e.get('sql'),str),'invalid SQL request sequence')
            pending[s]=e['sql']
        elif e['kind']=='sql_result':
            s=e.get('session')
            require(s in pending and isinstance(e.get('rows'),list) and all(isinstance(x,str) for x in e['rows']),'SQL response without request')
            sql=pending.pop(s)
            require(e.get('connection_id')==connection_ids[s] or e.get('connection_id') is None and sql=='SELECT CONNECTION_ID()' and e['rows']==[connection_ids[s]],'response connection identity')
            last[s]=(sql,e['rows'])
            sql_errors.extend(x for x in e['rows'] if x.startswith('ERROR '))
        elif e['kind']=='explain':
            name=e.get('query')
            require(name in plan_queries,'unknown plan query')
            expected_sql=plan_queries[name]
            if mode=='mutant-missing-tenant' and name=='ordinary-covering':expected_sql=expected_sql.replace('tenant_id = 1 AND ','')
            previous=last.get('observer')
            require(previous and normalized(previous[0])==normalized('EXPLAIN FORMAT=JSON '+expected_sql) and json.loads('\n'.join(previous[1]))==e['plan'],'plan not bound to SQL result')
            def has_table(node):
                if isinstance(node,list):return any(has_table(x) for x in node)
                if not isinstance(node,dict):return False
                return node.get('table_name')=='orders' and node.get('access_type') in {'ALL','index','range','ref','eq_ref','const','ref_or_null','index_merge'} or any(has_table(x) for x in node.values())
            require(has_table(e['plan']),'plan missing orders table access')
            require(e['constrained']==('FORCE INDEX' in expected_sql),'plan constraint label')
        elif e['kind']=='explain_analyze':
            previous=last.get('observer')
            require(e['query']=='constrained-covering' and previous and normalized(previous[0])==normalized('EXPLAIN ANALYZE '+plan_queries['constrained-covering']) and previous[1]==e['rows'],'ANALYZE not bound to actual SQL response')
        elif e['kind']=='statistics':
            require(last.get('observer')==('ANALYZE TABLE orders',e['rows']) and e['rows']==['mechanisms_lab.orders\tanalyze\tstatus\tOK'],'statistics response mismatch')
        elif e['kind']=='index_statistics':
            require(last.get('observer')==('SHOW INDEX FROM orders',e['rows']) and len(e['rows'])>=4,'index statistics response missing')
        elif e['kind']=='barrier':
            if e['name']=='B_waits_for_A_engine_lock':
                require(len(e['rows'])==1 and re.fullmatch('[1-9][0-9]*',e['rows'][0]) is not None,'lock barrier count must be positive')
                require(e['waiting_connection']==connection_ids['B'] and e['blocking_connection']==connection_ids['A'],'lock barrier connections')
                require('B' in pending and pending['B'].startswith('UPDATE inventory SET available=available-3'),'B must have an in-flight write')
                require(last.get('observer',(None,None))[1]==e['rows'] and 'performance_schema.data_lock_waits' in last['observer'][0],'lock barrier not bound to server response')
            elif e['name']=='B_commit_acknowledged':require(last.get('B')==('COMMIT',[]),'commit barrier has no ack')
            else:require(last.get('A')==('SELECT sku, available FROM inventory ORDER BY sku',['1\t10','2\t20']),'first-read barrier has no ack')
    require(not pending,'unfinished SQL frame')
    if mode=='control-sql-error':
        require(len(sql_errors)==1 and sql_errors[0].startswith('ERROR 1064 '),'wrong SQL control frame')
    else:
        require(not sql_errors,'unexpected SQL errors')
    mismatches=[e for e in events if e['kind']=='assertion' and e.get('expected')!=e.get('observed')]
    expected_assertion=MODE_EXPECTED[mode][2]
    if expected_assertion:
        require(len(mismatches)==1 and mismatches[0].get('assertion')==expected_assertion and mismatches[0].get('expected')==result['expected'] and mismatches[0].get('observed')==result['observed'],'mutation trace mismatch')
    else:
        require(not mismatches,'unexpected assertion mismatch')
    begun={'baseline':CASE_NAMES,'mutant-missing-tenant':CASE_NAMES[:1],'mutant-rc-for-rr':CASE_NAMES[:3],'mutant-stale-write':CASE_NAMES[:5],'control-sql-error':[]}[mode]
    passed=begun if mode=='baseline' else begun[:-1]
    require([e.get('case') for e in events if e['kind']=='case_begin']==begun and [e.get('case') for e in events if e['kind']=='case_pass']==passed,'case stage order')
    if mode=='baseline':
        require([e.get('case') for e in events if e['kind']=='case_pass']==CASE_NAMES,'baseline case evidence incomplete')
        require(any(e['kind']=='barrier' and e.get('name')=='B_waits_for_A_engine_lock' and e.get('rows')!=['0'] for e in events),'missing server lock barrier')
        require(len([e for e in events if e['kind']=='explain'])==6,'missing plans')
        require(all(isinstance(e.get('plan'),dict) and 'query_block' in e['plan'] for e in events if e['kind']=='explain'),'malformed plan')
        require(any(e['kind']=='explain_analyze' and any('actual time=' in x and 'loops=' in x for x in e.get('rows',[])) for e in events),'missing actual ANALYZE')
    validate_assertion_sequence(events,mode,result)
    from protocol_contract import validate_protocol
    validate_protocol(events,mode)
    return events

def expected_command_argv(label,owner,container=None,image=None):
    compose=['docker','compose','--project-name','ks-mechanisms-'+owner,'-f','<lab-root>/compose.yaml']
    specs={
        'docker-version':['docker','version','--format','{{.Server.Version}}'],
        'compose-version':['docker','compose','version','--short'],
        'checkout-commit':['git','rev-parse','HEAD'],
        'start':compose+['up','-d','--wait','--wait-timeout','180'],
        'container-id':compose+['ps','-q','mysql'],
        'owner-label':['docker','inspect','--format','{{index .Config.Labels "knowledge-station.mechanisms-owner"}}',container],
        'image-id':['docker','inspect','--format','{{.Image}}',container],
        'image-digests':['docker','image','inspect','--format','{{json .RepoDigests}}',image],
        'image-platform':['docker','image','inspect','--format','{{.Os}}/{{.Architecture}}',image],
        'service-log':compose+['logs','--no-color','--tail','200'],
        'cleanup':compose+['down','--volumes','--timeout','10'],
    }
    for mode in MODE_EXPECTED:
        specs[mode]=['<python3>','-B','cases.py','--container',container,'--owner',owner,'--mode',mode,'--out',f'<lab-root>/results/{owner}/{mode}']
    for kind,argv in [('containers',['docker','ps','-aq']),('volumes',['docker','volume','ls','-q']),('networks',['docker','network','ls','-q'])]:
        specs['remaining-'+kind]=argv+['--filter','label=com.docker.compose.project=ks-mechanisms-'+owner]
    return specs[label]
