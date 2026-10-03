"""Finite stdlib observations; no scheduler/fairness or performance claim."""
import json
import queue
import select
import socket
import threading
import time

LIMIT = 3.0


def require(value, message):
    if not value:
        raise AssertionError(message)


def wait(event, label):
    require(event.wait(LIMIT), 'HARNESS_TIMEOUT:' + label)


class Worker:
    def __init__(self, target):
        self.errors = queue.Queue()
        def guarded():
            try:
                target()
            except BaseException as error:
                self.errors.put((type(error).__name__, str(error)))
        self.thread = threading.Thread(target=guarded, daemon=False)
        self.thread.start()

    def join(self):
        self.thread.join(LIMIT + 1)
        require(not self.thread.is_alive(), 'CLEANUP:worker-alive')
        require(self.errors.empty(), 'WORKER_ERROR:' + repr(list(self.errors.queue)))


def cpu_work():
    start_wall, start_cpu = time.perf_counter_ns(), time.thread_time_ns()
    actual = sum(i * i for i in range(100_000))
    cpu_ns, wall_ns = time.thread_time_ns() - start_cpu, time.perf_counter_ns() - start_wall
    expected = 99_999 * 100_000 * 199_999 // 6
    require(actual == expected, 'RESULT:sum-of-squares')
    return {'kind': 'cpu', 'sum': actual, 'thread_cpu_ns': cpu_ns,
            'elapsed_ns': wall_ns, 'measurement_only': True}


def lock_wait():
    lock = threading.Lock()
    contended, acquired = threading.Event(), threading.Event()
    lock.acquire()
    def use_lock():
        require(not lock.acquire(blocking=False), 'SETUP:lock-must-be-held')
        contended.set()
        require(lock.acquire(timeout=LIMIT), 'HARNESS_TIMEOUT:lock-acquire')
        try:
            acquired.set()
        finally:
            lock.release()
    worker = Worker(use_lock)
    try:
        wait(contended, 'observed-lock-contention')
        require(not acquired.is_set(), 'ORDER:acquired-before-release')
    finally:
        lock.release()
        worker.join()
    require(acquired.is_set() and not lock.locked(), 'CLEANUP:lock')
    return {'kind': 'lock', 'failed_nonblocking_acquire': True,
            'acquired_after_release': True, 'worker_alive': False, 'lock_held': False}


def queue_wait():
    jobs = queue.Queue(maxsize=1)
    empty_seen, received = threading.Event(), threading.Event()
    result = []
    def consume():
        try:
            jobs.get_nowait()
        except queue.Empty:
            empty_seen.set()
        else:
            raise AssertionError('SETUP:queue-not-empty')
        result.append(jobs.get(timeout=LIMIT))
        received.set()
    worker = Worker(consume)
    try:
        wait(empty_seen, 'empty-queue-observation')
        require(not received.is_set(), 'ORDER:received-before-put')
    finally:
        jobs.put('job-7', timeout=LIMIT)
        worker.join()
    require(result == ['job-7'] and jobs.empty(), 'RESULT:queue-transfer')
    return {'kind': 'queue', 'empty_before_put': True, 'result': result,
            'worker_alive': False, 'queued_after_join': 0}


def recv_exact(sock, size):
    data = bytearray()
    deadline = time.monotonic() + LIMIT
    while len(data) < size:
        remaining = deadline - time.monotonic()
        require(remaining > 0, 'HARNESS_TIMEOUT:recv-total-budget')
        sock.settimeout(remaining)
        part = sock.recv(size - len(data))
        if not part:
            raise EOFError('peer closed before complete message')
        data.extend(part)
    return bytes(data)


def loopback_wait():
    ready, received = threading.Event(), threading.Event()
    result, sockets, worker = [], [], None
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockets.append(listener)
        listener.settimeout(LIMIT)
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        sender = socket.create_connection(listener.getsockname(), timeout=LIMIT)
        sockets.append(sender)
        receiver, _ = listener.accept()
        sockets.append(receiver)
        receiver.settimeout(LIMIT)
        def read_message():
            ready.set()
            result.append(recv_exact(receiver, 2).decode('ascii'))
            received.set()
        worker = Worker(read_message)
        wait(ready, 'reader-started')
        readable, _, _ = select.select([receiver], [], [], 0)
        require(not readable and not received.is_set(), 'SETUP:data-before-send')
        sender.sendall(b'OK')
        worker.join()
        worker = None
        require(result == ['OK'], 'RESULT:loopback-message')
    finally:
        # shutdown is a wake-up aid, not a portable promise that close cancels any I/O.
        for sock in reversed(sockets):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        if worker is not None:
            worker.join()
    require(all(sock.fileno() == -1 for sock in sockets), 'CLEANUP:socket-open')
    return {'kind': 'loopback', 'not_readable_before_send': True, 'result': result,
            'worker_alive': False, 'open_socket_objects': 0,
            'kernel_park_observed': False}


def main():
    print(json.dumps({'status': 'pass', 'observations': [cpu_work(), lock_wait(),
          queue_wait(), loopback_wait()]}, sort_keys=True))


if __name__ == '__main__':
    main()
