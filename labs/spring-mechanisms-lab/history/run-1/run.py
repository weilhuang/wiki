#!/usr/bin/env python3
"""Finite, serial compilation and execution; preserves failures and full causes."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, signal, subprocess, sys, time
ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--gradle-cache', type=Path)
parser.add_argument('--deps-dir', type=Path)
parser.add_argument('--output', type=Path, default=Path('proof/local'))
args = parser.parse_args()
output = (ROOT / args.output).resolve()
if output.exists():
    raise SystemExit('Refusing to overwrite evidence: choose a new --output')
output.mkdir(parents=True)
started = time.monotonic()
records = []
source_files = [{'path':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in sorted(ROOT.rglob('*')) if p.is_file() and any(p.is_relative_to(ROOT / x) for x in ['src','resources'])]
source_files += [{'path': n, 'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in ['run.py','dependencies.lock.json']]
def execute(name, command, logical, expected=0, assertion=None):
    remaining = 85 - (time.monotonic() - started)
    if remaining <= 0: raise TimeoutError('whole-run budget exhausted')
    proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    timed_out = False
    cleanup_error = None
    try:
        text, _ = proc.communicate(timeout=min(remaining, 20))
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            try: text, _ = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                text, _ = proc.communicate(timeout=2)
        except BaseException as ex:
            cleanup_error = repr(ex)
            text = 'TIMEOUT: cleanup failed: ' + cleanup_error
    (output / (name+'.txt')).write_text(text)
    record = dict(name=name, command=logical, exitCode=proc.returncode, timedOut=timed_out,
                  cleanupError=cleanup_error, log=name+'.txt', expectedExitCode=expected)
    records.append(record)
    if timed_out or cleanup_error or proc.returncode != expected:
        raise AssertionError(f'{name}: process result rejected; see {name}.txt')
    if assertion:
        lines = text.splitlines()
        expected_line = 'Exception in thread "main" java.lang.AssertionError: ' + assertion
        if expected_line not in lines:
            raise AssertionError(f'{name}: not the expected top-level AssertionError')
        record['expectedAssertion'] = assertion
    record['status'] = 'pass'
    print(name, 'exit='+str(proc.returncode), flush=True)

failure = None
try:
    lock = json.loads((ROOT/'dependencies.lock.json').read_text()); jars=[]
    for item in lock:
        matches=[]
        if args.deps_dir: matches += list(args.deps_dir.glob(item['filename']))
        if args.gradle_cache: matches += list((args.gradle_cache/item['group']/item['artifact']/item['version']).glob('*/'+item['filename']))
        matches = list(dict.fromkeys(p.resolve() for p in matches))
        if len(matches)!=1: raise ValueError('Need exactly one locked artifact: '+item['filename'])
        path=matches[0]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']: raise ValueError('Dependency hash mismatch: '+item['filename'])
        jars.append(str(path))
    home=Path(os.environ['JAVA_HOME']); java=str(home/'bin/java'); javac=str(home/'bin/javac')
    execute('java-version',[java,'-version'],'java -version')
    execute('javac-version',[javac,'-version'],'javac -version')
    cp=os.pathsep.join(jars); build=output/'classes';build.mkdir()
    sources=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'src').rglob('*.java'))]
    execute('compile',[javac,'-J-Xmx64m','-J-XX:ActiveProcessorCount=2','--release','21','-cp',cp,'-d',str(build),*sources],
            'javac -J-Xmx64m -J-XX:ActiveProcessorCount=2 --release 21 -cp $LOCKED_CLASSPATH -d $BUILD_CLASSES src/lab/*.java')
    shutil.copytree(ROOT/'resources',build,dirs_exist_ok=True)
    flags=['-Xmx64m','-XX:ActiveProcessorCount=2','-cp',str(build)+os.pathsep+cp]
    for label,clazz,mutation,expected,assertion in [
        ('aop','lab.AopLab','none',0,None),('boot','lab.BootLab','none',0,None),
        ('negative-bypass','lab.AopLab','bypass-proxy',1,'outer advice order and self invocation boundary'),
        ('negative-cache','lab.AopLab','proceed-on-cache-hit',1,'cache hit must skip business'),
        ('negative-backoff','lab.BootLab','remove-backoff',1,'user bean identity and single implementation')]:
        execute(label,[java,*flags,clazz,mutation],f'java -Xmx64m -XX:ActiveProcessorCount=2 -cp $BUILD_CLASSES:$LOCKED_CLASSPATH {clazz} {mutation}',expected,assertion)
except BaseException as ex:
    failure=ex
finally:
    # Compiled files are scratch outputs. A cleanup error makes the run fail, without masking the primary error.
    cleanup=None
    try:
        if (output/'classes').exists(): shutil.rmtree(output/'classes')
    except BaseException as ex:
        cleanup=repr(ex)
        if failure is None: failure=ex
        else: failure.add_note('cleanup failed: '+cleanup)
    (output/'result.json').write_text(json.dumps(dict(status='pass' if failure is None else 'fail',
        failure=None if failure is None else repr(failure),cleanupError=cleanup,sourceFiles=source_files,
        commands=records,elapsedSeconds=round(time.monotonic()-started,3)),indent=2)+'\n')
if failure is not None: raise failure
print('PASS all intended runs and counterexamples; no compiled outputs retained')
