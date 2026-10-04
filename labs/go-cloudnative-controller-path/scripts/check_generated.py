#!/usr/bin/env python3
"""Regenerate pinned CRD/DeepCopy in an owned temporary copy and compare exact bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import stat
from check_mutants import run

HERE = Path(__file__).resolve().parents[1]
FILES = ['api/v1alpha1/zz_generated.deepcopy.go', 'config/crd/lab.wiki.example_appservices.yaml']
GENERATOR = 'sigs.k8s.io/controller-tools/cmd/controller-gen@v0.22.0'
COMMAND = ['go', 'run', GENERATOR, 'object', 'crd', 'paths=./api/...', 'output:crd:artifacts:config=config/crd']


def tree(root):
    result = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode) or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError('nonregular or linked generator input/output')
        name = path.relative_to(root).as_posix()
        result[name] = {'mode':stat.S_IMODE(info.st_mode), 'kind':'file' if path.is_file() else 'directory'}
        if path.is_file(): result[name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--source-id', required=True); args = parser.parse_args()
    report = {'schema_version': 1, 'source_id': args.source_id, 'layer': 'pinned-controller-gen-golden',
              'generator': GENERATOR, 'status': 'fail', 'exit_code': 1}
    try:
        original = tree(HERE)
        goldens = {name:(HERE/name).read_bytes() for name in FILES}
        with tempfile.TemporaryDirectory(prefix='controller-generate-') as directory:
            if stat.S_IMODE(Path(directory).stat().st_mode)!=0o700: raise ValueError('generator temporary root is not private0700')
            work = Path(directory) / 'lab'; shutil.copytree(HERE, work)
            if not all(p.stat().st_uid==os.getuid() and p.stat().st_mode & stat.S_IWUSR for p in [work,*work.rglob('*')]):
                raise ValueError('generator copy is not owned and writable')
            before = tree(work)
            if before!=original: raise ValueError('generator copy differs before execution')
            for name in FILES: (work/name).unlink()
            if any((work/name).exists() or (work/name).is_symlink() for name in FILES): raise ValueError('old outputs remain')
            report.update(command=COMMAND, outputs_removed_before_run=True, private_root_mode=0o700)
            code, raw = run(COMMAND, work, time.monotonic()+120, offline=False)
            report['generator_output'] = raw.decode('utf-8', errors='replace')
            report['generator_exit_code'] = code
            if code != 0: raise ValueError('pinned generator did not exit successfully')
            after = tree(work)
            if set(after)!=set(before): raise ValueError('missing or unexpected generated paths')
            if any(after[name]!=before[name] for name in before if name not in FILES):
                raise ValueError('generator modified an input or unrelated source path')
            rows = []
            for name in FILES:
                info = (work/name).lstat()
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o644 or info.st_uid!=os.getuid():
                    raise ValueError('fresh generated file is not owned regular0644')
                actual, expected = (work/name).read_bytes(), goldens[name]
                rows.append({'path': name, 'sha256': hashlib.sha256(actual).hexdigest(), 'expected_sha256': hashlib.sha256(expected).hexdigest(), 'identical': actual == expected, 'fresh_regular_file':True, 'mode':0o644})
            report['files'] = rows
            if not all(row['identical'] for row in rows): raise ValueError('generated CRD or DeepCopy differs from committed bytes')
        if tree(HERE)!=original: raise ValueError('original source changed during generator check')
        report.update(status='pass', exit_code=0, temporary_copy_removed=True, source_tree_unchanged=True, unexpected_outputs=False)
    except Exception as exc:
        report['failure'] = str(exc)
    print(json.dumps(report))
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
