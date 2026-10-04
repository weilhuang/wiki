#!/usr/bin/env python3
"""Compile/run exact semantic counterexamples in owned temporary copies, never mutate source."""
import argparse
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import time

HERE = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('controller_go_events', Path(__file__).with_name('go_events.py'))
go_events = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(go_events)
_process_spec = importlib.util.spec_from_file_location('controller_owned_process', Path(__file__).with_name('owned_process.py'))
owned_process = importlib.util.module_from_spec(_process_spec); _process_spec.loader.exec_module(owned_process)
PACKAGE = 'example.com/wiki/p3-controller/internal/controller'
MUTANTS = [
    {'id': 'foreign-deployment-write', 'old': 'if !metav1.IsControlledBy(d, a) {', 'new': 'if false {',
     'test': 'TestReconcileRefusesForeignChildren/Deployment/unowned', 'message': 'FOREIGN_CHILD_UNCHANGED', 'names': ['TestReconcileRefusesForeignChildren', 'TestReconcileRefusesForeignChildren/Deployment/unowned']},
    {'id': 'stale-rollout-ready', 'old': 'd.Status.ObservedGeneration < d.Generation || ', 'new': '',
     'test': 'TestReadinessRequiresCurrentRollout/stale-observation', 'message': 'READINESS_CONTRACT', 'names': ['TestReadinessRequiresCurrentRollout', 'TestReadinessRequiresCurrentRollout/stale-observation']},
    {'id': 'recreated-uid-stamped', 'old': 'current.UID != observed.UID || ', 'new': '',
     'test': 'TestStatusDoesNotStampRecreatedUID', 'message': 'STALE_UID_STAMPED', 'names': ['TestStatusDoesNotStampRecreatedUID']},
    {'id': 'allocated-service-ip-erased', 'old': 's.Spec.Type = corev1.ServiceTypeClusterIP',
     'new': 's.Spec.ClusterIP = ""\n\ts.Spec.Type = corev1.ServiceTypeClusterIP',
     'test': 'TestServiceMutationPreservesAllocatedFields', 'message': 'ALLOCATED_FIELDS_PRESERVED', 'names': ['TestServiceMutationPreservesAllocatedFields']},
]


def semantic_failure(raw, code, target, marker):
    candidates = [m for m in MUTANTS if m['test']==target and m['message']==marker]
    if len(candidates)!=1: raise ValueError('undeclared mutant target/marker')
    return go_events.semantic(raw, code, PACKAGE, candidates[0]['names'], target, marker)


def command_for(mutant):
    return ['go', 'test', '-buildvcs=false', '-mod=readonly', '-trimpath', '-p=1', '-json', '-count=1', '-timeout=20s',
            '-run', '^' + mutant['test'].replace('/', '$/^') + '$', './internal/controller']


def changed_source(source, mutant):
    if source.count(mutant['old'])!=1: raise ValueError('mutation anchor is not unique')
    return source.replace(mutant['old'], mutant['new'])


def run(command, cwd, deadline, offline=True):
    env = {**os.environ, 'GOTOOLCHAIN': 'local', 'GOENV': 'off', 'GOWORK': 'off', 'GOMAXPROCS': '2', 'CGO_ENABLED': '0'}
    if offline: env['GOPROXY'] = 'off'
    process = subprocess.Popen(command, cwd=cwd, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    reader = selectors.DefaultSelector(); reader.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    failure = None
    try:
        while reader.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise TimeoutError('mutant suite deadline exhausted')
            for key, _ in reader.select(min(remaining, .5)):
                data = os.read(key.fd, 65536)
                if not data: reader.unregister(key.fileobj); continue
                output.extend(data)
                if len(output) > 1024 * 1024: raise ValueError('Go mutant output exceeded 1 MiB')
        return process.wait(timeout=max(.1, deadline-time.monotonic())), bytes(output)
    except BaseException as exc:
        failure = exc
        raise
    finally:
        reader.close(); process.stdout.close()
        cleanup = owned_process.finish_group(process, seconds=2)
        if not cleanup['process_group_cleanup'] or cleanup['lingering_children']:
            raise ValueError('owned command group did not exit cleanly; prior failure='+str(failure)) from failure


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--source-id', required=True); args = parser.parse_args()
    deadline = time.monotonic() + 150
    rows = []
    report = {'schema_version': 1, 'source_id': args.source_id, 'layer': 'go-unit-semantic-mutants', 'status': 'fail', 'cases': rows}
    try:
        with tempfile.TemporaryDirectory(prefix='controller-mutants-') as directory:
            root = Path(directory)
            for mutant in MUTANTS:
                work = root / mutant['id']; shutil.copytree(HERE, work)
                command = command_for(mutant)
                row = {'id':mutant['id'],'status':'fail','command':command}
                rows.append(row)
                code, baseline = run(command, work, min(deadline, time.monotonic()+30))
                row.update(baseline_exit_code=code,baseline_jsonl=baseline.decode())
                if code != 0: raise ValueError('exact baseline did not exit0 for '+mutant['id'])
                go_events.positive(baseline, {PACKAGE: mutant['names']}, frames_only=True)
                source = work / 'internal/controller/reconciler.go'; before = source.read_text()
                source.write_text(changed_source(before, mutant))
                row['mutant_file_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
                code, raw = run(command, work, min(deadline, time.monotonic()+30))
                row.update(exit_code=code,mutant_jsonl=raw.decode())
                observation = semantic_failure(raw, code, mutant['test'], mutant['message'])
                row.update(status='pass',**observation)
        report.update(status='pass', exit_code=0, temporary_copies_removed=True)
    except Exception as exc:
        report.update(exit_code=1, failure=str(exc))
    completed = {r['id'] for r in rows}
    rows.extend({'id': m['id'], 'status': 'not_run'} for m in MUTANTS if m['id'] not in completed)
    print(json.dumps(report, ensure_ascii=False))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
