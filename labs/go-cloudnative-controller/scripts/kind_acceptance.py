#!/usr/bin/env python3
"""Bounded one-cluster acceptance. Run only in the separately approved disposable CI job."""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import shutil
import signal
import selectors
import subprocess
import tempfile
import time
import uuid

NODE_IMAGE = 'kindest/node:v1.37.0@sha256:a1ed56cfb0e7b93589bdf97c8cd566405a265939e3620fc4f5de89adff580ae5'
HERE = pathlib.Path(__file__).resolve().parents[1]
REQUIRED = json.loads((HERE / 'test-inventory.json').read_text())['kind']


def current_rollout(a, d, pods):
    """Independent acceptance oracle; missing or stale evidence is never Ready."""
    if not a or not d:
        return False
    c = next((v for v in a.get('status', {}).get('conditions', []) if v['type'] == 'Ready'), {})
    ds = d.get('status', {})
    candidates = [p for p in pods if p['metadata'].get('labels', {}).get('lab.wiki.example/owner-uid') == a['metadata']['uid']]
    ready_pods = [p for p in candidates if p['status'].get('phase') == 'Running' and
                  any(c['type'] == 'Ready' and c['status'] == 'True' for c in p['status'].get('conditions', []))]
    return (c.get('status') == 'True' and c.get('observedGeneration') == a['metadata']['generation'] and
            a['status'].get('observedGeneration') == a['metadata']['generation'] and
            d['spec'].get('replicas') == 1 and d['metadata']['generation'] > 0 and
            ds.get('observedGeneration', 0) >= d['metadata']['generation'] and
            ds.get('replicas') == ds.get('updatedReplicas') == ds.get('readyReplicas') == ds.get('availableReplicas') == 1 and
            ds.get('unavailableReplicas', 0) == 0 and len(candidates) == len(ready_pods) == 1 and
            any(v['type'] == 'Available' and v['status'] == 'True' for v in ds.get('conditions', [])) and
            {'app_uid': a['metadata']['uid'], 'deployment_uid': d['metadata']['uid'],
             'pod_uid': ready_pods[0]['metadata']['uid'], 'pod_name': ready_pods[0]['metadata']['name'],
             'generation': a['metadata']['generation']})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--source-id', required=True)
    args = parser.parse_args()
    output = pathlib.Path(args.evidence_dir).absolute()
    if output.exists() or output.is_symlink() or output.parent.resolve() != output.parent:
        raise SystemExit('evidence-dir must be new, with an existing nonsymlink parent')
    if not output.parent.is_dir() or not args.source_id:
        raise SystemExit('missing evidence parent or source ID')
    output.mkdir(mode=0o700)
    run_id = uuid.uuid4().hex[:12]
    cluster = 'wiki-p0-' + run_id
    namespace = 'p0-lab'
    manager_image = 'wiki-p0-manager-' + run_id + ':local'
    operand_image = 'wiki-p0-operand-' + run_id + ':local'
    started = time.monotonic()
    # Main work gets 600 seconds; diagnostics and cleanup get distinct reserved windows.
    work_deadline, diagnostic_deadline, cleanup_deadline = started + 600, started + 630, started + 720
    report = {'schema_version': 1, 'status': 'fail', 'source_id': args.source_id,
              'run_id': run_id, 'layer': 'kind-real-workloads', 'node_image': NODE_IMAGE,
              'cases': [{'id': name, 'status': 'not_run', 'details': ''} for name in REQUIRED],
              'commands': [], 'lifecycle': {'cluster_name': cluster, 'namespace': namespace,
                                          'image_tags': [manager_image, operand_image], 'events': []}}
    active = None
    cluster_attempted = False
    image_attempts = []
    private = pathlib.Path(tempfile.mkdtemp(prefix='wiki-p0-' + run_id + '-'))
    kubeconfig = private / 'kubeconfig'
    report['lifecycle']['kubeconfig_policy'] = 'exclusive temporary file; never uploaded; deleted in finally'
    env = dict(os.environ)
    env['KUBECONFIG'] = str(kubeconfig)
    env['KIND_EXPERIMENTAL_PROVIDER'] = 'docker'
    env.update({'CGO_ENABLED': '0', 'GOOS': 'linux', 'GOARCH': 'amd64',
                'GOTOOLCHAIN': 'local', 'GOMAXPROCS': '2', 'GOFLAGS': '-p=1'})
    tools = {}

    def flush():
        tmp = output / 'kind-report.json.tmp'
        tmp.write_text(json.dumps(report, indent=2) + '\n')
        tmp.replace(output / 'kind-report.json')

    def event(name, status, **details):
        report['lifecycle']['events'].append({'event': name, 'status': status,
                                            'elapsed_seconds': round(time.monotonic() - started, 3), **details})
        flush()

    def command(argv, *, timeout=30, deadline=None, stdin=None, expected_failure=None):
        deadline = work_deadline if deadline is None else deadline
        remaining = deadline - time.monotonic()
        if remaining <= 2:
            raise RuntimeError('reserved phase deadline exhausted')
        limit = min(timeout, remaining - 2)  # Leave two seconds to kill/reap a timed-out group.
        begin = time.monotonic()
        payload = stdin.encode() if stdin is not None else b''
        entry = {'id': len(report['commands']) + 1, 'case_id': active, 'argv': list(map(str, argv)),
                 'timeout_seconds': round(limit, 3), 'allow_failure': expected_failure is not None,
                 'expected_failure': expected_failure, 'output_limit_bytes': 524288,
                 'stdin_bytes': len(payload), 'stdin_sha256': hashlib.sha256(payload).hexdigest()}
        process = None
        streams = {'stdout': bytearray(), 'stderr': bytearray()}
        selector = selectors.DefaultSelector()
        try:
            if len(payload) > 65536:
                raise RuntimeError('known manifest input exceeds 64KiB')
            process = subprocess.Popen(argv, cwd=HERE, env=env, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            for label, stream in [('stdout', process.stdout), ('stderr', process.stderr)]:
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, label)
            offset = 0
            if process.stdin is not None:
                os.set_blocking(process.stdin.fileno(), False)
                selector.register(process.stdin, selectors.EVENT_WRITE, 'stdin')
            while selector.get_map():
                if time.monotonic() - begin >= limit:
                    entry['exit_code'] = 124
                    raise RuntimeError('subprocess timeout; process group will be killed and reaped')
                for key, _ in selector.select(min(.2, max(0, limit - (time.monotonic() - begin)))):
                    if key.data == 'stdin':
                        try:
                            offset += os.write(key.fd, payload[offset:offset + 8192])
                        except BrokenPipeError:
                            offset = len(payload)
                        if offset == len(payload):
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        continue
                    block = os.read(key.fd, 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    room = 524288 - sum(len(v) for v in streams.values())
                    streams[key.data].extend(block[:room])
                    if len(block) > room:
                        entry['exit_code'] = 125
                        entry['output_limit_exceeded'] = True
                        raise RuntimeError('subprocess exceeded 512KiB combined output limit')
            exit_code = process.wait(timeout=max(.01, limit - (time.monotonic() - begin)))
            entry['exit_code'] = exit_code
        except Exception as exc:
            entry.setdefault('exit_code', 127 if isinstance(exc, OSError) else 124 if isinstance(exc, subprocess.TimeoutExpired) else 126)
            entry['error'] = str(exc)
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
            raise
        finally:
            selector.close()
            if process is not None:
                for stream in [process.stdin, process.stdout, process.stderr]:
                    if stream is not None and not stream.closed:
                        stream.close()
            for label, data in streams.items():
                entry[label + '_bytes'] = len(data)
                entry[label + '_sha256'] = hashlib.sha256(data).hexdigest()
                entry[label + '_tail'] = data[-4000:].decode(errors='replace')
            entry['elapsed_seconds'] = round(time.monotonic() - begin, 3)
            report['commands'].append(entry)
            flush()
        result = subprocess.CompletedProcess(argv, exit_code, streams['stdout'].decode(errors='replace'), streams['stderr'].decode(errors='replace'))
        if result.returncode and expected_failure is None:
            raise RuntimeError('command exit %d: %s: %s' % (result.returncode, argv[0], result.stderr[-1500:]))
        return result

    def case(name, fn):
        nonlocal active
        active = name
        row = next(c for c in report['cases'] if c['id'] == name)
        if row['status'] != 'not_run':
            raise RuntimeError('case repeated: ' + name)
        try:
            row['details'] = fn() or 'assertions completed'
            row['status'] = 'pass'
        except Exception as exc:
            row.update(status='fail', details=str(exc))
            raise
        finally:
            flush()
            active = None

    def k(*argv, deadline=None, timeout=20, stdin=None, expected_failure=None):
        return command([tools['kubectl'], '--kubeconfig', str(kubeconfig), '--context', 'kind-' + cluster,
                        '--request-timeout=10s', '--cache-dir', str(private / 'kubectl-cache'), '-n', namespace, *argv], deadline=deadline,
                       timeout=timeout, stdin=stdin, expected_failure=expected_failure)

    def apply(obj):
        return k('apply', '-f', '-', stdin=json.dumps(obj))

    def get(kind, name=None):
        args = ['get', kind]
        if name:
            args.append(name)
        args.extend(['--ignore-not-found', '-o', 'json'])
        raw = k(*args).stdout.strip()
        return json.loads(raw) if raw else None

    def poll(fn, seconds=90):
        until = min(work_deadline, time.monotonic() + seconds)
        while time.monotonic() < until:
            value = fn()
            if value:
                return value
            time.sleep(min(1, max(0, until - time.monotonic())))
        raise AssertionError('observable condition did not converge within %ds' % seconds)

    def owned(obj, uid):
        return bool(obj) and any(o.get('uid') == uid and o.get('controller') is True
                                for o in obj['metadata'].get('ownerReferences', []))

    def ready_state():
        return current_rollout(get('appservice', 'sample'), get('deployment', 'sample'), get('pods')['items'])

    def versions():
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise AssertionError('pinned fixture requires Linux amd64')
        for key, var in [('kind', 'P0_KIND'), ('kubectl', 'P0_KUBECTL')]:
            path = pathlib.Path(os.environ.get(var, ''))
            if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
                raise AssertionError('explicit verified executable required: ' + var)
            tools[key] = str(path)
        if os.environ.get('P0_NODE_IMAGE') != NODE_IMAGE:
            raise AssertionError('P0_NODE_IMAGE differs from frozen digest')
        for key in ['go', 'docker']:
            value = shutil.which(key)
            if not value:
                raise AssertionError('missing executable: ' + key)
            tools[key] = value
        go = command([tools['go'], 'version']).stdout.strip()
        kind = command([tools['kind'], 'version']).stdout.strip()
        kubectl = json.loads(command([tools['kubectl'], 'version', '--client=true', '-o', 'json']).stdout)['clientVersion']['gitVersion']
        docker = command([tools['docker'], 'version', '--format', '{{.Server.Version}}']).stdout.strip()
        if go != 'go version go1.27.1 linux/amd64' or not kind.startswith('kind v0.33.0 ') or kubectl != 'v1.37.0':
            raise AssertionError('tool version mismatch')
        return {'go': go, 'kind': kind, 'kubectl': kubectl, 'docker_server': docker}

    def build_images():
        # Establish cleanup ownership before any generated tag can be written.
        for tag in [manager_image, operand_image]:
            result = command([tools['docker'], 'image', 'inspect', '--format', '{{.Id}}', tag], timeout=5,
                             expected_failure='No such image or No such object proves generated tag initially absent')
            if result.returncode == 0:
                raise AssertionError('generated image tag already exists; refusing to overwrite: ' + tag)
            if 'No such image' not in result.stderr and 'No such object' not in result.stderr:
                raise AssertionError('cannot establish generated image tag absence: ' + tag)
            event('image_absence_before_build', 'pass', tag=tag)
        for target, tag in [('manager', manager_image), ('operand', operand_image)]:
            context = private / target
            context.mkdir()
            command([tools['go'], 'build', '-mod=readonly', '-trimpath', '-buildvcs=false', '-ldflags=-s -w',
                     '-o', str(context / 'app'), './cmd/' + target], timeout=120)
            (context / 'Dockerfile').write_text('FROM scratch\nCOPY app /app\nUSER 65532:65532\nENTRYPOINT ["/app"]\n')
            image_attempts.append(tag)
            event('image_build', 'attempt', tag=tag)
            command([tools['docker'], 'build', '--network=none', '-t', tag, str(context)], timeout=60)
            digest = command([tools['docker'], 'image', 'inspect', '--format', '{{.Id}}', tag]).stdout.strip()
            event('image_build', 'pass', tag=tag, image_id=digest)
        return 'two scratch images built from this module; no registry push'

    def create_cluster():
        nonlocal cluster_attempted
        existing = command([tools['kind'], 'get', 'clusters']).stdout.splitlines()
        if cluster in existing:
            raise AssertionError('generated name already exists; refusing ownership')
        cluster_attempted = True
        event('cluster_create', 'attempt', name=cluster)
        command([tools['kind'], 'create', 'cluster', '--name', cluster, '--image', NODE_IMAGE,
                 '--kubeconfig', str(kubeconfig), '--wait', '100s'], timeout=150)
        event('cluster_create', 'pass', name=cluster)
        version = json.loads(k('version', '-o', 'json').stdout)['serverVersion']['gitVersion']
        if version != 'v1.37.0':
            raise AssertionError('unexpected kind API version: ' + version)
        command([tools['kind'], 'load', 'docker-image', '--name', cluster, manager_image, operand_image], timeout=60)
        k('apply', '-f', str(HERE / 'config' / 'crd' / 'lab.wiki.example_appservices.yaml'))
        k('wait', '--for=condition=Established', '--timeout=30s', 'crd/appservices.lab.wiki.example', timeout=35)
        apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': namespace}})
        apply({'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': 'p0-other'}})
        return {'name': cluster, 'server_version': version}

    def deploy_manager():
        objs = [
            {'apiVersion': 'v1', 'kind': 'ServiceAccount', 'metadata': {'name': 'manager', 'namespace': namespace}},
            {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'Role', 'metadata': {'name': 'manager', 'namespace': namespace}, 'rules': [
                {'apiGroups': ['lab.wiki.example'], 'resources': ['appservices'], 'verbs': ['get', 'list', 'watch']},
                {'apiGroups': ['lab.wiki.example'], 'resources': ['appservices/status'], 'verbs': ['patch']},
                {'apiGroups': ['apps'], 'resources': ['deployments'], 'verbs': ['get', 'list', 'watch', 'create', 'patch']},
                {'apiGroups': [''], 'resources': ['services'], 'verbs': ['get', 'list', 'watch', 'create', 'patch']}]},
            {'apiVersion': 'rbac.authorization.k8s.io/v1', 'kind': 'RoleBinding', 'metadata': {'name': 'manager', 'namespace': namespace},
             'subjects': [{'kind': 'ServiceAccount', 'name': 'manager', 'namespace': namespace}],
             'roleRef': {'apiGroup': 'rbac.authorization.k8s.io', 'kind': 'Role', 'name': 'manager'}},
            {'apiVersion': 'apps/v1', 'kind': 'Deployment', 'metadata': {'name': 'manager', 'namespace': namespace}, 'spec': {
                'replicas': 1, 'strategy': {'type': 'Recreate'}, 'selector': {'matchLabels': {'app': 'p0-manager'}},
                'template': {'metadata': {'labels': {'app': 'p0-manager'}}, 'spec': {
                    'serviceAccountName': 'manager', 'terminationGracePeriodSeconds': 10,
                    'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
                    'containers': [{'name': 'manager', 'image': manager_image, 'imagePullPolicy': 'Never', 'args': ['--namespace=' + namespace],
                                    'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}},
                                    'resources': {'requests': {'cpu': '50m', 'memory': '64Mi'}, 'limits': {'cpu': '300m', 'memory': '192Mi'}},
                                    'readinessProbe': {'httpGet': {'path': '/readyz', 'port': 8081}, 'periodSeconds': 2}}]}}}}]
        for obj in objs:
            apply(obj)
        k('rollout', 'status', 'deployment/manager', '--timeout=80s', timeout=85)
        as_user = '--as=system:serviceaccount:' + namespace + ':manager'
        # Actual forbidden API requests under the deployed service-account identity.
        denied = []
        for resource, extra in [('secrets', []), ('deployments', ['-n', 'p0-other']), ('namespaces', [])]:
            r = k(as_user, 'get', resource, *extra, '-o', 'name', expected_failure='Kubernetes API Forbidden for manager service account')
            if r.returncode == 0 or 'Forbidden' not in r.stderr:
                raise AssertionError('expected API Forbidden: ' + resource)
            denied.append(resource + (':p0-other' if extra else ''))
        k(as_user, 'get', 'deployments', '-o', 'name')
        return {'service_account': namespace + ':manager', 'forbidden_api_requests': denied, 'manager_cluster_admin': False}

    app_uid = None
    service_ip = None

    def create_app():
        nonlocal app_uid, service_ip
        apply({'apiVersion': 'lab.wiki.example/v1alpha1', 'kind': 'AppService', 'metadata': {'name': 'sample', 'namespace': namespace},
               'spec': {'image': operand_image}})
        def children():
            a, d, s = get('appservice', 'sample'), get('deployment', 'sample'), get('service', 'sample')
            if a and owned(d, a['metadata']['uid']) and owned(s, a['metadata']['uid']) and s['spec'].get('clusterIP'):
                return a, d, s
            return False
        a, d, s = poll(children)
        app_uid, service_ip = a['metadata']['uid'], s['spec']['clusterIP']
        return {'app_uid': app_uid, 'deployment_uid': d['metadata']['uid'], 'service_uid': s['metadata']['uid'], 'cluster_ip': service_ip}

    def http_service(pod_name="request"):
        url = 'http://sample.' + namespace + '.svc.cluster.local:8080/'
        apply({'apiVersion': 'v1', 'kind': 'Pod', 'metadata': {'name': pod_name, 'namespace': namespace}, 'spec': {
            'restartPolicy': 'Never', 'automountServiceAccountToken': False, 'activeDeadlineSeconds': 30,
            'securityContext': {'runAsNonRoot': True, 'runAsUser': 65532, 'seccompProfile': {'type': 'RuntimeDefault'}},
            'containers': [{'name': 'request', 'image': operand_image, 'imagePullPolicy': 'Never', 'args': ['--url=' + url],
                            'resources': {'requests': {'cpu': '10m', 'memory': '16Mi'}, 'limits': {'cpu': '100m', 'memory': '32Mi'}},
                            'securityContext': {'allowPrivilegeEscalation': False, 'readOnlyRootFilesystem': True, 'capabilities': {'drop': ['ALL']}}}]}})
        def completed():
            p = get('pod', pod_name)
            if p and p['status'].get('phase') == 'Failed':
                raise AssertionError('in-cluster request Pod failed')
            return p if p and p['status'].get('phase') == 'Succeeded' else False
        p = poll(completed, seconds=40)
        body = k('logs', 'pod/' + pod_name, '--limit-bytes=1024').stdout
        if body != '{"message":"wiki-bootstrap"}\n':
            raise AssertionError('unexpected in-cluster HTTP response')
        if p['spec'].get('automountServiceAccountToken') is not False:
            raise AssertionError('request Pod token not explicitly disabled')
        return {'url': url, 'pod_uid': p['metadata']['uid'], 'body': body, 'transport': 'Pod -> Service DNS -> ClusterIP -> operand Pod'}

    def drift():
        k('patch', 'deployment/sample', '--type=merge', '-p', json.dumps({'spec': {'template': {'spec': {'containers': [{'name': 'operand', 'image': 'wrong:must-never-pull', 'imagePullPolicy': 'Never'}]}}}}))
        k('patch', 'service/sample', '--type=merge', '-p', json.dumps({'spec': {'selector': {'lab.wiki.example/owner-uid': 'wrong'}}}))
        def repaired():
            d, s = get('deployment', 'sample'), get('service', 'sample')
            return (d['spec']['template']['spec']['containers'][0]['image'] == operand_image and
                    s['spec']['selector'] == {'lab.wiki.example/owner-uid': app_uid} and s['spec']['clusterIP'] == service_ip)
        poll(repaired)
        return poll(ready_state)

    def deleted_child():
        previous = get('service', 'sample')['metadata']['uid']
        k('delete', 'service/sample', '--wait=true', '--timeout=20s', timeout=25)
        def recreated():
            s = get('service', 'sample')
            return s if s and s['metadata']['uid'] != previous and owned(s, app_uid) else False
        s = poll(recreated)
        return {'old_uid': previous, 'new_uid': s['metadata']['uid']}

    def restart():
        before = [p['metadata']['uid'] for p in get('pods')['items'] if p['metadata'].get('labels', {}).get('app') == 'p0-manager']
        k('scale', 'deployment/manager', '--replicas=0')
        poll(lambda: not [p for p in get('pods')['items'] if p['metadata'].get('labels', {}).get('app') == 'p0-manager'], seconds=30)
        k('patch', 'service/sample', '--type=merge', '-p', json.dumps({'spec': {'selector': {'lab.wiki.example/owner-uid': 'stopped-drift'}}}))
        k('scale', 'deployment/manager', '--replicas=1')
        k('rollout', 'status', 'deployment/manager', '--timeout=60s', timeout=65)
        poll(lambda: get('service', 'sample')['spec']['selector'] == {'lab.wiki.example/owner-uid': app_uid})
        observed = poll(ready_state)
        after = [p['metadata']['uid'] for p in get('pods')['items'] if p['metadata'].get('labels', {}).get('app') == 'p0-manager']
        if not after or set(before).intersection(after):
            raise AssertionError('controller Pod did not restart')
        return {'before_manager_pod_uids': before, 'after_manager_pod_uids': after, 'operand': observed,
                'http_after_recreation_and_restart': http_service('request-after-restart')}

    def owner_gc():
        # Background GC, and no direct dependent deletion: Kubernetes must remove owned objects.
        k('delete', 'appservice/sample', '--cascade=background', '--wait=true', '--timeout=20s', timeout=25)
        def gone():
            d, s = get('deployment', 'sample'), get('service', 'sample')
            pods = [p for p in get('pods')['items'] if p['metadata'].get('labels', {}).get('lab.wiki.example/owner-uid') == app_uid]
            rss = [r for r in get('replicasets')['items'] if r['metadata'].get('labels', {}).get('lab.wiki.example/owner-uid') == app_uid]
            return not d and not s and not pods and not rss
        poll(gone, seconds=60)
        return {'deleted_app_uid': app_uid, 'observed_absent': ['Deployment', 'Service', 'owned ReplicaSets', 'owned Pods']}

    def diagnostics():
        if not cluster_attempted or not kubeconfig.exists():
            return 'cluster never became accessible; no API diagnostics available'
        commands = [('manager.log', ('logs', 'deployment/manager', '--tail=150', '--limit-bytes=32768')),
                    ('events.json', ('get', 'events', '-o', 'json')),
                    ('resources.json', ('get', 'appservices,deployments,replicasets,services,pods', '-o', 'json'))]
        for filename, argv in commands:
            r = k(*argv, deadline=diagnostic_deadline, timeout=8)
            data = r.stdout.encode()
            if len(data) > 512 * 1024:
                raise AssertionError('diagnostic exceeds artifact bound: ' + filename)
            (output / filename).write_bytes(data)
        return 'bounded own-namespace resources/events/manager logs only; no Secrets, kubeconfig or environment dump'

    def cleanup_cluster():
        if cluster_attempted:
            event('cluster_delete', 'attempt', name=cluster)
            command([tools['kind'], 'delete', 'cluster', '--name', cluster], deadline=cleanup_deadline, timeout=50)
            remaining = command([tools['kind'], 'get', 'clusters'], deadline=cleanup_deadline, timeout=10).stdout.splitlines()
            if cluster in remaining:
                raise AssertionError('owned cluster still exists')
            event('cluster_delete', 'pass', name=cluster)
        return {'name': cluster, 'attempted': cluster_attempted, 'absent': True}

    def cleanup_images():
        for tag in image_attempts:
            inspect = command([tools['docker'], 'image', 'inspect', '--format', '{{.Id}}', tag], deadline=cleanup_deadline, timeout=5, expected_failure='No such image or No such object for the generated image tag')
            if inspect.returncode == 0:
                command([tools['docker'], 'image', 'rm', tag], deadline=cleanup_deadline, timeout=10)
            elif 'No such image' not in inspect.stderr and 'No such object' not in inspect.stderr:
                raise AssertionError('cannot establish image presence for cleanup: ' + tag)
            verify = command([tools['docker'], 'image', 'inspect', '--format', '{{.Id}}', tag], deadline=cleanup_deadline, timeout=5, expected_failure='No such image or No such object for the generated image tag')
            if verify.returncode == 0 or ('No such image' not in verify.stderr and 'No such object' not in verify.stderr):
                raise AssertionError('image tag deletion not established: ' + tag)
            event('image_delete', 'pass', tag=tag)
        return {'tags': image_attempts, 'remaining': [], 'scope': 'generated tags only; never prune/shared node image/cache'}

    try:
        for name, fn in [('ToolVersions', versions), ('BuildLocalImages', build_images), ('OwnedClusterCreated', create_cluster),
                         ('ManagerNamespacedRBAC', deploy_manager), ('OwnedDeploymentService', create_app),
                         ('ReadyPodAndCurrentCondition', lambda: poll(ready_state)), ('HTTPThroughServiceDNS', http_service),
                         ('DriftRepaired', drift), ('DeletedChildRecreated', deleted_child),
                         ('ControllerRestartConverges', restart), ('OwnerGarbageCollection', owner_gc)]:
            case(name, fn)
    except Exception as exc:
        report['failure'] = str(exc)
    finally:
        for name, fn in [('DiagnosticsCollected', diagnostics), ('OwnedClusterRemoved', cleanup_cluster), ('OwnedImagesRemoved', cleanup_images)]:
            try:
                case(name, fn)
            except Exception as exc:
                report.setdefault('cleanup_or_diagnostics_failures', []).append(str(exc))
        try:
            shutil.rmtree(private)
            event('private_workspace_remove', 'pass', kubeconfig_absent=not kubeconfig.exists())
        except Exception as exc:
            event('private_workspace_remove', 'fail', error=str(exc))
            report.setdefault('cleanup_or_diagnostics_failures', []).append(str(exc))
        report['status'] = 'pass' if (all(c['status'] == 'pass' for c in report['cases']) and
                                              not report.get('cleanup_or_diagnostics_failures') and not report.get('failure')) else 'fail'
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        report['exit_code'] = 0 if report['status'] == 'pass' else 1
        flush()
    return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
