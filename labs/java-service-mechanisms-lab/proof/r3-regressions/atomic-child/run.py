#!/usr/bin/env python3
"""Bounded JDK21 lab. Standard-library Python; no dependencies or network.
SPDX-License-Identifier: MIT
"""
import argparse, hashlib, json, os, pathlib, re, select, shutil, signal, subprocess, tempfile, time

ROOT = pathlib.Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=pathlib.Path)
args = parser.parse_args()
out = args.output.resolve()
if out.exists():
    raise SystemExit('Refusing to overwrite evidence: choose a new output directory')
out.mkdir(parents=True)
jdk = pathlib.Path(os.environ['JAVA_HOME'])
java, javac, jcmd = (str(jdk / 'bin' / name) for name in ('java', 'javac', 'jcmd'))
records = []
flags = ['-Xms32m', '-Xmx64m', '-XX:ActiveProcessorCount=2', '-XX:+UseSerialGC']

def run(argv, name, timeout=15, expected=0, token=None, required=()):
    p = subprocess.run(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    (out / name).write_text(p.stdout)
    record = {'artifact': name, 'exitCode': p.returncode, 'expectedExitCode': expected}
    if token: record['requiredToken'] = token
    records.append(record)
    exception_lines = [line for line in p.stdout.splitlines() if line.startswith('Exception in thread ')]
    if token:
        attributed = exception_lines == ['Exception in thread "main" java.lang.AssertionError: ' + token]
        attributed = attributed and 'Caused by:' not in p.stdout and 'Suppressed:' not in p.stdout
    else:
        attributed = not exception_lines
    complete = all(p.stdout.splitlines().count(marker) == 1 for marker in required)
    if p.returncode != expected or not attributed or not complete:
        raise AssertionError(f'{name}: wrong exit or missing target diagnostic')
    return p.stdout

def diagnostic_ok(exitcode, text):
    markers = ('READY cpu=RUNNABLE blocked=BLOCKED latch=WAITING',
               'ALLOCATED payloadBytes=268435456 retainedSlots=16', 'SAMPLED',
               'CLEANUP all four workers joined; watchdog joined', 'DIAGNOSTIC_OK')
    if exitcode != 0 or any(line.startswith('Exception in thread ') for line in text.splitlines()):
        raise AssertionError('unexpected diagnostic process failure')
    if any(text.splitlines().count(marker) != 1 for marker in markers):
        raise AssertionError('incomplete diagnostic output')

def until(stream, marker, destination, timeout=5):
    # Unbuffered binary pipe avoids TextIO readline prefetch hiding a line from select.
    deadline = time.monotonic() + timeout
    line = bytearray()
    while time.monotonic() < deadline:
        if not select.select([stream], [], [], max(0, deadline-time.monotonic()))[0]: break
        value = os.read(stream.fileno(), 1)
        if not value: break
        line += value
        if value == b'\n':
            text = line.decode(); destination.append(text); line.clear()
            if marker in text: return
    raise AssertionError('missing diagnostic marker: ' + marker)

try:
    version = run([java, '-version'], 'java-version.txt')
    if not re.search(r'version "21\.', version): raise AssertionError('JDK 21 required')
    run([javac, '-version'], 'javac-version.txt')
    with tempfile.TemporaryDirectory(prefix='java-mechanisms-') as build:
        srcs = sorted(str(p.relative_to(ROOT)) for p in (ROOT/'src').glob('*.java'))
        run([javac, '-J-Xmx64m', '-J-XX:ActiveProcessorCount=2', '--release', '21', '-encoding', 'UTF-8', '-d', build] + srcs, 'compile.txt', timeout=20)
        def command(cls, *extra): return [java] + flags + ['-cp', build, cls] + list(extra)
        run(command('HarnessContracts'), 'harness-contracts.txt', required=(
            'FAILURE_IDENTITY same Throwable once; distinct children retained; primary preserved',
            'COOPERATIVE_CLEANUP release then shutdown then await; no shutdownNow or interrupt',
            'FORCED_CLEANUP bounded timeout recorded as suppressed; worker ended', 'HARNESS_CONTRACTS_OK'))
        run(command('JmmLab'), 'jmm.txt', required=(
            'publication observed=42; guarantee comes from JLS, not this run',
            'volatile split read-modify-write result=1; both readers saw 0',
            'atomic increment result=2', 'JMM_CLEANUP all workers joined', 'JMM_OK'))
        run(command('ExecutorLab'), 'executor.txt', required=(
            'admission A=worker B=queue C=worker D=rejected; shutdown drained A/B/C exactly once',
            'execute exception=uncaught+hook; submit exception=Future.get cause; submit hook Throwable=null',
            'shutdownNow interrupted running task; returned exact queued FutureTask; owner cancelled pending Future',
            'offer/shutdown race: offered then shutdown then recheck removed+rejected; task never ran',
            'EXECUTOR_CLEANUP ordinary workers joined; scenario pools terminated', 'EXECUTOR_OK'))
        run(command('JmmLab', 'wrong-volatile-is-atomic'), 'negative-volatile.txt', expected=1, token='VOLATILE_COMPOUND_CLAIM expected=2 actual=1')
        run(command('ExecutorLab', 'wrong-max-first'), 'negative-max-first.txt', expected=1, token='MAX_FIRST_CLAIM expected=2 actual=1')
        run(command('ExecutorLab', 'wrong-drain-cancels'), 'negative-drain.txt', expected=1, token='DRAIN_CANCEL_CLAIM Future remained NEW')
        gc = out/'gc.log'
        argv = command('DiagnosticLab')
        argv.insert(1, '-Xlog:gc*:file=' + str(gc) + ':uptime,level,tags')
        p = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, start_new_session=True)
        lines = []
        try:
            until(p.stdout, 'READY', lines)
            snapshot_start = len(lines)
            p.stdin.write(b'snapshot\n'); p.stdin.flush(); until(p.stdout, 'SNAPSHOT_END', lines)
            (out/'threads-before.txt').write_text(''.join(lines[snapshot_start:]))
            p.stdin.write(b'allocate\n'); p.stdin.flush()
            until(p.stdout, 'ALLOCATED', lines)
            # Sampling interval, not a synchronization mechanism in the experiments.
            time.sleep(0.25)
            snapshot_start = len(lines)
            p.stdin.write(b'snapshot\n'); p.stdin.flush(); until(p.stdout, 'SNAPSHOT_END', lines)
            (out/'threads-after.txt').write_text(''.join(lines[snapshot_start:]))
            p.stdin.write(b'sample\n'); p.stdin.flush(); until(p.stdout, 'SAMPLED', lines)
            p.stdin.write(b'stop\n'); p.stdin.flush()
            remaining, _ = p.communicate(timeout=5)
            lines.append(remaining.decode())
            text = ''.join(lines); (out/'diagnostic.txt').write_text(text)
            records.append({'artifact':'diagnostic.txt','exitCode':p.returncode,'expectedExitCode':0})
            diagnostic_ok(p.returncode, text)
            for name in ('threads-before.txt','threads-after.txt'):
                dump = (out/name).read_text()
                for thread,state in [('lab-cpu-busy','RUNNABLE'),('lab-monitor-blocked','BLOCKED'),('lab-latch-waiter','WAITING')]:
                    block = re.search(r'^SNAPSHOT name='+thread+r' state=([A-Z_]+) ', dump, re.M)
                    if not block or block.group(1) != state: raise AssertionError(f'{name}: {thread} wrong state')
                if 'DiagnosticLab.busy' not in dump or 'owner=lab-monitor-holder' not in dump: raise AssertionError('missing application frames')
            cpu = re.findall(r'CPU (\S+) state=(\S+) deltaNs=(\d+)', text)
            if len(cpu) != 4: raise AssertionError('missing CPU samples')
            values = {name:int(value) for name,state,value in cpu}
            if values['lab-cpu-busy'] <= values['lab-latch-waiter']: raise AssertionError('CPU evidence does not support selected sample')
            gc_text = gc.read_text()
            if 'Pause Young (Allocation Failure)' not in gc_text: raise AssertionError('no actual allocation GC event')
            summary = {'status':'pass','cpuDeltaNs':values,'gcPauseEvents':len(re.findall(r'GC\(\d+\) Pause Young .*ms',gc_text)), 'bounds':{'maxHeapMiB':64,'activeProcessors':2,'applicationWorkers':4,'allocationPayloadMiB':256,'retainedArrayPayloadMiB':2}, 'limitations':['Controlled platform-thread process; no production workload or throughput claim','Thread snapshots come from same-process ThreadMXBean, not successful jcmd attach','CPU deltas and durations are observations of this run','GC pause is not evidence of a leak or request-level latency causation']}
            (out/'diagnostic-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try: p.wait(timeout=2)
                except subprocess.TimeoutExpired: os.killpg(p.pid, signal.SIGKILL); p.wait(timeout=2)
            (out/'diagnostic.txt').write_text(''.join(lines))
    (out/'result.json').write_text(json.dumps({'status':'pass','records':records,'sourceFiles':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted((ROOT/'src').glob('*.java'))]+[{'path':'run.py','sha256':hashlib.sha256((ROOT/'run.py').read_bytes()).hexdigest()}]},indent=2)+'\n')
    print('PASS: bounded JMM, executor and diagnostic evidence saved')
except BaseException as exc:
    (out/'result.json').write_text(json.dumps({'status':'fail','error':str(exc),'records':records},indent=2)+'\n')
    raise
