from service import ControlledJob

job = ControlledJob()
publications = []
publish_done = job.done.set
def observe_done():
    publications.append(job.snapshot())
    publish_done()
job.done.set = observe_done
job.thread.start()
try:
    if not job.ready.wait(4):
        raise TimeoutError('ready')
    job.cancel()
    job.permit_commit.set()
    if not job.computed.wait(4):
        raise TimeoutError('computed')
    state = job.snapshot()
    if state['worker_error'] is not None:
        raise RuntimeError(state['worker_error'])
    if state['result'] != 'cancelled' or state['effects']:
        raise AssertionError('CANCEL_EFFECT')
    if state['done'] or not state['resource_open']:
        raise AssertionError('PUBLISH_ORDER')
finally:
    job.permit_commit.set()
    job.permit_cleanup.set()
    job.thread.join(4)
    if job.thread.is_alive():
        raise AssertionError('CLEANUP_THREAD')
state = job.snapshot()
if state['worker_error'] is not None:
    raise RuntimeError(state['worker_error'])
if state['resource_open'] or not state['done']:
    raise AssertionError('CLEANUP_RESOURCE')
if not publications or any(state['resource_open'] for state in publications):
    raise AssertionError('PUBLISH_ORDER')
print('cancelled; zero effects; resource closed; worker joined')
