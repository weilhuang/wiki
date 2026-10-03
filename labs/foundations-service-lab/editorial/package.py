"""Build the author delivery from this package root. Standard library only."""
import ast
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
LAB = ROOT / 'labs/foundations-service-lab'
ARTIFACTS = ROOT / 'artifacts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def snapshot(path, target=None):
    return {'path': target or path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def run_lab():
    result = subprocess.run([sys.executable, '-B', 'verify.py'], cwd=LAB,
                            capture_output=True, text=True, timeout=60)
    if result.returncode or result.stderr:
        raise RuntimeError({'exitCode': result.returncode, 'stderr': result.stderr, 'stdout': result.stdout})
    report = json.loads(result.stdout)
    walk = subprocess.run([sys.executable, '-B', 'causal_walkthrough.py'], cwd=LAB,
                          capture_output=True, text=True, timeout=15)
    if walk.returncode or walk.stderr or walk.stdout != 'cancelled; zero effects; resource closed; worker joined\n':
        raise RuntimeError('walkthrough did not complete as expected')
    regression = subprocess.run([sys.executable, '-B', 'verify_regressions.py'], cwd=LAB,
                                capture_output=True, text=True, timeout=60)
    if regression.returncode or regression.stderr:
        raise RuntimeError('verifier regression failed: '+regression.stderr)
    report['verifierRegressions'] = json.loads(regression.stdout)
    if report['verifierRegressions']['status'] != 'pass':
        raise RuntimeError('regression report did not pass')
    report['regressionCommand'] = {'command': 'python3 -B verify_regressions.py', 'exitCode': regression.returncode}
    report['driverCommand'] = {'command': 'python3 -B verify.py', 'exitCode': result.returncode}
    report['walkthroughCommand'] = {'command': 'python3 -B causal_walkthrough.py', 'exitCode': walk.returncode, 'stdout': walk.stdout}
    report['recordedAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report['limitations'] = ['Finite Python/loopback observations, no scheduler guarantees', 'ControlledJob resource and effects are in-memory models', 'No production exception recovery, HTTP, database or remote-service verification']
    save(ARTIFACTS / 'foundations-service-results.json', report)
    return report


def main():
    syntax = []
    for path in sorted(LAB.glob('*.py')):
        ast.parse(path.read_text(), filename=path.name)
        syntax.append(snapshot(path))
    save(ARTIFACTS / 'python-syntax.json', {'status': 'pass', 'method': 'ast.parse; no bytecode output', 'sourceFiles': syntax})
    report = run_lab()
    manifest = [snapshot(p, p.relative_to(LAB).as_posix()) for p in sorted(LAB.rglob('*')) if p.is_file() and p.name != 'source-manifest.json']
    save(LAB / 'source-manifest.json', {'format': 1, 'scope': 'Source bundle, excluding this manifest', 'files': manifest})
    archive = ARTIFACTS / 'foundations-service-lab.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as output:
        for p in sorted(LAB.rglob('*')):
            if not p.is_file():
                continue
            info = zipfile.ZipInfo('foundations-service-lab/' + p.relative_to(LAB).as_posix(), date_time=(2026, 10, 3, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, p.read_bytes())
    with zipfile.ZipFile(archive) as bundle:
        for p in LAB.rglob('*'):
            if p.is_file():
                assert bundle.read('foundations-service-lab/' + p.relative_to(LAB).as_posix()) == p.read_bytes()
        assert all(not name.startswith('/') and '..' not in name.split('/') for name in bundle.namelist())
    save(ARTIFACTS / 'packaging-check.json', {'status': 'pass', 'zip': snapshot(archive),
         'sourceBytesUnchanged': True, 'licenseBytesUnchanged': True, 'sourceOnly': True,
         'manifestSha256': sha(LAB / 'source-manifest.json'), 'files': len(manifest) + 1})
    print(json.dumps({'status': 'pass', 'archiveSha256': sha(archive), 'python': report['python']}))


if __name__ == '__main__':
    main()
