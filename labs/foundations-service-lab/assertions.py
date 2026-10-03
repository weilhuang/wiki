"""Result, causality, side-effect and cleanup oracle for ControlledJob."""
import json
import sys
from service import ControlledJob, LIMIT


def wait(event, label):
    if not event.wait(LIMIT + 1):
        raise TimeoutError(label)


def run_case(mode, schedule):
    job = ControlledJob(mode)
    violations = []
    publications = []
    publish_done = job.done.set
    def observe_done():
        publications.append(job.snapshot())
        publish_done()
    job.done.set = observe_done
    before_cleanup = after_join = None
    harness_error = None
    job.thread.start()
    try:
        wait(job.ready, 'worker-ready')
        if schedule == 'cancel-first':
            job.cancel()
        job.permit_commit.set()
        wait(job.computed, 'computed')
        # Worker cannot pass the cleanup gate until this observation is recorded.
        before_cleanup = job.snapshot()
        if before_cleanup['worker_error'] is not None:
            raise RuntimeError('worker failed: ' + repr(before_cleanup['worker_error']))
        if schedule == 'cancel-first':
            if before_cleanup['result'] != 'cancelled' or before_cleanup['effects'] != []:
                violations.append('CANCEL_EFFECT')
        else:
            if before_cleanup['result'] != 'receipt:7':
                violations.append('RESULT')
            if before_cleanup['effects'] != ['receipt:7']:
                violations.append('SIDE_EFFECT')
        if before_cleanup['done']:
            violations.append('PUBLISH_ORDER')
        if schedule == 'commit-first':
            job.cancel()
        job.permit_cleanup.set()
        job.thread.join(LIMIT + 1)
        if job.thread.is_alive():
            raise TimeoutError('worker-join')
        after_join = job.snapshot()
        if after_join['worker_error'] is not None:
            raise RuntimeError('worker failed: ' + repr(after_join['worker_error']))
        if schedule == 'cancel-first':
            if after_join['result'] != 'cancelled' or after_join['effects'] != []:
                violations.append('CANCEL_EFFECT')
        else:
            if after_join['result'] != 'receipt:7':
                violations.append('RESULT')
            if after_join['effects'] != ['receipt:7']:
                violations.append('SIDE_EFFECT')
        if any(state['resource_open'] for state in publications):
            violations.append('PUBLISH_ORDER')
        if after_join['resource_open']:
            violations.append('RESOURCE')
        if not after_join['done']:
            violations.append('COMPLETION')
    except BaseException as error:
        harness_error = {'type': type(error).__name__, 'message': str(error)}
    finally:
        job.permit_commit.set()
        job.permit_cleanup.set()
        job.thread.join(LIMIT + 1)
        # Record the implementation's leak BEFORE rescue cleanup.
        with job.lock:
            leaked_before_rescue = job.resource_open
            job.resource_open = False
        cleanup = {'thread_alive': job.thread.is_alive(),
                   'resource_open_after_rescue': job.resource_open,
                   'leaked_before_rescue': leaked_before_rescue}
    violations = list(dict.fromkeys(violations))
    status = 'error' if harness_error or cleanup['thread_alive'] else ('rejected' if violations else 'pass')
    return {'mode': mode, 'schedule': schedule, 'status': status, 'violations': violations,
            'before_cleanup': before_cleanup, 'publications': publications, 'after_join': after_join,
            'harness_error': harness_error, 'cleanup': cleanup}


def main():
    mode, schedule = sys.argv[1:]
    report = run_case(mode, schedule)
    print(json.dumps(report, sort_keys=True))
    return {'pass': 0, 'rejected': 1, 'error': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
