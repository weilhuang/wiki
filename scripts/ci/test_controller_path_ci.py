#!/usr/bin/env python3
"""Pure/synthetic checks. These are not Go, envtest or kind execution evidence."""
import ast
import shutil
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).parent

def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ci = load('controller_path_ci')
assets = load('controller_path_assets')
fixtures = load('controller_path_fixtures')

class IdentityAndEvents(unittest.TestCase):
    def test_each_actual_required_case_is_mandatory(self):
        inventory = json.loads((ci.LAB/'test-inventory.json').read_text())
        for layer in ('unit', 'integration'):
            expected = inventory[layer]
            events = fixtures.stream(expected)
            ci.test_events(('\n'.join(map(json.dumps, events))+'\n').encode(), expected)
            for index, event in enumerate(events):
                if event['Action']=='output': continue
                with self.subTest(layer=layer, omitted=event):
                    raw = '\n'.join(json.dumps(e) for i, e in enumerate(events) if i != index).encode()
                    with self.assertRaises(ValueError): ci.test_events(raw, expected)
        for layer in ('kind', 'harness_unit', 'mutants'):
            required = inventory[layer]
            rows = [{'id': name, 'status': 'pass'} for name in required]
            for index, name in enumerate(required):
                with self.subTest(layer=layer, omitted=name):
                    with self.assertRaises(ValueError): ci.exact_cases(rows[:index]+rows[index+1:], required)

    def test_regular_and_symlink_boundaries(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            file = root / 'record.json'
            file.write_bytes(b'{}')
            self.assertEqual(ci.bounded_bytes(file), b'{}')
            (root / 'link').symlink_to(file)
            with self.assertRaisesRegex(ValueError, 'symbolic'):
                ci.bounded_bytes(root / 'link')
            (root / 'parent').symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symbolic'):
                ci.bounded_bytes(root / 'parent/record.json')
            with self.assertRaisesRegex(ValueError, 'bounded'):
                ci.bounded_bytes(file, 1)
            with self.assertRaisesRegex(ValueError, 'regular'):
                ci.bounded_bytes(root)

    def test_required_go_outcomes(self):
        expected = {'pkg': ['TestContract', 'TestContract/state']}
        events = fixtures.stream(expected)
        encode = lambda x: ('\n'.join(json.dumps(e) for e in x)+'\n').encode()
        self.assertEqual(len(ci.test_events(encode(events), expected)), 2)
        for changed in [events[:-1], events[1:], events + [events[0]],
                        events + [{'Action': 'skip', 'Package': 'pkg', 'Test': 'TestOptional'}],
                        events + [{'Action': 'fail', 'Package': 'other'}],
                        events + [{'Action': 'build-fail', 'Package': 'pkg'}]]:
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    ci.test_events(encode(changed), expected)
        with self.assertRaises(json.JSONDecodeError):
            ci.test_events(b'go: failed to build\n', expected)

    def test_manifest_hash_is_order_independent(self):
        self.assertEqual(ci.source_id({'b': '2', 'a': '1'}), ci.source_id({'a': '1', 'b': '2'}))
        self.assertNotEqual(ci.source_id({'a': '1'}), ci.source_id({'a': '2'}))

class HarnessEventContract(unittest.TestCase):
    def test_lifecycle_event_preserves_cluster_name_detail(self):
        # Execute the actual nested event helper with in-memory dependencies only.
        module = ast.parse((ci.LAB / 'scripts/kind_acceptance.py').read_text())
        main = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        event = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == 'event')
        report = {'lifecycle': {'events': []}}
        flush = mock.Mock()
        context = {'report': report, 'started': 10.0,
                   'time': SimpleNamespace(monotonic=lambda: 11.25), 'flush': flush}
        exec(compile(ast.Module(body=[event], type_ignores=[]), '<actual-event-helper>', 'exec'), context)
        for phase, status in [('cluster_create', 'attempt'), ('cluster_create', 'pass'), ('cluster_delete', 'pass')]:
            context['event'](phase, status, name='wiki-p3-0123456789ab')
        self.assertEqual(report['lifecycle']['events'], [
            {'event': phase, 'status': status, 'elapsed_seconds': 1.25, 'name': 'wiki-p3-0123456789ab'}
            for phase, status in [('cluster_create', 'attempt'), ('cluster_create', 'pass'), ('cluster_delete', 'pass')]])
        self.assertEqual(flush.call_count, 3)


class Assets(unittest.TestCase):
    def test_checksum_and_size_before_executable(self):
        data = b'official fixture simulation'
        spec = {'url': 'https://example.invalid/artifact', 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            r = assets.fetch_asset(spec, root / 'okay', opener=lambda *_a, **_k: io.BytesIO(data))
            self.assertEqual(r['bytes'], len(data))
            for number, changed in enumerate([{**spec, 'sha256': '0'*64}, {**spec, 'bytes': 2},
                                              {**spec, 'sha512': '0'*128}]):
                with self.subTest(changed=changed):
                    with self.assertRaises(ValueError):
                        assets.fetch_asset(changed, root / ('bad'+str(number)), opener=lambda *_a, **_k: io.BytesIO(data))
            with self.assertRaisesRegex(ValueError, 'already exists'):
                assets.fetch_asset(spec, root / 'okay', opener=lambda *_a, **_k: io.BytesIO(data))

    def archive(self, path, entries):
        with tarfile.open(path, 'w:gz') as tar:
            for name, kind in entries:
                member = tarfile.TarInfo(name)
                member.mode = 0o755
                if kind == 'file':
                    member.size = 3
                    tar.addfile(member, io.BytesIO(b'bin'))
                else:
                    member.type = tarfile.SYMTYPE
                    member.linkname = '/etc/passwd'
                    tar.addfile(member)

    def test_envtest_archive_inventory_and_paths(self):
        good = [(f'controller-tools/envtest/{x}', 'file') for x in ['kubectl', 'etcd', 'kube-apiserver']]
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            archive = root / 'good.tar.gz'
            self.archive(archive, good)
            self.assertEqual(set(assets.extract_envtest(archive, root / 'good')), {'kubectl', 'etcd', 'kube-apiserver'})
            for number, entries in enumerate([good[:-1], good + [('elsewhere/etcd', 'file')],
                                                good + [('../escape', 'file')],
                                                good + [('link', 'link')]]):
                bad = root / f'bad{number}.tar.gz'
                self.archive(bad, entries)
                with self.subTest(entries=entries):
                    with self.assertRaises(ValueError):
                        assets.extract_envtest(bad, root / f'bad{number}')

class CompleteEvidence(unittest.TestCase):
    def command_trace(self, cluster):
        return fixtures.command_trace(ci, cluster)

    def fixture(self, root):
        return fixtures.fixture(ci, root)

    def test_complete_and_omitted_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files, before = self.fixture(root)
            with mock.patch.multiple(ci, LAB=root, CONTRACT=root/'reviewed.json'):
                self.assertEqual(ci.validate_reports(files, before)['kind_cases'], 18)
                for name in sorted(files):
                    with self.subTest(missing=name):
                        incomplete = dict(files)
                        del incomplete[name]
                        with self.assertRaises((ValueError, KeyError)):
                            ci.validate_reports(incomplete, before)

    def test_wrong_semantics_and_cleanup_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files, before = self.fixture(root)
            edits = [
                ('source-after.json', lambda d: d.update({'changed': 'b'*64})),
                ('assets.json', lambda d: d.update(status='failed')),
                ('generated.json', lambda d: d['files'][0].update(identical=False)),
                ('generated.json', lambda d: d['files'][0].update(sha256='0'*64)),
                ('generated.json', lambda d: d['files'].pop()),
                ('mutants.json', lambda d: d['cases'].pop()),
                ('mutants.json', lambda d: d['cases'][0].update(exit_code=2)),
                ('mutants.json', lambda d: d['cases'][0].update(mutant_jsonl='go: compile error')),
                ('mutants.json', lambda d: d['cases'][0].update(baseline_exit_code=1)),
                ('unit-stage.json', lambda d: d.update(timed_out=True)),
                ('integration-stage.json', lambda d: d.update(exit_code=1)),
                ('kind-stage.json', lambda d: d.update(process_group_cleanup=False)),
                ('kind-stage.json', lambda d: d.update(source_id='0'*64)),
                ('harness-oracle.json', lambda d: d.update(layer='real-cluster')),
                ('harness-oracle.json', lambda d: d['cases'][0].update(status='fail')),
                ('kind-report.json', lambda d: d.update(commands=[{'id': 1, 'exit_code': 0}])),
                ('kind-report.json', lambda d: d['commands'][0].pop('stdout_bytes')),
                ('kind-report.json', lambda d: d['commands'][0].update(stdout_sha256='0'*64)),
                ('kind-report.json', lambda d: d['commands'][0].update(case_id='Unknown')),
                ('kind-report.json', lambda d: d['lifecycle']['events'].pop(0)),
                ('kind-report.json', lambda d: d.update(run_id='b'*12)),
                ('envtest-report.json', lambda d: d.update(server_version='v1.36.0')),
                ('envtest-report.json', lambda d: d['cases'][0].update(status='not_run')),
                ('envtest-report.json', lambda d: d['lifecycle'].pop()),
                ('kind-report.json', lambda d: d.update(source_id='0'*64)),
                ('kind-report.json', lambda d: d['cases'].append(d['cases'][0])),
                ('kind-report.json', lambda d: d['lifecycle']['events'].pop()),
                ('kind-report.json', lambda d: d['commands'][0].update(exit_code=125)),
                ('kind-report.json', lambda d: d['commands'][0].update(timeout_seconds=999)),
                ('kind-report.json', lambda d: d['commands'][0].update(argv=['docker', 'system', 'prune'])),
                ('kind-report.json', lambda d: d['commands'][0].update(exit_code=1, allow_failure=True)),
                ('kind-report.json', lambda d: d.update(cleanup_or_diagnostics_failures=['error']))]
            with mock.patch.multiple(ci, LAB=root, CONTRACT=root/'reviewed.json'):
                for name, change in edits:
                    altered = dict(files)
                    value = json.loads(altered[name]); change(value); altered[name] = json.dumps(value).encode()
                    with self.subTest(file=name, change=change):
                        with self.assertRaises((ValueError, KeyError)):
                            ci.validate_reports(altered, before)

    def test_command_ownership_and_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); files, before = self.fixture(root)
            cases = [
                ('wrong cluster', lambda d: next(c for c in d['commands'] if Path(c['argv'][0]).name=='kind' and c['argv'][1]=='delete')['argv'].__setitem__(4, 'another-cluster')),
                ('missing phase', lambda d: d.update(commands=[c for c in d['commands'] if c['case_id']!='HTTPThroughServiceDNS'])),
                ('wrong cache', lambda d: next(c for c in d['commands'] if '--cache-dir' in c['argv'])['argv'].__setitem__(7, '/another/cache')),
                ('direct GC', lambda d: next(c for c in d['commands'] if c['case_id']=='OwnerGarbageCollection' and 'delete' in c['argv'])['argv'].__setitem__(11, 'deployment/sample')),
                ('absence missing', lambda d: next(c for c in d['commands'] if c['case_id']=='BuildLocalImages' and c['exit_code']==1).update(exit_code=0)),
                ('absence wrong class', lambda d: next(c for c in d['commands'] if c['case_id']=='BuildLocalImages' and c['exit_code']==1).update(expected_failure='No such image or No such object for the generated image tag')),
                ('forbidden missing', lambda d: next(c for c in d['commands'] if c['case_id']=='ManagerNamespacedRBAC' and c['exit_code']==1).update(exit_code=0)),
            ]
            with mock.patch.multiple(ci, LAB=root, CONTRACT=root/'reviewed.json'):
                for name, mutate in cases:
                    record=json.loads(files['kind-report.json']);mutate(record)
                    for i, command in enumerate(record['commands'], 1): command['id']=i
                    altered={**files,'kind-report.json':json.dumps(record).encode()}
                    with self.subTest(name=name):
                        with self.assertRaises((ValueError, KeyError)):
                            ci.validate_reports(altered, before)

    def test_kind_budget_fails_before_external_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); before={'labs/example':'a'*64}
            (root/'source-before.json').write_text(json.dumps(before))
            (root/'provenance.json').write_text(json.dumps({'prepared_monotonic':100.0}))
            with mock.patch.object(ci,'PRIVATE',root), mock.patch.object(ci,'source_identity',return_value=before), \
                    mock.patch.object(ci.time,'monotonic',return_value=1061.0), mock.patch.object(ci,'run_command') as run:
                with self.assertRaisesRegex(ValueError,'not enough job time'):
                    ci.run_kind()
                run.assert_not_called()

    def test_collect_validates_raw_then_uploads_only_redacted_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); lab=root/'lab';lab.mkdir();private=root/'private';private.mkdir()
            upload=root/'upload';output=root/'github-output'
            files,before=self.fixture(lab)
            stage=json.loads(files['kind-stage.json'])
            stage['command'][stage['command'].index('--evidence-dir')+1]=str(private/'kind')
            files['kind-stage.json']=json.dumps(stage).encode()
            report=json.loads(files['kind-report.json'])
            previous=dict(report['tool_paths'])
            for name in ['kind','kubectl']: report['tool_paths'][name]=str(private/'tools'/name)
            for row in report['commands']:
                for name in ['kind','kubectl']:
                    if row['argv'][0]==previous[name]: row['argv'][0]=report['tool_paths'][name]
            command=next(c for c in report['commands'] if Path(c['argv'][0]).name=='kind' and c['argv'][1:3]==['create','cluster'])
            raw_tail='kubectl cluster-info --kubeconfig '+str(private)+'/kubeconfig\n'
            command.update(stderr_tail=raw_tail,stderr_bytes=len(raw_tail.encode()),stderr_sha256=hashlib.sha256(raw_tail.encode()).hexdigest())
            files['kind-report.json']=json.dumps(report).encode()
            mapping={name:private/name for name in ci.PUBLIC_FILES | {'kind.log'}}
            mapping.update({'kind-report.json':private/'kind/kind-report.json',
                'kind-manager.log':private/'kind/manager.log','kind-events.json':private/'kind/events.json',
                'kind-resources.json':private/'kind/resources.json'})
            for name,data in files.items():
                path=mapping[name];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            real_reader=ci.bounded_bytes; counts={}
            def counted(path,*args):
                key=str(path);counts[key]=counts.get(key,0)+1
                return real_reader(path,*args)
            with mock.patch.multiple(ci,TEMP=root,PRIVATE=private,UPLOAD=upload,LAB=lab,CONTRACT=lab/'reviewed.json'), \
                    mock.patch.object(ci,'source_identity',return_value=before), \
                    mock.patch.object(ci,'bounded_bytes',side_effect=counted), \
                    mock.patch.dict('os.environ',{'GITHUB_OUTPUT':str(output)}):
                # The regression must reject comparing redacted tails with raw stream hashes.
                transformed=dict(files)
                changed=json.loads(files['kind-report.json'])
                selected=next(c for c in changed['commands'] if Path(c['argv'][0]).name=='kind' and c['argv'][1:3]==['create','cluster'])
                selected['stderr_tail']=ci.normalize_for_upload(selected['stderr_tail'].encode()).decode()
                transformed['kind-report.json']=json.dumps(changed).encode()
                with self.assertRaisesRegex(ValueError,'short stream identity differs'):
                    ci.validate_reports(transformed,before)
                ci.collect()
            validation=json.loads((upload/'validation.json').read_text())
            self.assertEqual(validation['status'],'pass')
            body=(upload/'kind-report.json').read_bytes();identity=validation['files']['kind-report.json']
            self.assertNotIn(str(private).encode(),body)
            self.assertIn(b'<private>/kubeconfig',body)
            self.assertEqual(identity['raw_sha256'],hashlib.sha256(files['kind-report.json']).hexdigest())
            self.assertEqual(identity['raw_bytes'],len(files['kind-report.json']))
            self.assertEqual(identity['upload_sha256'],hashlib.sha256(body).hexdigest())
            self.assertEqual(identity['upload_bytes'],len(body))
            self.assertNotEqual(identity['raw_sha256'],identity['upload_sha256'])
            self.assertEqual(counts[str(private/'kind/kind-report.json')],1)
            self.assertEqual(output.read_text(),'upload_ready=true\n')

    def test_upload_existing_path_never_enables_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root / 'github-output'; upload = root / 'upload'; upload.mkdir()
            (upload/'unexpected').write_text('not validated')
            with mock.patch.multiple(ci, TEMP=root, UPLOAD=upload, PRIVATE=root/'private'), mock.patch.dict('os.environ', {'GITHUB_OUTPUT': str(output)}):
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    ci.collect()
            self.assertFalse(output.exists())

    def test_private_symlink_yields_only_safe_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); external=root/'external';external.mkdir();(external/'secret').write_text('SHOULD_NOT_BE_READ')
            private=root/'private';private.symlink_to(external, target_is_directory=True)
            output=root/'github-output';upload=root/'upload'
            with mock.patch.multiple(ci, TEMP=root, UPLOAD=upload, PRIVATE=private), mock.patch.dict('os.environ', {'GITHUB_OUTPUT': str(output)}):
                with self.assertRaisesRegex(ValueError, 'evidence gate failed'):
                    ci.collect()
            self.assertEqual([f.name for f in upload.iterdir()], ['validation.json'])
            self.assertNotIn('SHOULD_NOT_BE_READ', (upload/'validation.json').read_text())
            self.assertEqual(json.loads((upload/'validation.json').read_text())['status'], 'fail')
            self.assertEqual(output.read_text(), 'upload_ready=true\n')

    def test_credential_refusal_and_path_normalization(self):
        for text in [b'-----BEGIN PRIVATE KEY-----', b'client-key-data: xxx',
                     b'Authorization: Bearer abc.def.ghi', b'{"kind":"Secret"}']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):ci.normalize_for_upload(text)
        data = str(ci.PRIVATE).encode() + b'/example'
        self.assertEqual(ci.normalize_for_upload(data), b'<private>/example')


if __name__ == '__main__':
    unittest.main()
