"""Reject actual source mutations that the r1 observation windows missed."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

def mutations(original):
    late = original.replace("        with self.lock:\n            if self.mode != 'leak':\n                self.resource_open = False\n        self.done.set()", "        self.done.set()\n        with self.lock:\n            if self.mode != 'leak':\n                self.resource_open = False")
    transient = original.replace("        self.computed.set()\n        if not self.permit_cleanup.wait(LIMIT):", "        saved_result = self.result\n        if self.result == 'receipt:7':\n            self.result = 'receipt:WRONG'\n        self.computed.set()\n        if not self.permit_cleanup.wait(LIMIT):").replace("            raise TimeoutError('cleanup gate')\n        with self.lock:", "            raise TimeoutError('cleanup gate')\n        self.result = saved_result\n        with self.lock:")
    startup = original.replace("raise RuntimeError('injected startup failure')", "raise ValueError('not the injected startup failure')")
    return [('late-publication-before-release', late, 'PUBLISH_ORDER'),
            ('wrong-result-at-computed', transient, 'RESULT'),
            ('wrong-startup-identity', startup, 'STARTUP_IDENTITY')]


def check_failure(result, target):
    lines = result.stderr.splitlines()
    if result.returncode != 1 or result.stdout or not lines or lines[0] != 'Traceback (most recent call last):':
        raise AssertionError('Unexpected regression failure shape')
    if target == 'STARTUP_IDENTITY':
        if lines[-1] != 'AssertionError: startup failure was misclassified':
            raise AssertionError('Wrong startup failure attribution')
        return {'assertion': 'startup failure was misclassified'}
    prefix = 'AssertionError: unexpected case outcome: '
    if not lines[-1].startswith(prefix):
        raise AssertionError('Not the expected business verifier failure')
    report = json.loads(lines[-1][len(prefix):])
    if (report['status'] != 'rejected' or report['violations'] != [target]
            or report['harness_error'] is not None
            or report['cleanup']['thread_alive'] or report['cleanup']['resource_open_after_rescue']):
        raise AssertionError('Wrong business violation or failed cleanup')
    if target == 'RESULT' and (report['before_cleanup']['result'] != 'receipt:WRONG'
                               or report['after_join']['result'] != 'receipt:7'):
        raise AssertionError('Transient mutation must be wrong at computed and restored at join')
    if target == 'PUBLISH_ORDER' and (report['before_cleanup']['done']
            or not any(state['resource_open'] for state in report['publications'])
            or report['after_join']['resource_open']):
        raise AssertionError('Late publication mutation must expose only the intermediate window')
    return {'status': report['status'], 'violations': report['violations'],
            'before_cleanup': report['before_cleanup'], 'publications': report['publications'],
            'after_join': report['after_join'], 'cleanup': report['cleanup']}


def main():
    original = (ROOT/'service.py').read_text()
    records = []
    for name, source, target in mutations(original):
        if source == original:
            raise AssertionError('Mutation no longer applies: '+name)
        with tempfile.TemporaryDirectory(prefix='foundation-verifier-') as directory:
            temp = Path(directory)
            for p in ROOT.glob('*.py'):
                shutil.copyfile(p, temp/p.name)
            (temp/'service.py').write_text(source)
            result = subprocess.run([sys.executable, '-B', 'verify.py'], cwd=temp,
                                    text=True, capture_output=True, timeout=18)
            checked = check_failure(result, target)
            records.append({'mutation': name, 'exitCode': result.returncode,
                            'sourceSha256': hashlib.sha256(source.encode()).hexdigest(), 'observed': checked})
    print(json.dumps({'status': 'pass', 'originalServiceSha256': hashlib.sha256(original.encode()).hexdigest(),
                      'scope': 'three exact source mutations, synchronous publication witness and computed-phase result checks',
                      'records': records}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
