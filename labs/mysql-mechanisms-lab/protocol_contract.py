"""Complete expected client protocol; only bounded engine-lock polling varies."""
from pathlib import Path
from safety import require,secure_read
from trace_contract import normalized,required_assertions,READ,CURRENT

def protocol(mode,ids):
    stream=[]
    def event(*fields):stream.append(tuple(fields))
    def query(session,sql):
        event('sql_send',session,normalized(sql));event('sql_result',session)
    def check(key,session,sql):
        query(session,sql);event('assertion',key)
    def begin(name):event('case_begin',name)
    def passed(name):event('case_pass',name)
    def reset():
        for session in ('observer','A','B'):
            query(session,'ROLLBACK; SET autocommit=1; SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        query('observer','DELETE FROM inventory; INSERT INTO inventory VALUES (1,10),(2,20)')
        check('reset.rows','observer',READ)
    def start(session,level='REPEATABLE READ',snapshot=False):
        query(session,'SET SESSION TRANSACTION ISOLATION LEVEL '+level)
        query(session,'START TRANSACTION'+(' WITH CONSISTENT SNAPSHOT' if snapshot else ''))
    def changed(first=11,second=21):
        start('B')
        check('B.changed-two','B',f'UPDATE inventory SET available=CASE sku WHEN 1 THEN {first} ELSE {second} END; SELECT ROW_COUNT()')
        query('B','COMMIT');event('barrier','B_commit_acknowledged')
    def finish():
        for session in ('B','A','observer'):
            query(session,'ROLLBACK');event('session_close',session)
        return stream
    for session in ('observer','A','B'):
        query(session,'SELECT CONNECTION_ID()');event('session_open',session)
        query(session,'SET SESSION max_execution_time=5000; SET SESSION innodb_lock_wait_timeout=8')
    query('observer','SELECT VERSION(), @@version_comment, @@transaction_isolation, @@autocommit')
    event('server_identity')
    schema=secure_read(Path(__file__).absolute().parent/'sql/schema.sql',8192).decode()
    query('observer',schema)
    if mode=='control-sql-error':
        query('observer','SELEC available FROM inventory')
        return finish()
    begin('index_cases')
    query('observer','DELETE FROM orders')
    values=[f"({t*1000+s*100+d},{t},{s},{d},{d*10},'t{t}-s{s}-d{d}')" for t in (1,2) for s in (0,1,2) for d in range(1,7)]
    query('observer','INSERT INTO orders VALUES '+','.join(values))
    check('index.fixture-count','observer','SELECT COUNT(*) FROM orders')
    query('observer','ANALYZE TABLE orders');event('statistics')
    query('observer','SHOW INDEX FROM orders');event('index_statistics')
    queries={key.removeprefix('index.').removesuffix('.rows'):sql for key,session,sql,expected in required_assertions('baseline') if key.startswith('index.') and key.endswith('.rows')}
    for name in ('ordinary-covering','constrained-covering','constrained-noncovering'):
        sql=queries[name]
        if mode=='mutant-missing-tenant':sql=sql.replace('tenant_id = 1 AND ','')
        query('observer','EXPLAIN FORMAT=JSON '+sql);event('explain',name)
        check('index.'+name+'.rows','observer',sql)
        if mode=='mutant-missing-tenant':return finish()
    query('observer','EXPLAIN ANALYZE '+queries['constrained-covering']);event('explain_analyze','constrained-covering')
    for name in ('range-residual','missing-left-prefix','cross-state-sort'):
        query('observer','EXPLAIN FORMAT=JSON '+queries[name]);event('explain',name)
        check('index.'+name+'.rows','observer',queries[name])
    passed('index_cases')
    begin('begin_is_not_snapshot')
    reset();start('A');changed();check('begin.first-read-after-B','A',READ);query('A','ROLLBACK')
    reset();start('A',snapshot=True);changed();check('explicit-snapshot.before-B','A',READ);query('A','ROLLBACK')
    passed('begin_is_not_snapshot')
    begin('rr_retention')
    reset();start('A','READ COMMITTED' if mode=='mutant-rc-for-rr' else 'REPEATABLE READ')
    check('rr.first','A',READ);event('barrier','A_first_consistent_read_acknowledged')
    changed();check('rr.repeat','A',READ)
    if mode=='mutant-rc-for-rr':return finish()
    query('A','COMMIT');check('rr.after-commit','A',READ);passed('rr_retention')
    begin('rc_refresh')
    reset();start('A','READ COMMITTED');check('rc.first','A',READ);changed();check('rc.refresh','A',READ);query('A','ROLLBACK')
    passed('rc_refresh')
    begin('current_and_own')
    reset();start('A');check('own.initial-snapshot','A',READ);changed(7,17)
    check('current.locking-value','A','SELECT available FROM inventory WHERE sku=1 FOR UPDATE')
    check('current.does-not-refresh-view','A',READ)
    check('own.affected','A',CURRENT.replace('available - 2','10 - 2') if mode=='mutant-stale-write' else CURRENT)
    check('own.mixed-view','A',READ)
    if mode=='mutant-stale-write':return finish()
    check('own.uncommitted-hidden','B',READ);query('A','ROLLBACK');check('own.rollback-restores','observer',READ)
    start('A');check('own.commit-affected','A',CURRENT);query('A','COMMIT');check('own.commit-visible','B',READ)
    passed('current_and_own')
    begin('lock_handoff')
    reset();start('A');check('lock.A-value','A','SELECT available FROM inventory WHERE sku=1 FOR UPDATE');start('B')
    event('sql_send','B',normalized('UPDATE inventory SET available=available-3 WHERE sku=1 AND available>=3; SELECT ROW_COUNT()'))
    event('lock_poll','observer',normalized(lock_query(ids)))
    event('barrier','B_waits_for_A_engine_lock')
    check('lock.A-affected','A','UPDATE inventory SET available=available-2 WHERE sku=1; SELECT ROW_COUNT()');query('A','COMMIT')
    event('sql_result','B');event('assertion','lock.B-affected-after-release')
    check('lock.B-current-after-release','B','SELECT available FROM inventory WHERE sku=1');query('B','ROLLBACK')
    check('lock.B-rollback','observer',READ);passed('lock_handoff')
    return finish()

def lock_query(ids):
    return ('SELECT COUNT(*) FROM performance_schema.data_lock_waits w '
            'JOIN performance_schema.threads r ON w.REQUESTING_THREAD_ID=r.THREAD_ID '
            'JOIN performance_schema.threads b ON w.BLOCKING_THREAD_ID=b.THREAD_ID '
            f"WHERE r.PROCESSLIST_ID={int(ids['B'])} AND b.PROCESSLIST_ID={int(ids['A'])}")

def validate_protocol(events,mode):
    ids={e['session']:e['connection_id'] for e in events if e['kind']=='session_open'}
    require(set(ids)=={'observer','A','B'},'protocol session identities')
    actual=[]
    poll_values=[]
    lock_sql=normalized(lock_query(ids))
    i=0
    while i<len(events):
        e=events[i];kind=e['kind']
        if kind=='sql_send' and e['session']=='observer' and normalized(e['sql'])==lock_sql:
            require(i+1<len(events) and events[i+1]['kind']=='sql_result' and events[i+1]['session']=='observer','lock poll frame incomplete')
            rows=events[i+1]['rows']
            require(len(rows)==1 and rows[0].isdigit(),'lock poll response shape')
            poll_values.append(int(rows[0]))
            if not actual or actual[-1]!=('lock_poll','observer',lock_sql):actual.append(('lock_poll','observer',lock_sql))
            i+=2;continue
        if kind=='sql_send':actual.append((kind,e['session'],normalized(e['sql'])))
        elif kind in {'sql_result','session_open','session_close'}:actual.append((kind,e['session']))
        elif kind in {'case_begin','case_pass'}:actual.append((kind,e['case']))
        elif kind=='assertion':actual.append((kind,e['assertion']))
        elif kind=='barrier':actual.append((kind,e['name']))
        elif kind in {'explain','explain_analyze'}:actual.append((kind,e['query']))
        elif kind in {'server_identity','statistics','index_statistics'}:actual.append((kind,))
        else:raise RuntimeError('unexpected protocol event')
        i+=1
    if mode=='baseline':require(1<=len(poll_values)<=120 and all(v==0 for v in poll_values[:-1]) and poll_values[-1]>0,'lock poll progression')
    else:require(not poll_values,'unexpected lock polling')
    expected=protocol(mode,ids)
    require(actual==expected,'complete session/transaction protocol differs')
