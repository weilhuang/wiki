#!/usr/bin/env python3
"""Bounded source identity, test execution and evidence staging for the P0 fixture."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / 'labs/go-cloudnative-controller'
PIN_FILE = Path(__file__).with_name('go_cloudnative_versions.json')
CONTRACT = ROOT / 'labs/go-cloudnative-controller-reviewed.json'
TEMP = Path(os.environ.get('RUNNER_TEMP', '/tmp/wiki-go-cloudnative-ci-tests'))
PRIVATE = TEMP / 'wiki-go-cloudnative-private'
UPLOAD = TEMP / 'wiki-go-cloudnative-upload'
PER_FILE = 8 * 1024 * 1024
TOTAL = 32 * 1024 * 1024
PUBLIC_FILES = {'source-before.json', 'source-after.json', 'provenance.json', 'assets.json',
                'unit.jsonl', 'unit-stage.json', 'integration.jsonl', 'integration-stage.json',
                'envtest-report.json', 'kind-report.json', 'kind-stage.json',
                'dependencies.log', 'dependencies-stage.json', 'module-verify.log', 'module-verify-stage.json',
                'harness-oracle.json', 'harness-oracle-stage.json'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def safe_path(path, must_exist=True):
    path = Path(path).absolute()
    require('..' not in path.parts, 'parent traversal')
    for item in list(path.parents)[::-1] + [path]:
        require(not item.is_symlink(), 'symbolic link in path')
    if must_exist:
        require(path.exists(), 'required path is missing')
    return path


def bounded_bytes(path, maximum=PER_FILE):
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum,
                'evidence is not a bounded regular file')
        chunks, total = [], 0
        while True:
            block = os.read(fd, min(65536, maximum + 1 - total))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            require(total <= maximum, 'evidence grew beyond bound')
        after = os.fstat(fd)
        require((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                'evidence changed while reading')
        return b''.join(chunks)
    finally:
        os.close(fd)


def source_identity():
    contract = json.loads(bounded_bytes(CONTRACT))
    require(contract.get('scope') == 'real-envtest-api-and-single-node-kind-teaching-controller', 'reviewed manifest scope differs')
    expected = contract['source_sha256']
    critical = {'scripts/ci/go_cloudnative_ci.py', 'scripts/ci/go_cloudnative_assets.py',
                'scripts/ci/go_cloudnative_versions.json', 'scripts/ci/test_go_cloudnative_ci.py',
                '.github/workflows/go-cloudnative-bootstrap.yml'}
    require(critical <= set(expected), 'critical wrapper source missing from identity')
    require(expected and all(isinstance(k, str) and re.fullmatch(r'[a-zA-Z0-9_./-]+', k)
                             and not k.startswith('/') and '..' not in k.split('/')
                             and re.fullmatch('[a-f0-9]{64}', v) for k, v in expected.items()),
            'invalid reviewed source manifest')
    require(all(k.startswith(('labs/go-cloudnative-controller/', 'scripts/ci/', '.github/workflows/'))
                for k in expected), 'source manifest outside allowed scope')
    actual = {name: hashlib.sha256(bounded_bytes(ROOT / name)).hexdigest() for name in sorted(expected)}
    require(actual == expected, 'reviewed source bytes changed')
    require(contract.get('source_id') == source_id(actual), 'contract source ID differs')
    lab_files = set()
    for file in safe_path(LAB).rglob('*'):
        require(not file.is_symlink(), 'symlink in lab source')
        if file.is_file():
            lab_files.add(file.relative_to(ROOT).as_posix())
    require(lab_files == {k for k in expected if k.startswith('labs/go-cloudnative-controller/')},
            'unexpected or missing lab source file')
    return actual


def source_id(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def prepare():
    require(not sys.flags.optimize and not os.environ.get('PYTHONOPTIMIZE'), 'optimized Python forbidden')
    safe_path(TEMP)
    safe_path(PRIVATE, False)
    safe_path(UPLOAD, False)
    require(not PRIVATE.exists() and not UPLOAD.exists(), 'pre-existing evidence directory')
    before = source_identity()
    PRIVATE.mkdir(mode=0o700)
    write_json(PRIVATE / 'source-before.json', before)
    write_json(PRIVATE / 'provenance.json', {
        'source_id': source_id(before), 'prepared_monotonic': time.monotonic(),
        'checkout_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'pr_head_sha': os.environ.get('PR_HEAD_SHA'), 'pr_base_sha': os.environ.get('PR_BASE_SHA'),
        'repository': os.environ.get('GITHUB_REPOSITORY'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
        'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'contract_sha256': hashlib.sha256(bounded_bytes(CONTRACT)).hexdigest(),
        'scope': 'real-envtest-api-and-single-node-kind-teaching-controller',
    })


def test_events(raw, expected):
    terminal, packages = {}, {}
    for line in raw.decode('utf-8').splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        action, package, name = event.get('Action'), event.get('Package'), event.get('Test')
        require(action not in ('fail', 'skip', 'build-fail'), 'failed/skipped Go test or package')
        if action == 'pass':
            target = terminal if name else packages
            key = (package, name) if name else package
            require(key not in target, 'duplicate terminal Go event')
            target[key] = True
    required = {(package, name) for package, names in expected.items() for name in names}
    require(required and required <= set(terminal), 'missing required Go test outcome')
    require(set(expected) <= set(packages), 'missing required package pass')
    return [{'package': p, 'test': n, 'status': 'pass'} for p, n in sorted(required)]


def run_command(argv, env, stdout_path, deadline_seconds):
    require(not stdout_path.exists(), 'command output already exists')
    started = time.monotonic()
    result = {'command': argv, 'status': 'fail', 'exit_code': None, 'timed_out': False,
              'output_bound_exceeded': False, 'process_group_cleanup': False}
    process = subprocess.Popen(argv, cwd=LAB, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    total = 0
    try:
        with stdout_path.open('xb') as output:
            while selector.get_map():
                remaining = deadline_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    result['timed_out'] = True
                    raise TimeoutError('bounded command exceeded deadline')
                for key, _ in selector.select(min(remaining, 0.5)):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(data)
                    if total > PER_FILE:
                        result['output_bound_exceeded'] = True
                        raise ValueError('command output exceeded bound')
                    output.write(data)
            result['exit_code'] = process.wait(timeout=max(0.1, deadline_seconds - (time.monotonic() - started)))
            require(result['exit_code'] == 0, 'command failed')
            result['status'] = 'pass'
    except BaseException as error:
        result['error_type'] = type(error).__name__
        raise
    finally:
        selector.close()
        process.stdout.close()
        # Only the session/process group created above is eligible for termination.
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            result['process_group_cleanup'] = True
        else:
            os.killpg(process.pid, signal.SIGTERM)
            end = time.monotonic() + 5
            while time.monotonic() < end:
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                result['process_group_cleanup'] = True
            # A nominal success with leftover child processes is a lifecycle failure.
            result['status'] = 'fail'
        if result['exit_code'] is None and process.returncode is not None:
            result['exit_code'] = process.returncode
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        result['output_bytes'] = min(total, PER_FILE)
        write_json(stdout_path.with_name(stdout_path.stem + '-stage.json'), result)
    require(result['status'] == 'pass' and result['process_group_cleanup'], 'owned command processes did not cleanly exit')
    return result


def run_go(stage):
    require(stage in ('unit', 'integration'), 'unknown Go stage')
    safe_path(PRIVATE)
    before = json.loads(bounded_bytes(PRIVATE / 'source-before.json'))
    require(source_identity() == before, 'source changed before Go run')
    inventory = json.loads(bounded_bytes(LAB / 'test-inventory.json'))
    pins = json.loads(bounded_bytes(PIN_FILE))
    command = ['go', 'test', '-json', '-count=1', '-p=1', '-timeout=150s']
    env = {**os.environ, 'GOTOOLCHAIN': 'local', 'GOWORK': 'off', 'GOMAXPROCS': '2', 'GOMEMLIMIT': '512MiB',
           'GOFLAGS': '-mod=readonly -p=1 -trimpath', 'CGO_ENABLED': '0', 'PYTHONDONTWRITEBYTECODE': '1',
           'P0_SOURCE_ID': source_id(before)}
    if stage == 'unit':
        oracle = run_command([sys.executable, '-B', 'scripts/check_kind_oracle.py', '--source-id', source_id(before)],
                             env, PRIVATE / 'harness-oracle.json', 15)
        oracle['source_id'] = source_id(before)
        write_json(PRIVATE / 'harness-oracle-stage.json', oracle)
        command += ['./api/...', './internal/controller/...', './cmd/operand/...']
    else:
        command += ['-tags=integration', './test/integration']
        env.update(P0_ENVTEST='1', KUBEBUILDER_ASSETS=str(PRIVATE / 'tools/envtest'),
                   P0_ENVTEST_REPORT=str(PRIVATE / 'envtest-report.json'))
        env.pop('USE_EXISTING_CLUSTER', None)
        env.pop('KUBECONFIG', None)
    version = subprocess.check_output(['go', 'version'], text=True, env=env, timeout=15)
    require(('go' + pins['go'] + ' linux/amd64') in version, 'wrong Go toolchain')
    result = run_command(command, env, PRIVATE / (stage + '.jsonl'), 180)
    try:
        result['tests'] = test_events(bounded_bytes(PRIVATE / (stage + '.jsonl')), inventory[stage])
        result['source_id'] = source_id(before)
    except Exception as error:
        result['status'] = 'fail'
        result['validation_error_type'] = type(error).__name__
        raise
    finally:
        write_json(PRIVATE / (stage + '-stage.json'), result)


def dependencies():
    safe_path(PRIVATE)
    before = json.loads(bounded_bytes(PRIVATE / 'source-before.json'))
    require(source_identity() == before, 'source changed before dependency check')
    env = {**os.environ, 'GOTOOLCHAIN': 'local', 'GOWORK': 'off', 'GOMAXPROCS': '2',
           'GOMEMLIMIT': '512MiB', 'GOFLAGS': '-mod=readonly -p=1 -trimpath', 'CGO_ENABLED': '0'}
    run_command(['go', 'mod', 'download'], env, PRIVATE / 'dependencies.log', 180)
    run_command(['go', 'mod', 'verify'], env, PRIVATE / 'module-verify.log', 60)
    require(source_identity() == before, 'dependency resolution changed frozen source')


def run_kind():
    safe_path(PRIVATE)
    before = json.loads(bounded_bytes(PRIVATE / 'source-before.json'))
    require(source_identity() == before, 'source changed before kind')
    provenance = json.loads(bounded_bytes(PRIVATE / 'provenance.json'))
    elapsed = time.monotonic() - provenance['prepared_monotonic']
    require(0 <= elapsed <= 23 * 60 - 780, 'not enough job time remains for the complete kind phase and cleanup')
    pins = json.loads(bounded_bytes(PIN_FILE))
    env = {**os.environ, 'GOTOOLCHAIN': 'local', 'GOWORK': 'off', 'GOMAXPROCS': '2',
           'GOMEMLIMIT': '512MiB', 'PYTHONDONTWRITEBYTECODE': '1',
           'P0_KIND': str(PRIVATE / 'tools/kind'), 'P0_KUBECTL': str(PRIVATE / 'tools/kubectl'),
           'P0_NODE_IMAGE': pins['kind_node_image']}
    env.pop('KUBECONFIG', None)
    env.pop('USE_EXISTING_CLUSTER', None)
    result = run_command([sys.executable, '-B', 'scripts/kind_acceptance.py',
                          '--evidence-dir', str(PRIVATE / 'kind'),
                          '--source-id', source_id(before)], env, PRIVATE / 'kind.log', 750)
    result['source_id'] = source_id(before)
    write_json(PRIVATE / 'kind-stage.json', result)


def exact_cases(rows, required):
    require(isinstance(rows, list) and len(rows) == len(required), 'case inventory length differs')
    ids = [row.get('id') for row in rows]
    require(len(set(ids)) == len(ids) and set(ids) == set(required), 'missing/duplicate/unknown case')
    require(all(row.get('status') == 'pass' for row in rows), 'case is not pass')


# Variable poll counts are allowed; every phase must retain its essential operation types.
COMMAND_COVERAGE = {
    'ToolVersions': {'go:version', 'kind:version', 'kubectl:version', 'docker:version'},
    'BuildLocalImages': {'go:build', 'docker:build', 'docker:image inspect'},
    'OwnedClusterCreated': {'kind:get clusters', 'kind:create cluster', 'kind:load docker-image', 'kubectl:version', 'kubectl:apply', 'kubectl:wait'},
    'ManagerNamespacedRBAC': {'kubectl:apply', 'kubectl:rollout', 'kubectl:get'},
    'OwnedDeploymentService': {'kubectl:apply', 'kubectl:get'},
    'ReadyPodAndCurrentCondition': {'kubectl:get'},
    'HTTPThroughServiceDNS': {'kubectl:apply', 'kubectl:get', 'kubectl:logs'},
    'DriftRepaired': {'kubectl:patch', 'kubectl:get'},
    'DeletedChildRecreated': {'kubectl:delete', 'kubectl:get'},
    'ControllerRestartConverges': {'kubectl:scale', 'kubectl:patch', 'kubectl:rollout', 'kubectl:get', 'kubectl:apply', 'kubectl:logs'},
    'OwnerGarbageCollection': {'kubectl:delete', 'kubectl:get'},
    'DiagnosticsCollected': {'kubectl:logs', 'kubectl:get'},
    'OwnedClusterRemoved': {'kind:delete cluster', 'kind:get clusters'},
    'OwnedImagesRemoved': {'docker:image inspect', 'docker:image rm'},
}


def validate_kind_commands(cluster, required):
    import math
    require(set(required) == set(COMMAND_COVERAGE), 'command-bearing case contract differs')
    commands = cluster.get('commands', [])
    require(0 < len(commands) <= 2000 and [c['id'] for c in commands] == list(range(1, len(commands) + 1)), 'command identity sequence differs')
    owner = cluster['lifecycle']['cluster_name']
    tags = set(cluster['lifecycle']['image_tags'])
    suffix = owner.removeprefix('wiki-p0-')
    require(re.fullmatch('[a-f0-9]{12}', suffix) and cluster.get('run_id') == suffix
            and cluster['lifecycle'].get('namespace') == 'p0-lab'
            and tags == {'wiki-p0-manager-'+suffix+':local', 'wiki-p0-operand-'+suffix+':local'},
            'owned run and image identities differ')
    coverage = {case: set() for case in required}
    order = {case: i for i, case in enumerate(required)}
    observed_order, essential, rejected = [], [], []
    for command in commands:
        fields = {'id', 'case_id', 'argv', 'timeout_seconds', 'elapsed_seconds', 'exit_code',
                  'stdout_sha256', 'stderr_sha256', 'stdout_tail', 'stderr_tail',
                  'stdout_bytes', 'stderr_bytes', 'stdin_bytes', 'stdin_sha256',
                  'allow_failure', 'expected_failure', 'output_limit_bytes'}
        require(fields <= command.keys(), 'incomplete command record')
        case = command['case_id']
        require(case in coverage, 'command has unknown phase')
        observed_order.append(order[case])
        argv = command['argv']
        require(isinstance(argv, list) and 1 < len(argv) <= 80
                and all(isinstance(a, str) and '\0' not in a and len(a) <= 65536 for a in argv), 'invalid command argv')
        require(type(command['exit_code']) is int and command['exit_code'] in (0, 1)
                and not command.get('error'), 'subprocess did not have an eligible outcome')
        for key in ['timeout_seconds', 'elapsed_seconds']:
            require(type(command[key]) in (int, float) and math.isfinite(command[key]) and command[key] >= 0, 'invalid command duration')
        require(0 < command['timeout_seconds'] <= 150
                and command['elapsed_seconds'] <= command['timeout_seconds'] + 3, 'command time bound differs')
        require(command['output_limit_bytes'] == 524288, 'command output cap differs')
        require(all(type(command[k]) is int and command[k] >= 0 for k in ['stdout_bytes', 'stderr_bytes', 'stdin_bytes']), 'invalid command byte counts')
        require(command['stdout_bytes'] + command['stderr_bytes'] <= 524288 and command['stdin_bytes'] <= 65536, 'command byte bound exceeded')
        for channel in ['stdout', 'stderr', 'stdin']:
            require(isinstance(command[channel+'_sha256'], str)
                    and re.fullmatch('[a-f0-9]{64}', command[channel+'_sha256']), 'missing stream identity')
            if channel != 'stdin':
                tail = command[channel+'_tail']
                require(isinstance(tail, str) and len(tail.encode()) <= 12000, 'unbounded command tail')
                if command[channel+'_bytes'] <= 4000:
                    require(len(tail.encode()) == command[channel+'_bytes']
                            and hashlib.sha256(tail.encode()).hexdigest() == command[channel+'_sha256'], 'short stream identity differs')
        tool = Path(argv[0]).name
        args = argv[1:]
        if tool == 'kubectl':
            if args[:2] == ['version', '--client=true']:
                verb = 'version'
            else:
                require(len(args) >= 10 and args[0] == '--kubeconfig' and args[1].endswith('/kubeconfig')
                        and args[2:6] == ['--context', 'kind-'+owner, '--request-timeout=10s', '--cache-dir']
                        and args[6] == str(Path(args[1]).parent / 'kubectl-cache')
                        and args[7:9] == ['-n', 'p0-lab'],
                        'kubectl is not scoped to the owned cluster')
                args = args[9:]
                if args and args[0].startswith('--as='):
                    require(case == 'ManagerNamespacedRBAC' and args[0] == '--as=system:serviceaccount:p0-lab:manager', 'unexpected impersonation')
                    args = args[1:]
                require(bool(args), 'kubectl verb missing')
                verb = args[0]
                require(verb in {'version', 'apply', 'wait', 'get', 'rollout', 'logs', 'patch', 'delete', 'scale'}, 'unexpected kubectl operation')
                if case == 'OwnerGarbageCollection' and verb == 'delete':
                    require(args[1] == 'appservice/sample' and '--cascade=background' in args, 'GC proof directly deletes dependents')
            op = 'kubectl:' + verb
        elif tool == 'kind':
            op = 'kind:' + (' '.join(args[:2]) if args[0] != 'version' else 'version')
            require(op in {'kind:version', 'kind:get clusters', 'kind:create cluster', 'kind:load docker-image', 'kind:delete cluster'}, 'unexpected kind operation')
            if args[0] in ('create', 'load', 'delete'):
                require('--name' in args and args[args.index('--name')+1] == owner, 'kind mutation targets another cluster')
                essential.append(op)
            if args[0] == 'create':
                require('--image' in args and args[args.index('--image')+1] == cluster['node_image'], 'kind image differs')
        elif tool == 'docker':
            op = 'docker:' + (' '.join(args[:2]) if args[0] == 'image' else args[0])
            require(op in {'docker:version', 'docker:build', 'docker:image inspect', 'docker:image rm'}, 'unexpected Docker operation')
            if args[0] == 'build':
                require('--network=none' in args and '-t' in args and args[args.index('-t')+1] in tags, 'Docker build is not owned/offline')
                essential.append(op+':'+args[args.index('-t')+1])
            elif args[0] == 'image':
                require(args[-1] in tags, 'Docker image operation is not owned')
                if args[1] == 'rm':
                    require(len(args) == 3, 'unexpected image delete arguments')
                    essential.append(op+':'+args[-1])
        elif tool == 'go':
            require(args[0] in ('version', 'build'), 'unexpected Go operation')
            op = 'go:' + args[0]
            if args[0] == 'build':
                require('-mod=readonly' in args and '-trimpath' in args
                        and args[-1] in ('./cmd/manager', './cmd/operand'), 'Go build scope differs')
                essential.append(op+':'+args[-1])
        else:
            raise ValueError('unexpected command executable')
        require(op in COMMAND_COVERAGE[case], 'operation is associated with the wrong case')
        coverage[case].add(op)
        if command['exit_code']:
            require(command['allow_failure'] is True, 'unclassified nonzero command')
            expected, stderr = command['expected_failure'], command['stderr_tail']
            if expected == 'Kubernetes API Forbidden for manager service account':
                require(case == 'ManagerNamespacedRBAC' and 'Forbidden' in stderr
                        and op == 'kubectl:get' and '--as=system:serviceaccount:p0-lab:manager' in argv,
                        'RBAC rejection has wrong identity')
                resource = args[1] + (':p0-other' if args[2:4] == ['-n', 'p0-other'] else '')
                require(resource in {'secrets', 'deployments:p0-other', 'namespaces'}, 'unexpected denied resource')
                rejected.append('rbac:'+resource)
            elif expected in {'No such image or No such object for the generated image tag',
                              'No such image or No such object proves generated tag initially absent'}:
                initial = expected.endswith('initially absent')
                require(case == ('BuildLocalImages' if initial else 'OwnedImagesRemoved')
                        and op == 'docker:image inspect' and argv[-1] in tags
                        and ('No such image' in stderr or 'No such object' in stderr), 'image absence has wrong identity')
                rejected.append(('image-initial:' if initial else 'image-final:')+argv[-1])
            else:
                raise ValueError('unknown expected command rejection')
    expected_rejections = {'rbac:secrets', 'rbac:deployments:p0-other', 'rbac:namespaces'}
    expected_rejections |= {'image-initial:'+tag for tag in tags} | {'image-final:'+tag for tag in tags}
    require(len(rejected) == len(expected_rejections) and set(rejected) == expected_rejections,
            'required rejection/absence evidence missing or duplicated')
    require(observed_order == sorted(observed_order), 'command phase order differs')
    require(all(coverage[k] == COMMAND_COVERAGE[k] for k in required), 'required command coverage missing')
    expected = {'kind:create cluster', 'kind:load docker-image', 'kind:delete cluster',
                'go:build:./cmd/manager', 'go:build:./cmd/operand'}
    expected |= {'docker:build:'+tag for tag in tags} | {'docker:image rm:'+tag for tag in tags}
    require(len(essential) == len(expected) and set(essential) == expected, 'missing or duplicate essential mutation command')


def validate_reports(staged, before):
    require(PUBLIC_FILES | {'kind.log', 'kind-manager.log', 'kind-events.json', 'kind-resources.json'} <= set(staged), 'required bounded evidence file missing')
    read = lambda name: json.loads(staged[name])
    pins = json.loads(bounded_bytes(PIN_FILE))
    inventory = json.loads(bounded_bytes(LAB / 'test-inventory.json'))
    identity = source_id(before)
    require(read('source-before.json') == read('source-after.json') == before, 'source changed across execution')
    provenance = read('provenance.json')
    require(provenance['source_id'] == identity and provenance['repository'] == 'weilhuang/wiki'
            and provenance['scope'] == 'real-envtest-api-and-single-node-kind-teaching-controller',
            'provenance scope mismatch')
    for name in ['checkout_sha', 'pr_head_sha', 'pr_base_sha']:
        require(bool(re.fullmatch('[a-f0-9]{40}', provenance.get(name, ''))), 'missing Git identity')
    assets = read('assets.json')
    require(assets['status'] == 'verified', 'official assets were not verified')
    require(assets['pins_sha256'] == hashlib.sha256(bounded_bytes(PIN_FILE)).hexdigest(), 'asset pins differ')
    for name in ['kind', 'kubectl', 'envtest']:
        require(assets['downloads'][name]['sha256'] == pins[name]['sha256'], 'asset identity differs')
    for stage in ['dependencies', 'module-verify', 'harness-oracle', 'unit', 'integration', 'kind']:
        result = read(stage + '-stage.json')
        require(result['status'] == 'pass' and result['exit_code'] == 0
                and result['process_group_cleanup'] is True and not result['timed_out']
                and not result['output_bound_exceeded'], 'command stage did not pass cleanly')
    for stage in ['unit', 'integration']:
        result = read(stage + '-stage.json')
        require(result['source_id'] == identity, 'Go result source differs')
        require(result['tests'] == test_events(staged[stage + '.jsonl'], inventory[stage]),
                'Go test inventory/result differs')
    oracle = read('harness-oracle.json')
    require(oracle.get('schema_version') == 1 and oracle.get('status') == 'pass' and oracle.get('exit_code') == 0
            and oracle.get('source_id') == identity and oracle.get('layer') == 'pure-harness-oracle'
            and read('harness-oracle-stage.json')['source_id'] == identity, 'harness oracle identity/outcome differs')
    exact_cases(oracle['cases'], inventory['harness_unit'])
    api = read('envtest-report.json')
    require(api.get('schema_version') == 1 and api.get('status') == 'pass'
            and api.get('exit_code') == 0 and api.get('source_id') == identity
            and api.get('layer') == 'envtest-real-manager' and api.get('server_version') == pins['kubernetes'],
            'envtest report identity/outcome differs')
    names = [t.split('/', 1)[1] for tests in inventory['integration'].values() for t in tests if '/' in t]
    exact_cases(api['cases'], names)
    require('simulated' in api.get('readiness_inputs', ''), 'envtest readiness boundary missing')
    events = api['lifecycle']
    require(not any(e.get('status') == 'fail' for e in events), 'envtest lifecycle failure')
    for event in ['control_plane_start', 'server_version', 'manager_start', 'manager_cache_sync', 'manager_stop', 'control_plane_stop']:
        require(any(e.get('event') == event and e.get('status') == 'pass' for e in events), 'envtest lifecycle proof missing')
    starts = sum(e.get('event') == 'manager_start' and e.get('status') == 'pass' for e in events)
    stops = sum(e.get('event') == 'manager_stop' and e.get('status') == 'pass' for e in events)
    syncs = sum(e.get('event') == 'manager_cache_sync' and e.get('status') == 'pass' for e in events)
    require(starts >= 2 and starts == stops == syncs, 'manager restart/stop inventory differs')
    cluster = read('kind-report.json')
    require(cluster.get('schema_version') == 1 and cluster.get('status') == 'pass'
            and cluster.get('exit_code') == 0 and cluster.get('source_id') == identity
            and cluster.get('layer') == 'kind-real-workloads' and cluster.get('node_image') == pins['kind_node_image'],
            'kind report identity/outcome differs')
    require(not cluster.get('failure') and not cluster.get('cleanup_or_diagnostics_failures'), 'kind has preserved failures')
    exact_cases(cluster['cases'], inventory['kind'])
    lifecycle = cluster['lifecycle']
    require(re.fullmatch(r'wiki-p0-[a-f0-9]+', lifecycle['cluster_name']) is not None, 'unexpected owned cluster name')
    require(len(lifecycle['image_tags']) == 2 and len(set(lifecycle['image_tags'])) == 2, 'image inventory differs')
    events = lifecycle['events']
    require(not any(e.get('status') == 'fail' for e in events), 'kind lifecycle failure')
    require(any(e.get('event') == 'cluster_delete' and e.get('status') == 'pass'
                and e.get('name') == lifecycle['cluster_name'] for e in events), 'owned cluster removal missing')
    initial = [e.get('tag') for e in events if e.get('event') == 'image_absence_before_build' and e.get('status') == 'pass']
    require(len(initial) == 2 and set(initial) == set(lifecycle['image_tags']), 'owned image absence before build missing')
    require({e.get('tag') for e in events if e.get('event') == 'image_delete' and e.get('status') == 'pass'} == set(lifecycle['image_tags']),
            'owned image removals missing')
    require(any(e.get('event') == 'private_workspace_remove' and e.get('status') == 'pass'
                and e.get('kubeconfig_absent') is True for e in events), 'private kubeconfig cleanup missing')
    require(read('kind-stage.json')['source_id'] == identity, 'kind stage source differs')
    validate_kind_commands(cluster, inventory['kind'])
    return {'source_id': identity, 'unit_required': sum(map(len, inventory['unit'].values())),
            'envtest_cases': len(names), 'kind_cases': len(inventory['kind']),
            'synthetic_harness_cases': len(inventory['harness_unit']),
            'scope': provenance['scope']}


def normalize_for_upload(data):
    text = data.decode('utf-8')
    require(not re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text), 'private key content refused')
    require(not re.search(r'(?i)client-key-data|client-certificate-data|certificate-authority-data|authorization:\s*bearer\s+\S+', text),
            'credential/configuration content refused')
    require(not re.search(r'"kind"\s*:\s*"Secret"', text), 'Secret object refused')
    for actual, alias in [(str(PRIVATE), '<private>'), (str(ROOT), '<repo>'), (str(TEMP), '<runner-temp>')]:
        text = text.replace(actual, alias)
    text = re.sub(r'/tmp/wiki-p0-[a-f0-9]+-[A-Za-z0-9_-]+', '<owned-kind-private>', text)
    return text.encode('utf-8')


def collect():
    safe_path(TEMP)
    safe_path(UPLOAD, False)
    require(not UPLOAD.exists(), 'upload path already exists; refusing pre-existing content')
    # Never enable upload until a complete bounded staging directory has been validated.
    UPLOAD.mkdir(mode=0o700)
    staged, raw_snapshot, identities, error = {}, {}, {}, None
    try:
        safe_path(PRIVATE)
        before = json.loads(bounded_bytes(PRIVATE / 'source-before.json'))
        after = source_identity()
        write_json(PRIVATE / 'source-after.json', after)
        mapping = {name: PRIVATE / name for name in PUBLIC_FILES}
        mapping.update({'kind.log': PRIVATE / 'kind.log',
                        'kind-report.json': PRIVATE / 'kind/kind-report.json',
                        'kind-manager.log': PRIVATE / 'kind/manager.log',
                        'kind-events.json': PRIVATE / 'kind/events.json',
                        'kind-resources.json': PRIVATE / 'kind/resources.json'})
        for name, path in sorted(mapping.items()):
            if not path.exists() and not path.is_symlink():
                continue
            raw = bounded_bytes(path)
            body = normalize_for_upload(raw)
            require(len(body) <= PER_FILE, 'normalized file exceeds bound')
            raw_snapshot[name] = raw
            staged[name] = body
            identities[name] = {'raw_sha256': hashlib.sha256(raw).hexdigest(), 'raw_bytes': len(raw),
                                'upload_sha256': hashlib.sha256(body).hexdigest(), 'upload_bytes': len(body),
                                'bytes': len(body)}
        require(sum(map(len, raw_snapshot.values())) <= TOTAL - 65536, 'raw snapshot exceeds aggregate bound')
        require(sum(map(len, staged.values())) <= TOTAL - 65536, 'upload exceeds aggregate bound')
        # Validate original stream hashes against the same bounded byte snapshots read above.
        # Path redaction changes displayed tails; it must not be compared with raw stream identities.
        details = validate_reports(raw_snapshot, before)
        validation = {'status': 'pass', **details}
    except Exception as exc:
        error = exc
        validation = {'status': 'fail', 'error_type': type(exc).__name__,
                      'reason': normalize_for_upload(str(exc).encode()).decode()[:500]}
    # Already checked bytes are staged, never re-read from mutable source paths.
    for name, data in staged.items():
        (UPLOAD / name).write_bytes(data)
    validation['files'] = identities
    validation['normalization'] = 'Original bounded in-memory snapshots validated before owned-path redaction. Each file retains raw_sha256 and upload_sha256. Command stream byte counts and SHA256 describe the original streams; displayed tails may contain redacted paths. No outcome rewrite.'
    write_json(UPLOAD / 'validation.json', validation)
    require(sum(p.stat().st_size for p in UPLOAD.iterdir()) <= TOTAL, 'staged aggregate bound exceeded')
    output = os.environ.get('GITHUB_OUTPUT')
    if output:
        with open(output, 'a', encoding='utf-8') as stream:
            stream.write('upload_ready=true\n')
    if error is not None:
        raise ValueError('P0 evidence gate failed; bounded diagnostics staged') from error


def main():
    require(len(sys.argv) == 2, 'one action required')
    if sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'dependencies':
        dependencies()
    elif sys.argv[1] == 'kind':
        run_kind()
    elif sys.argv[1] == 'collect':
        collect()
    elif sys.argv[1] in ('unit', 'integration'):
        run_go(sys.argv[1])
    else:
        raise ValueError('unknown action')


if __name__ == '__main__':
    main()
