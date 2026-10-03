"""Independent expected observations for the finite SQL cases, not a DB model."""
import re
from safety import require

READ='SELECT sku, available FROM inventory ORDER BY sku'
CURRENT='UPDATE inventory SET available = available - 2 WHERE sku = 1 AND available >= 2; SELECT ROW_COUNT();'

def normalized(sql): return re.sub(r'\s+',' ',sql.strip()).rstrip(';')

def required_assertions(mode):
    seq=[]
    def add(key,session,sql,expected): seq.append((key,session,normalized(sql),expected))
    def reset(): add('reset.rows','observer',READ,['1\t10','2\t20'])
    def changed(first=11,second=21): add('B.changed-two','B',f'UPDATE inventory SET available=CASE sku WHEN 1 THEN {first} ELSE {second} END; SELECT ROW_COUNT()',['2'])
    add('index.fixture-count','observer','SELECT COUNT(*) FROM orders',['36'])
    for name,columns,forced in [('ordinary-covering','order_id, created_at',False),('constrained-covering','order_id, created_at',True),('constrained-noncovering','order_id, created_at, note',True)]:
        sql=f'SELECT {columns} FROM orders'+(' FORCE INDEX (idx_tenant_state_created)' if forced else '')+' WHERE tenant_id = 1 AND state = 1 AND created_at >= 3 ORDER BY created_at, order_id'
        if mode=='mutant-missing-tenant' and name=='ordinary-covering': sql=sql.replace('tenant_id = 1 AND ','')
        add('index.'+name+'.rows','observer',sql,[f'{1100+d}\t{d}'+(f'\tt1-s1-d{d}' if name=='constrained-noncovering' else '') for d in (3,4,5,6)])
        if mode=='mutant-missing-tenant': return seq
    add('index.range-residual.rows','observer','SELECT order_id FROM orders FORCE INDEX (idx_tenant_state_created) WHERE tenant_id=1 AND state>=1 AND created_at=3 ORDER BY order_id',['1103','1203'])
    add('index.missing-left-prefix.rows','observer','SELECT order_id FROM orders WHERE state=1 AND created_at=3 ORDER BY order_id',['1103','2103'])
    add('index.cross-state-sort.rows','observer','SELECT order_id,created_at FROM orders WHERE tenant_id=1 AND state>=1 ORDER BY created_at,order_id',[f'{1000+s*100+d}\t{d}' for d in range(1,7) for s in (1,2)])
    reset();changed();add('begin.first-read-after-B','A',READ,['1\t11','2\t21'])
    reset();changed();add('explicit-snapshot.before-B','A',READ,['1\t10','2\t20'])
    reset();add('rr.first','A',READ,['1\t10','2\t20']);changed();add('rr.repeat','A',READ,['1\t10','2\t20'])
    if mode=='mutant-rc-for-rr':return seq
    add('rr.after-commit','A',READ,['1\t11','2\t21'])
    reset();add('rc.first','A',READ,['1\t10','2\t20']);changed();add('rc.refresh','A',READ,['1\t11','2\t21'])
    reset();add('own.initial-snapshot','A',READ,['1\t10','2\t20']);changed(7,17)
    add('current.locking-value','A','SELECT available FROM inventory WHERE sku=1 FOR UPDATE',['7'])
    add('current.does-not-refresh-view','A',READ,['1\t10','2\t20'])
    add('own.affected','A',CURRENT.replace('available - 2','10 - 2') if mode=='mutant-stale-write' else CURRENT,['1'])
    add('own.mixed-view','A',READ,['1\t5','2\t20'])
    if mode=='mutant-stale-write':return seq
    add('own.uncommitted-hidden','B',READ,['1\t7','2\t17'])
    add('own.rollback-restores','observer',READ,['1\t7','2\t17'])
    add('own.commit-affected','A',CURRENT,['1'])
    add('own.commit-visible','B',READ,['1\t5','2\t17'])
    reset();add('lock.A-value','A','SELECT available FROM inventory WHERE sku=1 FOR UPDATE',['10'])
    add('lock.A-affected','A','UPDATE inventory SET available=available-2 WHERE sku=1; SELECT ROW_COUNT()',['1'])
    add('lock.B-affected-after-release','B','UPDATE inventory SET available=available-3 WHERE sku=1 AND available>=3; SELECT ROW_COUNT()',['1'])
    add('lock.B-current-after-release','B','SELECT available FROM inventory WHERE sku=1',['5'])
    add('lock.B-rollback','observer',READ,['1\t8','2\t20'])
    return seq

SCHEMAS={
'sql_send':{'session','sql'},'sql_result':{'session','connection_id','rows'},
'session_open':{'session','connection_id'},'server_identity':{'rows'},
'session_close':{'session','exit_code','clean'},'assertion':{'assertion','expected','observed'},
'case_begin':{'case'},'case_pass':{'case'},'statistics':{'rows'},'index_statistics':{'rows'},
'explain':{'query','constrained','plan'},'explain_analyze':{'query','rows'},
'cleanup_error':{'session','error'},
}

def validate_event(event):
    kind=event.get('kind')
    if kind=='barrier':
        name=event.get('name')
        fields={'name'} if name in {'A_first_consistent_read_acknowledged','B_commit_acknowledged'} else {'name','rows','waiting_connection','blocking_connection'}
        require(name in {'A_first_consistent_read_acknowledged','B_commit_acknowledged','B_waits_for_A_engine_lock'},'unknown barrier')
    else:
        require(kind in SCHEMAS,'unknown trace event')
        fields=SCHEMAS[kind]
    require(set(event)==fields|{'sequence','kind'},'trace event field schema')
    for key in ('rows','expected','observed'):
        if key in event:require(isinstance(event[key],list) and all(isinstance(x,str) for x in event[key]),'trace row schema')
    if 'session' in event:require(event['session'] in {'observer','A','B'},'trace session name')

def validate_assertion_sequence(events,mode,result):
    if mode=='control-sql-error':
        require(not any(e['kind']=='assertion' for e in events),'syntax control has business assertion')
        require(any(e['kind']=='sql_send' and e['sql']=='SELEC available FROM inventory' for e in events),'missing syntax SQL')
        return
    required=required_assertions(mode)
    assertions=[e for e in events if e['kind']=='assertion']
    require([e['assertion'] for e in assertions]==[x[0] for x in required],'business assertions missing or reordered')
    pending={}
    last={}
    position=0
    for e in events:
        if e['kind']=='sql_send':pending[e['session']]=normalized(e['sql'])
        elif e['kind']=='sql_result':last[e['session']]=(pending.pop(e['session']),e['rows'])
        elif e['kind']=='assertion':
            key,session,sql,expected=required[position]
            require(e['expected']==expected,'expected values not frozen')
            require(last.get(session)==(sql,e['observed']),'assertion not bound to actual SQL response')
            if position==len(required)-1 and mode!='baseline':
                mutated={'mutant-rc-for-rr':['1\t11','2\t21'],'mutant-stale-write':['1\t8','2\t20'],
                         'mutant-missing-tenant':[f'{t*1000+100+d}\t{d}' for d in (3,4,5,6) for t in (1,2)]}[mode]
                require(e['observed']==mutated,'unexpected semantic mutation outcome')
            else:require(e['observed']==expected,'baseline observation differs')
            position+=1
    require(len([e for e in events if e['kind']=='sql_send'])>=len(required)+10,'insufficient SQL frames')
