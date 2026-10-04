#!/usr/bin/env python3
"""Pure synthetic checks for the acceptance oracle. No cluster, subprocess or network."""
import argparse
import copy
import json
import sys
sys.dont_write_bytecode = True
from kind_acceptance import current_rollout


def fixture():
    app = {'metadata': {'uid': 'app-uid', 'generation': 2},
           'status': {'observedGeneration': 2, 'conditions': [{'type': 'Ready', 'status': 'True', 'observedGeneration': 2}]}}
    deployment = {'metadata': {'uid': 'deployment-uid', 'generation': 3}, 'spec': {'replicas': 1},
                  'status': {'observedGeneration': 3, 'replicas': 1, 'updatedReplicas': 1,
                             'readyReplicas': 1, 'availableReplicas': 1, 'unavailableReplicas': 0,
                             'conditions': [{'type': 'Available', 'status': 'True'}]}}
    pod = {'metadata': {'uid': 'pod-uid', 'name': 'operand', 'labels': {'lab.wiki.example/owner-uid': 'app-uid'}},
           'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}]}}
    return app, deployment, [pod]


def two_replicas(a, d, pods):
    a['spec'] = {'replicas': 2}
    d['spec']['replicas'] = 2
    d['status'].update(replicas=2, updatedReplicas=2, readyReplicas=2, availableReplicas=2)
    second = copy.deepcopy(pods[0])
    second['metadata'].update(uid='pod-two', name='operand-two')
    pods.append(second)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-id', required=True)
    args = parser.parse_args()
    tests = [
        ('ReadyOracleAcceptsCurrent', lambda a, d, p: None, True),
        ('ReadyOracleRejectsReplicaSpecMismatch', lambda a, d, p: d['spec'].update(replicas=2), False),
        ('ReadyOracleRejectsExtraOldReplica', lambda a, d, p: d['status'].update(replicas=2), False),
        ('ReadyOracleRejectsUnavailableReplica', lambda a, d, p: d['status'].update(unavailableReplicas=1), False),
        ('ReadyOracleRejectsStaleDeployment', lambda a, d, p: d['status'].update(observedGeneration=2), False),
        ('ReadyOracleRejectsStaleCondition', lambda a, d, p: a['status']['conditions'][0].update(observedGeneration=1), False),
        ('ReadyOracleRejectsExtraUnreadyPod', lambda a, d, p: p.append({'metadata': {'uid': 'old', 'labels': {'lab.wiki.example/owner-uid': 'app-uid'}}, 'status': {'phase': 'Pending'}}), False),
        ('ReadyOracleRejectsMissingAvailableCondition', lambda a, d, p: d['status'].update(conditions=[]), False),
    ]
    tests += [('ReadyOracleAcceptsTwoReplicas', two_replicas, True),
              ('ReadyOracleRejectsWrongDesiredCount', lambda a, d, p: a.update(spec={'replicas': 2}), False)]
    cases = []
    for name, mutate, expected in tests:
        try:
            a, d, pods = copy.deepcopy(fixture())
            mutate(a, d, pods)
            observed = bool(current_rollout(a, d, pods))
            if observed != expected:
                raise AssertionError('expected=%r observed=%r' % (expected, observed))
            cases.append({'id': name, 'status': 'pass'})
        except Exception as exc:
            cases.append({'id': name, 'status': 'fail', 'details': str(exc)})
    status = 'pass' if all(c['status'] == 'pass' for c in cases) else 'fail'
    print(json.dumps({'schema_version': 1, 'source_id': args.source_id, 'layer': 'pure-harness-oracle',
                      'status': status, 'exit_code': 0 if status == 'pass' else 1, 'cases': cases}))
    return 0 if status == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
