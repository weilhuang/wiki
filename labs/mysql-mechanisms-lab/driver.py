#!/usr/bin/env python3
"""Live MySQL CLI sessions. No DB simulator and no third-party Python package."""
from __future__ import annotations
import json
import queue
import subprocess
import threading
import time
import uuid

class SqlFailure(RuntimeError):
    pass

class InfraFailure(RuntimeError):
    pass

class SemanticMismatch(AssertionError):
    def __init__(self, assertion, expected, observed):
        self.assertion, self.expected, self.observed = assertion, expected, observed
        super().__init__(assertion)

class Evidence:
    def __init__(self, directory):
        self.directory, self.sequence = directory, 0
        self.bytes = 0
    def emit(self, kind, **fields):
        self.sequence += 1
        line = json.dumps(dict(sequence=self.sequence, kind=kind, **fields), ensure_ascii=False) + '\n'
        self.bytes += len(line.encode())
        if self.bytes > 512 * 1024:
            raise InfraFailure('trace exceeds 512 KiB')
        with (self.directory / 'trace.jsonl').open('a', encoding='utf-8') as f:
            f.write(line)
    def equal(self, assertion, observed, expected):
        self.emit('assertion', assertion=assertion, expected=expected, observed=observed)
        if observed != expected:
            raise SemanticMismatch(assertion, expected, observed)

class Session:
    def __init__(self, container, evidence, name):
        self.ev, self.name, self.pending = evidence, name, None
        self.lines = queue.Queue(maxsize=4096)
        self.proc = subprocess.Popen([
            'docker', 'exec', '-i', container, 'mysql', '--protocol=socket', '-uroot',
            '--batch', '--raw', '--skip-column-names', '--unbuffered', '--force',
            '--skip-reconnect', '--default-character-set=utf8mb4', 'mechanisms_lab'
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        self.reader = None
        try:
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            self.connection_id = self.query('SELECT CONNECTION_ID()')[0]
            self.ev.emit('session_open', session=name, connection_id=self.connection_id)
            self.query('SET SESSION max_execution_time=5000; SET SESSION innodb_lock_wait_timeout=8')
        except BaseException:
            # Constructor owns its Popen immediately, before it can be registered.
            try:
                self.close()
            except BaseException:
                if self.proc.poll() is None:
                    self.proc.kill()
                    self.proc.wait(timeout=3)
            raise
    def _read(self):
        try:
            for line in self.proc.stdout:
                if len(line) > 65536:
                    self.lines.put(InfraFailure('SQL line exceeds 64 KiB'), timeout=1)
                    return
                self.lines.put(line.rstrip('\n'), timeout=1)
        except Exception:
            try:
                self.lines.put(InfraFailure('SQL reader failed'), timeout=1)
            except queue.Full:
                pass
        finally:
            try:
                self.lines.put(None, timeout=1)
            except queue.Full:
                pass
    def send(self, sql):
        if self.pending is not None:
            raise InfraFailure('session already has in-flight statement')
        self.pending = '__END_' + uuid.uuid4().hex
        self.ev.emit('sql_send', session=self.name, sql=sql)
        self.proc.stdin.write(sql.rstrip().rstrip(';') + ";\nSELECT '" + self.pending + "';\n")
        self.proc.stdin.flush()
    def receive(self):
        deadline, output = time.monotonic() + 12, []
        while True:
            try:
                line = self.lines.get(timeout=max(0.001, deadline - time.monotonic()))
            except queue.Empty as error:
                raise TimeoutError('SQL response deadline') from error
            if line is None:
                raise InfraFailure('SQL client exited before sentinel')
            if isinstance(line, Exception):
                raise line
            if line == self.pending:
                self.pending = None
                break
            output.append(line)
            if len(output) > 2048 or sum(map(len, output)) > 256 * 1024:
                raise InfraFailure('SQL response exceeds bounded frame')
            if time.monotonic() >= deadline:
                raise TimeoutError('SQL response deadline')
        self.ev.emit('sql_result', session=self.name, connection_id=getattr(self, 'connection_id', None), rows=output)
        if any(line.startswith('ERROR ') for line in output):
            raise SqlFailure('\n'.join(output))
        return output
    def query(self, sql):
        self.send(sql)
        return self.receive()
    def close(self):
        failed = False
        try:
            if self.proc.poll() is None and self.pending is None:
                self.query('ROLLBACK')
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
            else:
                failed = True
        except Exception:
            failed = True
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        if self.reader is not None and self.reader.ident is not None:
            self.reader.join(timeout=2)
        self.ev.emit('session_close', session=self.name, exit_code=self.proc.returncode, clean=not failed and self.proc.returncode == 0)
        return not failed and self.proc.returncode == 0
