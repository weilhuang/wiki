"""Teaching application. Events expose phase boundaries; this is not a server."""
import threading

LIMIT = 3.0


class ControlledJob:
    def __init__(self, mode='correct'):
        self.mode = mode
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.permit_commit = threading.Event()
        self.computed = threading.Event()
        self.permit_cleanup = threading.Event()
        self.done = threading.Event()
        self.cancelled = False
        self.result = None
        self.effects = []
        self.resource_open = False
        self.worker_error = None
        self.thread = threading.Thread(target=self._guarded, daemon=False)

    def cancel(self):
        with self.lock:
            self.cancelled = True

    def snapshot(self):
        with self.lock:
            return {'result': self.result, 'effects': list(self.effects),
                    'resource_open': self.resource_open, 'done': self.done.is_set(),
                    'worker_error': self.worker_error}

    def _guarded(self):
        try:
            self.run()
        except BaseException as error:
            with self.lock:
                self.worker_error = {'type': type(error).__name__, 'message': str(error)}
        finally:
            # Wake the controller on failure; it must check worker_error explicitly.
            self.ready.set()
            self.computed.set()

    def run(self):
        if self.mode == 'startup-error':
            raise RuntimeError('injected startup failure')
        with self.lock:
            self.resource_open = True
        self.ready.set()
        if not self.permit_commit.wait(LIMIT):
            raise TimeoutError('commit gate')
        with self.lock:
            if self.cancelled and self.mode != 'ignore-cancel':
                self.result = 'cancelled'
            else:
                self.effects.append('receipt:7')
                if self.mode == 'duplicate':
                    self.effects.append('receipt:7')
                self.result = 'receipt:8' if self.mode == 'wrong-result' else 'receipt:7'
        if self.mode == 'early-done':
            self.done.set()
        self.computed.set()
        if not self.permit_cleanup.wait(LIMIT):
            raise TimeoutError('cleanup gate')
        with self.lock:
            if self.mode != 'leak':
                self.resource_open = False
        self.done.set()
