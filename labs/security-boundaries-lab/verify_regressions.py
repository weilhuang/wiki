"""Check that real source mutations fail the strengthened public verifier.
No dependencies or network; each altered model runs in an isolated temporary copy.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
CASES = (
    ('ignore-grant-actions',
     'and request.action == "read" and request.action in grant.actions',
     'and request.action == "read"', 'EMPTY_GRANT_ACTIONS'),
    ('online-omits-profile',
     'return snapshot_accepts(claims, now) and claims.token_id not in revoked',
     'return claims.token_id not in revoked', 'ONLINE_PROFILE:issuer'),
    ('cache-ignores-inactive',
     'return (snapshot_accepts(claims, now) and cache.active',
     'return (snapshot_accepts(claims, now)', 'CACHE_INACTIVE'),
    ('cache-ignores-observed-time',
     'and cache.observed_at <= now < cache.valid_until)',
     'and now < cache.valid_until)', 'CACHE_NOT_OBSERVED'),
    ('commit-ignores-revision',
     'if order is None or order.revision != prepared.revision:',
     'if order is None:', 'STALE_PREPARATION'),
    ('commit-does-not-increment-revision',
     'order, revision=order.revision + 1, note=prepared.note)',
     'order, revision=order.revision, note=prepared.note)', 'STALE_PREPARATION'),
)


def assert_target_rejection(result, code):
    lines = result.stderr.splitlines()
    expected = 'AssertionError: ' + code
    if (result.returncode != 1 or result.stdout or not lines
            or lines[0] != 'Traceback (most recent call last):' or lines[-1] != expected):
        raise AssertionError('Wrong failure identity; expected ' + expected)
    return expected


def main():
    original = (ROOT / 'model.py').read_text()
    rows = []
    for name, old, new, code in CASES:
        if original.count(old) != 1:
            raise AssertionError('Mutation no longer has exactly one target: ' + name)
        altered = original.replace(old, new)
        with tempfile.TemporaryDirectory(prefix='identity-verifier-') as directory:
            target = Path(directory)
            for path in ROOT.glob('*.py'):
                shutil.copyfile(path, target / path.name)
            (target / 'model.py').write_text(altered)
            result = subprocess.run([sys.executable, '-B', 'verify.py'], cwd=target,
                                    capture_output=True, text=True, timeout=5)
            exception = assert_target_rejection(result, code)
            rows.append({'mutation': name, 'exitCode': result.returncode,
                         'exception': exception,
                         'mutatedModelSha256': hashlib.sha256(altered.encode()).hexdigest()})
    # A crash with matching words, compile/startup error or unexpected success is not proof.
    target_code = 'EMPTY_GRANT_ACTIONS'
    for exception, exit_code in [('RuntimeError: '+target_code, 1),
                                 ('SyntaxError: '+target_code, 1),
                                 ('ModuleNotFoundError: '+target_code, 1),
                                 ('AssertionError: '+target_code, 0)]:
        fake = subprocess.CompletedProcess([], exit_code, '', 'Traceback (most recent call last):\n'+exception+'\n')
        try:
            assert_target_rejection(fake, target_code)
        except AssertionError:
            continue
        raise AssertionError('Failure classifier accepted '+exception)
    print(json.dumps({'status': 'pass', 'originalModelSha256': hashlib.sha256(original.encode()).hexdigest(),
                      'scope': 'six source mutations; exact Python assertion attribution; no real authentication provider',
                      'failureClassifierNegatives': 4, 'records': rows}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
