#!/usr/bin/env python3
"""Fixed finite cases; exit 42 means only a named semantic assertion mismatch."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from driver import Evidence, InfraFailure, SemanticMismatch, Session, SqlFailure
from safety import safe_path
ROOT = safe_path(Path(__file__).absolute().parent)
MODES = ('baseline', 'mutant-missing-tenant', 'mutant-rc-for-rr', 'mutant-stale-write', 'control-sql-error')

class Lab:
    def __init__(self, args, ev):
        self.args, self.ev, self.sessions = args, ev, []
    def initialize(self):
        args, ev = self.args, self.ev
        if not re.fullmatch('[a-f0-9]{64}', args.container) or not re.fullmatch('[a-f0-9]{32}', args.owner):
            raise InfraFailure('invalid owned identity')
        label = subprocess.check_output(['docker', 'inspect', '--format', '{{index .Config.Labels "knowledge-station.mechanisms-owner"}}', args.container], text=True, timeout=10).strip()
        if label != args.owner:
            raise InfraFailure('container owner mismatch')
        self.observer = self.session('observer')
        self.a = self.session('A')
        self.b = self.session('B')
        if len({s.connection_id for s in self.sessions}) != 3:
            raise InfraFailure('sessions are not distinct connections')
        version = self.observer.query('SELECT VERSION(), @@version_comment, @@transaction_isolation, @@autocommit')
        ev.emit('server_identity', rows=version)
        if len(version)!=1 or version[0].split('\t')[0]!='8.4.7':
            raise InfraFailure('server version mismatch')
        self.observer.query((ROOT / 'sql/schema.sql').read_text())
    def session(self, name):
        s = Session(self.args.container, self.ev, name)
        self.sessions.append(s)
        return s
    def reset(self):
        for s in self.sessions:
            s.query('ROLLBACK; SET autocommit=1; SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        self.observer.query('DELETE FROM inventory; INSERT INTO inventory VALUES (1,10),(2,20)')
        self.eq('reset.rows', self.observer.query('SELECT sku, available FROM inventory ORDER BY sku'), ['1\t10','2\t20'])
    def eq(self, key, actual, expected):
        self.ev.equal(key, actual, expected)
    def read(self, s):
        return s.query('SELECT sku, available FROM inventory ORDER BY sku')
    def start(self, s, level='REPEATABLE READ', snapshot=False):
        s.query('SET SESSION TRANSACTION ISOLATION LEVEL ' + level)
        s.query('START TRANSACTION' + (' WITH CONSISTENT SNAPSHOT' if snapshot else ''))
    def change_b(self, first=11, second=21):
        self.start(self.b)
        self.eq('B.changed-two', self.b.query(f'UPDATE inventory SET available=CASE sku WHEN 1 THEN {first} ELSE {second} END; SELECT ROW_COUNT()'), ['2'])
        self.b.query('COMMIT')
        self.ev.emit('barrier', name='B_commit_acknowledged')
    def index_cases(self):
        self.observer.query('DELETE FROM orders')
        values = [f"({tenant*1000+state*100+day},{tenant},{state},{day},{day*10},'t{tenant}-s{state}-d{day}')" for tenant in (1,2) for state in (0,1,2) for day in range(1,7)]
        self.observer.query('INSERT INTO orders VALUES ' + ','.join(values))
        self.eq('index.fixture-count', self.observer.query('SELECT COUNT(*) FROM orders'), ['36'])
        self.ev.emit('statistics', rows=self.observer.query('ANALYZE TABLE orders'))
        self.ev.emit('index_statistics', rows=self.observer.query('SHOW INDEX FROM orders'))
        base = (ROOT / 'sql/access_paths.sql').read_text().strip().split(';')
        queries = [(name, sql.strip()) for name, sql in zip(('ordinary-covering','constrained-covering','constrained-noncovering'),base) if sql.strip()]
        if self.args.mode == 'mutant-missing-tenant':
            queries[0] = (queries[0][0], queries[0][1].replace('tenant_id = 1 AND ',''))
        for name, sql in queries:
            raw = self.observer.query('EXPLAIN FORMAT=JSON ' + sql)
            plan = json.loads('\n'.join(raw))
            if 'query_block' not in plan:
                raise InfraFailure('EXPLAIN did not return a query block')
            self.ev.emit('explain', query=name, constrained=name.startswith('constrained'), plan=plan)
            expected = [f'{1100+d}\t{d}' + (f'\tt1-s1-d{d}' if name == 'constrained-noncovering' else '') for d in (3,4,5,6)]
            self.eq('index.'+name+'.rows', self.observer.query(sql), expected)
        # EXPLAIN ANALYZE really executes this SELECT in the throwaway schema.
        self.ev.emit('explain_analyze', query='constrained-covering', rows=self.observer.query('EXPLAIN ANALYZE ' + queries[1][1]))
        other = [
            ('range-residual', 'SELECT order_id FROM orders FORCE INDEX (idx_tenant_state_created) WHERE tenant_id=1 AND state>=1 AND created_at=3 ORDER BY order_id', ['1103','1203']),
            ('missing-left-prefix', 'SELECT order_id FROM orders WHERE state=1 AND created_at=3 ORDER BY order_id', ['1103','2103']),
            ('cross-state-sort', 'SELECT order_id,created_at FROM orders WHERE tenant_id=1 AND state>=1 ORDER BY created_at,order_id', [f'{1000+s*100+d}\t{d}' for d in range(1,7) for s in (1,2)])
        ]
        for name, sql, expected in other:
            self.ev.emit('explain', query=name, constrained='FORCE INDEX' in sql, plan=json.loads('\n'.join(self.observer.query('EXPLAIN FORMAT=JSON '+sql))))
            self.eq('index.'+name+'.rows', self.observer.query(sql), expected)
    def begin_is_not_snapshot(self):
        self.reset()
        self.start(self.a)
        self.change_b()
        self.eq('begin.first-read-after-B', self.read(self.a), ['1\t11','2\t21'])
        self.a.query('ROLLBACK')
        self.reset()
        self.start(self.a, snapshot=True)
        self.change_b()
        self.eq('explicit-snapshot.before-B', self.read(self.a), ['1\t10','2\t20'])
        self.a.query('ROLLBACK')
    def rr_retention(self):
        self.reset()
        self.start(self.a, 'READ COMMITTED' if self.args.mode == 'mutant-rc-for-rr' else 'REPEATABLE READ')
        self.eq('rr.first', self.read(self.a), ['1\t10','2\t20'])
        self.ev.emit('barrier', name='A_first_consistent_read_acknowledged')
        self.change_b()
        self.eq('rr.repeat', self.read(self.a), ['1\t10','2\t20'])
        self.a.query('COMMIT')
        self.eq('rr.after-commit', self.read(self.a), ['1\t11','2\t21'])
    def rc_refresh(self):
        self.reset()
        self.start(self.a, 'READ COMMITTED')
        self.eq('rc.first', self.read(self.a), ['1\t10','2\t20'])
        self.change_b()
        self.eq('rc.refresh', self.read(self.a), ['1\t11','2\t21'])
        self.a.query('ROLLBACK')
    def current_and_own(self):
        self.reset()
        self.start(self.a)
        self.eq('own.initial-snapshot', self.read(self.a), ['1\t10','2\t20'])
        self.change_b(7,17)
        self.eq('current.locking-value', self.a.query('SELECT available FROM inventory WHERE sku=1 FOR UPDATE'), ['7'])
        self.eq('current.does-not-refresh-view', self.read(self.a), ['1\t10','2\t20'])
        sql = (ROOT / 'sql/current_write.sql').read_text()
        if self.args.mode == 'mutant-stale-write':
            sql = sql.replace('available - 2', '10 - 2')
        self.eq('own.affected', self.a.query(sql), ['1'])
        self.eq('own.mixed-view', self.read(self.a), ['1\t5','2\t20'])
        self.eq('own.uncommitted-hidden', self.read(self.b), ['1\t7','2\t17'])
        self.a.query('ROLLBACK')
        self.eq('own.rollback-restores', self.read(self.observer), ['1\t7','2\t17'])
        self.start(self.a)
        self.eq('own.commit-affected', self.a.query((ROOT/'sql/current_write.sql').read_text()), ['1'])
        self.a.query('COMMIT')
        self.eq('own.commit-visible', self.read(self.b), ['1\t5','2\t17'])
    def lock_handoff(self):
        self.reset()
        self.start(self.a)
        self.eq('lock.A-value', self.a.query('SELECT available FROM inventory WHERE sku=1 FOR UPDATE'), ['10'])
        self.start(self.b)
        self.b.send('UPDATE inventory SET available=available-3 WHERE sku=1 AND available>=3; SELECT ROW_COUNT()')
        deadline = time.monotonic() + 5
        query = ('SELECT COUNT(*) FROM performance_schema.data_lock_waits w '
                 'JOIN performance_schema.threads r ON w.REQUESTING_THREAD_ID=r.THREAD_ID '
                 'JOIN performance_schema.threads b ON w.BLOCKING_THREAD_ID=b.THREAD_ID '
                 f'WHERE r.PROCESSLIST_ID={int(self.b.connection_id)} AND b.PROCESSLIST_ID={int(self.a.connection_id)}')
        while True:
            count = self.observer.query(query)
            if len(count)!=1 or re.fullmatch('[0-9]+',count[0]) is None:
                raise InfraFailure('malformed lock wait count')
            if int(count[0])>0:
                break
            if time.monotonic() >= deadline:
                raise InfraFailure('expected engine lock wait was not observed')
            time.sleep(0.05) # Poll a server predicate, never use elapsed delay as ordering proof.
        self.ev.emit('barrier', name='B_waits_for_A_engine_lock', rows=count, waiting_connection=self.b.connection_id, blocking_connection=self.a.connection_id)
        self.eq('lock.A-affected', self.a.query('UPDATE inventory SET available=available-2 WHERE sku=1; SELECT ROW_COUNT()'), ['1'])
        self.a.query('COMMIT')
        self.eq('lock.B-affected-after-release', self.b.receive(), ['1'])
        self.eq('lock.B-current-after-release', self.b.query('SELECT available FROM inventory WHERE sku=1'), ['5'])
        self.b.query('ROLLBACK')
        self.eq('lock.B-rollback', self.read(self.observer), ['1\t8','2\t20'])
    def run(self):
        if self.args.mode == 'control-sql-error':
            self.observer.query('SELEC available FROM inventory')
            raise InfraFailure('syntax control did not fail')
        for name in ('index_cases','begin_is_not_snapshot','rr_retention','rc_refresh','current_and_own','lock_handoff'):
            self.ev.emit('case_begin', case=name)
            getattr(self,name)()
            self.ev.emit('case_pass', case=name)
    def close(self):
        clean=True
        for s in reversed(self.sessions):
            try:
                clean=s.close() and clean
            except BaseException:
                clean=False
                try:
                    self.ev.emit('cleanup_error', session=s.name, error='session close raised')
                except BaseException:
                    pass
        return clean

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--container', required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--mode', choices=MODES, required=True)
    parser.add_argument('--out', required=True)
    args=parser.parse_args()
    from safety import safe_path
    out=safe_path(args.out)
    expected=ROOT/'results'/args.owner/args.mode
    if out!=expected: raise InfraFailure('case output outside owned mode directory')
    out.mkdir(exist_ok=False)
    ev=Evidence(out)
    report={'mode':args.mode,'status':'NOT_RUN'}
    lab=None
    rc=45
    try:
        lab=Lab(args,ev)
        lab.initialize()
        lab.run()
        rc=0
        report.update(status='PASS')
    except SemanticMismatch as error:
        rc=42
        report.update(status='SEMANTIC_MISMATCH', assertion=error.assertion, expected=error.expected, observed=error.observed)
    except SqlFailure as error:
        rc=43
        report.update(status='SQL_FAILURE', error=str(error))
    except TimeoutError:
        rc=44
        report.update(status='TIMEOUT', error='bounded SQL operation timed out')
    except Exception as error:
        report.update(status='INFRA_FAILURE', error_type=type(error).__name__)
    finally:
        if lab is not None:
            report['sessions_clean']=lab.close()
            if not report['sessions_clean']:
                report['prior_status']=report['status']
                report['status']='SESSION_CLEANUP_FAILURE'
                rc=46
        else:
            report['sessions_clean']=False
        report['exit_code']=rc
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return rc
if __name__=='__main__':
    sys.exit(main())
