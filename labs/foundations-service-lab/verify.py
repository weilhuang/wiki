"""Finite child processes; exact failure attribution rather than nonzero = success."""
import hashlib
import json
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
EXPECTED = [('correct', 'cancel-first', None), ('correct', 'commit-first', None),
            ('wrong-result', 'commit-first', 'RESULT'),
            ('duplicate', 'commit-first', 'SIDE_EFFECT'),
            ('ignore-cancel', 'cancel-first', 'CANCEL_EFFECT'),
            ('early-done', 'commit-first', 'PUBLISH_ORDER'),
            ('leak', 'commit-first', ['PUBLISH_ORDER', 'RESOURCE'])]


def accepted(returncode, report, target):
    expected = [] if target is None else ([target] if isinstance(target, str) else target)
    wanted_status = 'pass' if target is None else 'rejected'
    wanted_code = 0 if target is None else 1
    return (returncode == wanted_code and report.get('status') == wanted_status
            and report.get('violations') == expected
            and report.get('harness_error') is None
            and report.get('cleanup', {}).get('thread_alive') is False
            and report.get('cleanup', {}).get('resource_open_after_rescue') is False)


def child(args):
    result = subprocess.run([sys.executable, '-B', *args], cwd=ROOT,
                            text=True, capture_output=True, timeout=15, check=False)
    if result.stderr:
        raise AssertionError('unexpected child stderr: ' + result.stderr)
    return result, json.loads(result.stdout)


def main():
    records = []
    waiting_result, waiting_report = child(['waiting.py'])
    if waiting_result.returncode != 0 or waiting_report.get('status') != 'pass':
        raise AssertionError('waiting observations failed')
    records.append({'command': 'python3 -B waiting.py', 'exitCode': waiting_result.returncode,
                    'report': waiting_report})
    for mode, schedule, target in EXPECTED:
        result, report = child(['assertions.py', mode, schedule])
        if not accepted(result.returncode, report, target):
            raise AssertionError('unexpected case outcome: ' + json.dumps(report))
        records.append({'command': f'python3 -B assertions.py {mode} {schedule}',
                        'exitCode': result.returncode, 'expectedViolation': target,
                        'report': report})
    # A real startup failure must never count as killing an implementation mutant.
    result, report = child(['assertions.py', 'startup-error', 'commit-first'])
    if (result.returncode != 2 or report['status'] != 'error'
            or report.get('before_cleanup', {}).get('worker_error') != {'type': 'RuntimeError', 'message': 'injected startup failure'}
            or accepted(result.returncode, report, 'RESULT')):
        raise AssertionError('startup failure was misclassified')
    records.append({'command': 'python3 -B assertions.py startup-error commit-first',
                    'exitCode': result.returncode, 'expectedStatus': 'error', 'report': report})
    # Guard the grader too: false green, wrong failure and malformed report are rejected.
    sample = records[3]['report']
    if accepted(0, sample, 'RESULT') or accepted(1, sample, 'RESOURCE') or accepted(1, {}, 'RESULT'):
        raise AssertionError('grader accepted mismatched evidence')
    sources = [{'path': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
               for p in sorted(ROOT.glob('*.py'))]
    print(json.dumps({'status': 'pass', 'python': platform.python_version(),
                      'implementation': platform.python_implementation(),
                      'platform': platform.system(), 'sourceFiles': sources,
                      'grader_guards': ['startup-error', 'wrong-exit', 'wrong-cause', 'malformed-report'],
                      'records': records}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
