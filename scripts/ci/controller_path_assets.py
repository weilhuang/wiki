#!/usr/bin/env python3
"""Download only the reviewed official fixture assets into a new private directory."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request

PIN_FILE = Path(__file__).with_name('controller_path_versions.json')
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_parents(path):
    path = Path(path).absolute()
    require('..' not in path.parts, 'parent traversal is forbidden')
    for ancestor in list(path.parents)[::-1] + [path]:
        if ancestor.exists() or ancestor.is_symlink():
            require(not ancestor.is_symlink(), 'symbolic-link ancestor is forbidden')
    return path


def fetch_asset(spec, destination, opener=urllib.request.urlopen):
    destination = safe_parents(destination)
    require(not destination.exists(), 'download destination already exists')
    require(spec['url'].startswith('https://'), 'asset must use HTTPS')
    started = time.monotonic()
    max_bytes = min(spec.get('bytes', spec.get('max_bytes', MAX_ARCHIVE)), MAX_ARCHIVE)
    size = 0
    h256, h512 = hashlib.sha256(), hashlib.sha512()
    # urllib retains normal TLS and proxy validation; signed redirect URLs are not logged.
    with opener(spec['url'], timeout=30) as response, destination.open('xb') as output:
        while True:
            require(time.monotonic() - started <= 150, 'asset download deadline exceeded')
            block = response.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            require(size <= max_bytes, 'asset byte bound exceeded')
            output.write(block)
            h256.update(block)
            h512.update(block)
    require(h256.hexdigest() == spec['sha256'], 'asset SHA256 mismatch')
    if 'sha512' in spec:
        require(h512.hexdigest() == spec['sha512'], 'asset SHA512 mismatch')
    if 'bytes' in spec:
        require(size == spec['bytes'], 'asset size mismatch')
    return {'url': spec['url'], 'sha256': h256.hexdigest(), 'bytes': size}


def extract_envtest(archive, destination):
    destination = safe_parents(destination)
    require(not destination.exists(), 'envtest destination already exists')
    wanted = {'etcd', 'kube-apiserver', 'kubectl'}
    seen = {}
    total = 0
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        require(len(members) <= 100, 'too many archive members')
        for member in members:
            path = Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts,
                    'unsafe archive member path')
            require(member.isdir() or member.isfile(), 'archive links/devices are forbidden')
            if member.isfile():
                total += member.size
                require(0 <= member.size <= 256 * 1024 * 1024 and total <= MAX_EXPANDED,
                        'expanded archive bound exceeded')
                if path.name in wanted:
                    require(path.name not in seen, 'duplicate envtest executable')
                    seen[path.name] = member
        require(set(seen) == wanted, 'envtest executable inventory mismatch')
        destination.mkdir(mode=0o700)
        hashes = {}
        for name, member in sorted(seen.items()):
            stream = tar.extractfile(member)
            require(stream is not None, 'missing archive stream')
            output = destination / name
            with stream, output.open('xb') as file:
                remaining = member.size
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    require(bool(block), 'truncated archive member')
                    file.write(block)
                    remaining -= len(block)
                require(not stream.read(1), 'unexpected archive member data')
            output.chmod(0o700)
            hashes[name] = hashlib.sha256(output.read_bytes()).hexdigest()
    return hashes


def version(command):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=15, check=False)
    require(result.returncode == 0, 'tool version command failed')
    require(len(result.stdout.encode()) <= 65536, 'tool version output bound exceeded')
    return result.stdout.strip()


def main():
    require(len(sys.argv) == 2, 'usage: controller_path_assets.py <new-private-tool-dir>')
    target = safe_parents(Path(sys.argv[1]))
    require(not target.exists(), 'tool directory already exists')
    require(target.parent.is_dir(), 'tool directory parent is missing')
    target.mkdir(mode=0o700)
    pins = json.loads(PIN_FILE.read_text())
    records = {'scope': pins['scope'], 'pins_sha256': hashlib.sha256(PIN_FILE.read_bytes()).hexdigest(),
               'downloads': {}, 'commands': {}, 'status': 'started'}
    try:
        for name in ['kind', 'kubectl']:
            records['downloads'][name] = fetch_asset(pins[name], target / name)
            (target / name).chmod(0o700)
        archive = target / 'envtest.tar.gz'
        records['downloads']['envtest'] = fetch_asset(pins['envtest'], archive)
        records['executable_sha256'] = extract_envtest(archive, target / 'envtest')
        records['commands']['kind'] = version([str(target / 'kind'), 'version'])
        require(pins['kind_version'] in records['commands']['kind'], 'kind version mismatch')
        records['commands']['kubectl'] = json.loads(version([str(target / 'kubectl'), 'version', '--client=true', '-o', 'json']))
        require(records['commands']['kubectl']['clientVersion']['gitVersion'] == pins['kubernetes'], 'kubectl version mismatch')
        records['commands']['api_server'] = version([str(target / 'envtest/kube-apiserver'), '--version'])
        require(pins['kubernetes'] in records['commands']['api_server'], 'API-server version mismatch')
        records['commands']['etcd'] = version([str(target / 'envtest/etcd'), '--version'])
        records['status'] = 'verified'
    except Exception as error:
        records['status'] = 'failed'
        records['error_type'] = type(error).__name__
        raise
    finally:
        # Contains official URLs and version strings only, never redirects or credentials.
        (target.parent / 'assets.json').write_text(json.dumps(records, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    main()
