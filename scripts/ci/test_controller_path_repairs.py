#!/usr/bin/env python3
"""Pure Python regressions for the six r4 review blockers. No Go or cluster runs."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

HERE=Path(__file__).parent
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
ci=load(HERE/'controller_path_ci.py','repair_ci')
fx=load(HERE/'controller_path_fixtures.py','repair_fixtures')
mutants=load(ci.LAB/'scripts/check_mutants.py','repair_mutants')
sys.path.insert(0,str(ci.LAB/'scripts'))
generated=load(ci.LAB/'scripts/check_generated.py','repair_generated')
owned=load(ci.LAB/'scripts/owned_process.py','repair_owned')
encode=lambda events:b''.join(json.dumps(e).encode()+b'\n' for e in events)


class StrictGo(unittest.TestCase):
    def test_all_exact_controls(self):
        for m in mutants.MUTANTS:
            raw=encode(fx.stream({mutants.PACKAGE:m['names']},'fail',m['message'],m['test']))
            mutants.semantic_failure(raw,1,m['test'],m['message'])
            mutants.go_events.positive(encode(fx.stream({mutants.PACKAGE:m['names']})),{mutants.PACKAGE:m['names']},frames_only=True)

    def test_real_go127_controls_and_legacy_bad_inputs(self):
        root=ci.LAB/'testdata/go127-gates'
        p2=root/'p2-m06-real-go127.jsonl'
        mutants.go_events.semantic(p2.read_bytes(),1,'example.com/reservation-service/internal/grpcapi',
                                   ['TestG07StreamSendError'],'TestG07StreamSendError','STREAM_SEND_ERROR')
        inventory=json.loads((ci.LAB/'test-inventory.json').read_text())['unit']
        self.assertEqual(len(ci.test_events((root/'p3-r3-unit-real-go127.jsonl').read_bytes(),inventory)),29)
        for path in root.glob('p2-mutant_*.jsonl'):
            with self.subTest(path=path.name),self.assertRaises(ValueError):
                mutants.go_events.semantic(path.read_bytes(),1,'example.com/reservation-service/tests',
                    ['TestIntegration','TestIntegration/sql','TestIntegration/sql/H10','TestIntegration/gorm','TestIntegration/gorm/H10'],
                    'TestIntegration/sql/H10','HTTP_ERROR_BODY')

    def test_parent_leaf_package_and_missing_test_adversaries(self):
        m=mutants.MUTANTS[0];leaf=m['test'];parent=m['names'][0];pkg=mutants.PACKAGE
        baseline=fx.stream({pkg:m['names']},'fail',m['message'],leaf)
        def inject(rows,text,name=leaf,typ='error'):
            index=next(i for i,e in enumerate(rows) if e.get('Test')==name and e['Action']=='fail')
            rows.insert(index,{'Action':'output','Package':pkg,'Test':name,'Output':text+'\n','OutputType':typ})
        def semantic_event(rows):return next(e for e in rows if 'SEMANTIC_ASSERT' in e.get('Output',''))
        changes={
            'extra-leaf-cleanup':lambda r:inject(r,'    fixture_test.go:58: owned cleanup failed'),
            'extra-parent-assertion':lambda r:inject(r,'    controller_test.go:99: unrelated parent assertion',parent),
            'panic-with-marker':lambda r:inject(r,'panic: runtime error: '+m['message'],typ=None),
            'timeout-with-marker':lambda r:inject(r,'panic: test timed out after 20s '+m['message'],typ=None),
            'setup-failure':lambda r:inject(r,'FAIL setup [setup failed]',typ=None),
            'other-package-build':lambda r:r.extend([{'Action':'start','Package':'wrong/pkg'},{'Action':'fail','Package':'wrong/pkg'}]),
            'wrong-package':lambda r:[e.update(Package='wrong/pkg') for e in r],
            'missing-parent-terminal':lambda r:r.__setitem__(slice(None),[e for e in r if not(e['Action']=='fail' and e.get('Test')==parent)]),
            'missing-leaf-run':lambda r:r.__setitem__(slice(None),[e for e in r if not(e['Action']=='run' and e.get('Test')==leaf)]),
            'missing-package-start':lambda r:r.pop(0),
            'missing-package-terminal':lambda r:r.pop(),
            'extra-unfinished-leaf':lambda r:r.insert(-1,{'Action':'run','Package':pkg,'Test':parent+'/unfinished'}),
            'extra-passing-leaf':lambda r:r.insert(-1,{'Action':'pass','Package':pkg,'Test':parent+'/extra'}),
            'duplicate-package-terminal':lambda r:r.append(r[-1].copy()),
            'wrong-failure-mentions-marker':lambda r:semantic_event(r).update(Output='    x.go:1: setup failed while reading '+m['message']+'\n'),
            'logged-marker':lambda r:semantic_event(r).update(OutputType=None),
            'contradictory-pass':lambda r:r.insert(-1,{'Action':'pass','Package':pkg,'Test':leaf}),
            'missing-leaf':lambda r:r.__setitem__(slice(None),[e for e in r if e.get('Test')!=leaf]),
            'duplicate-assertion':lambda r:inject(r,semantic_event(r)['Output'].strip()),
            'wrong-marker':lambda r:semantic_event(r).update(Output=semantic_event(r)['Output'].replace(m['message'],'OTHER')),
            'got-equals-want':lambda r:semantic_event(r).update(Output=semantic_event(r)['Output'].replace('"got": "wrong"','"got": "correct"')),
            'invented-slash-parent':lambda r:r.insert(-1,{'Action':'run','Package':pkg,'Test':parent+'/Deployment'}),
        }
        for name,change in changes.items():
            rows=copy.deepcopy(baseline);change(rows)
            with self.subTest(case=name),self.assertRaises(ValueError):mutants.semantic_failure(encode(rows),1,leaf,m['message'])
        for code in [0,2,124,True]:
            with self.subTest(exit_code=code),self.assertRaises(ValueError):mutants.semantic_failure(encode(baseline),code,leaf,m['message'])

    def test_positive_started_tests_cannot_disappear(self):
        expected={mutants.PACKAGE:['TestRoot','TestRoot/Deployment/unowned']}
        good=fx.stream(expected)
        ci.test_events(encode(good),expected)
        for index,event in enumerate(good):
            if event['Action']=='output':continue
            with self.subTest(omitted=event),self.assertRaises(ValueError):ci.test_events(encode(good[:index]+good[index+1:]),expected)
        for extra in [{'Action':'run','Package':mutants.PACKAGE,'Test':'TestUnfinished'},
                      {'Action':'pass','Package':mutants.PACKAGE,'Test':'TestExtra'},
                      {'Action':'start','Package':'wrong/pkg'}]:
            with self.subTest(extra=extra),self.assertRaises(ValueError):ci.test_events(encode(good[:-1]+[extra,good[-1]]),expected)


class FreshGenerator(unittest.TestCase):
    def run_fixture(self,change):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source';source.mkdir()
            for name in generated.FILES:
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('golden '+name+'\n');path.chmod(0o644)
            (source/'input.go').write_text('original\n');before=generated.tree(source)
            def fake_run(command,work,deadline,offline):
                self.assertEqual(command,generated.COMMAND)
                self.assertFalse(any((work/name).exists() for name in generated.FILES))
                change(source,work)
                return 0,b''
            output=io.StringIO()
            with mock.patch.object(generated,'HERE',source),mock.patch.object(generated,'run',side_effect=fake_run),\
                 mock.patch.object(sys,'argv',['check_generated.py','--source-id','synthetic']),contextlib.redirect_stdout(output):
                code=generated.main()
            return code,json.loads(output.getvalue()),before,generated.tree(source)

    @staticmethod
    def valid(source,work):
        for name in generated.FILES:shutil.copyfile(source/name,work/name)

    def test_fresh_outputs_required_and_inputs_untouched(self):
        code,report,before,after=self.run_fixture(self.valid)
        self.assertEqual(code,0);self.assertEqual(before,after);self.assertTrue(report['outputs_removed_before_run'])
        changes={
            'noop':lambda s,w:None,
            'missing':lambda s,w:shutil.copyfile(s/generated.FILES[0],w/generated.FILES[0]),
            'wrong':lambda s,w:(self.valid(s,w),(w/generated.FILES[0]).write_text('wrong')),
            'symlink':lambda s,w:(self.valid(s,w),(w/generated.FILES[0]).unlink(),(w/generated.FILES[0]).symlink_to(s/generated.FILES[0])),
            'unexpected':lambda s,w:(self.valid(s,w),(w/'surprise').write_text('extra')),
            'input-drift':lambda s,w:(self.valid(s,w),(w/'input.go').write_text('changed')),
            'mode':lambda s,w:(self.valid(s,w),(w/generated.FILES[0]).chmod(0o666)),
            'source-mutation':lambda s,w:(self.valid(s,w),(s/'input.go').write_text('changed')),
        }
        for name,change in changes.items():
            with self.subTest(case=name):
                code,report,before,after=self.run_fixture(change);self.assertEqual(code,1);self.assertEqual(report['status'],'fail')
                if name!='source-mutation':self.assertEqual(before,after)


class IdentityAndSecrets(unittest.TestCase):
    def test_report_source_command_and_diagnostic_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);files,before=fx.fixture(ci,root)
            changes=[
                ('generated.json',lambda r:r.update(generator_exit_code=1)),
                ('generated.json',lambda r:r.update(generator_exit_code=False)),
                ('generated.json',lambda r:r.update(generator='wrong/tool@v9')),
                ('generated.json',lambda r:r.update(command=['wrong'])),
                ('generated.json',lambda r:r.update(outputs_removed_before_run=False)),
                ('generated.json',lambda r:r.update(source_tree_unchanged=False)),
                ('generated.json',lambda r:r['files'][0].update(fresh_regular_file=False)),
                ('generated-stage.json',lambda r:r.update(source_id='0'*64)),
                ('mutants-stage.json',lambda r:r.update(source_id='0'*64)),
                ('generated-stage.json',lambda r:r.update(command=['wrong-stage'])),
                ('mutants-stage.json',lambda r:r.update(command=['wrong-stage'])),
                ('kind-stage.json',lambda r:r.update(command=['wrong-stage'])),
                ('dependencies-stage.json',lambda r:r.update(source_id='0'*64)),
                ('mutants.json',lambda r:r['cases'][0].update(mutant_file_sha256='0'*64)),
                ('mutants.json',lambda r:r['cases'][0].update(command=['wrong'])),
                ('mutants.json',lambda r:r['cases'][0].update(test='TestWrong')),
                ('provenance.json',lambda r:r.update(contract_sha256='0'*64)),
                ('kind-report.json',lambda r:next(c for c in r['commands'] if c['argv'][1:3]==['create','cluster'])['argv'].extend(['--kubeconfig','/not-owned/override'])),
                ('kind-report.json',lambda r:next(c for c in r['commands'] if '--kubeconfig' in c['argv'] and Path(c['argv'][0]).name=='kubectl')['argv'].extend(['--context=other'])),
                ('kind-report.json',lambda r:r['commands'][0].update(process_group_cleanup=False)),
                ('kind-report.json',lambda r:r['commands'][0].update(lingering_children=True)),
                ('kind-report.json',lambda r:r['commands'][0].pop('lingering_children')),
                ('kind-report.json',lambda r:r['commands'][0].update(parent_reaped=False)),
                ('kind-report.json',lambda r:r['commands'][0].update(termination_sent=True)),
                ('kind-report.json',lambda r:r['commands'][0]['argv'].__setitem__(0,'/wrong/go')),
            ]
            with mock.patch.multiple(ci,LAB=root,CONTRACT=root/'reviewed.json'):
                ci.validate_reports(files,before)
                for name,change in changes:
                    value=json.loads(files[name]);change(value)
                    with self.subTest(file=name,change=change),self.assertRaises(ValueError):ci.validate_reports({**files,name:json.dumps(value).encode()},before)
                for name in ['kind-manager.log','kind-events.json','kind-resources.json']:
                    with self.subTest(diagnostic=name),self.assertRaises(ValueError):ci.validate_reports({**files,name:b'replaced bytes\n'},before)
                for name,kind,namespace in [('kind-events.json','Secret','p3-lab'),('kind-resources.json','Pod','other-namespace')]:
                    value=json.loads(files['kind-report.json']);blob=json.dumps({'kind':'List','items':[{'apiVersion':'v1','kind':kind,'metadata':{'namespace':namespace}}]}).encode()
                    resource='events' if name=='kind-events.json' else 'appservices,deployments,replicasets,services,pods'
                    row=next(c for c in value['commands'] if c['case_id']=='DiagnosticsCollected' and c['argv'][11]==resource)
                    row.update(stdout_tail=blob.decode(),stdout_bytes=len(blob),stdout_sha256=hashlib.sha256(blob).hexdigest())
                    with self.subTest(scope=name),self.assertRaises(ValueError):ci.validate_reports({**files,name:blob,'kind-report.json':json.dumps(value).encode()},before)

    def test_decoded_credential_forms(self):
        samples=[
            b'apiVersion: v1\nkind: Config\nusers:\n- name: fixture\n  user:\n    token: SYNTHETIC_NOT_A_SECRET\n',
            b'users:\n- user:\n    username: fixture\n    password: SYNTHETIC_NOT_A_SECRET\n',
            b'{"client\\u002dkey\\u002ddata":"SYNTHETIC_NOT_A_SECRET"}',
            b'{"k\\u0069nd":"Secret","data":{"fake":"SYNTHETIC_NOT_A_SECRET"}}',
            json.dumps({'Output':json.dumps({'user':{'token':'SYNTHETIC_NOT_A_SECRET'}})}).encode(),
            json.dumps({'Output':json.dumps(json.dumps({'client-key-data':'SYNTHETIC_NOT_A_SECRET'}))}).encode(),
            json.dumps({'Output':'    fixture.go:1: details '+json.dumps({'user':{'token':'SYNTHETIC_NOT_A_SECRET'}})}).encode(),
            b'"k\\u0069nd": Secret\n',
            b'Authorization: Basic SYNTHETIC_NOT_A_SECRET\n',
            b'{"kind":"Secret","kind":"Pod"}',
            b'tokenFile: /synthetic/no-file-read\n',
        ]
        for data in samples:
            with self.subTest(sample=data),self.assertRaises(ValueError):ci.normalize_for_upload(data)
        safe=b'{"spec":{"automountServiceAccountToken":false},"msg":"no credentials collected"}'
        self.assertEqual(ci.normalize_for_upload(safe),safe)
        for safe in [b'No tokens, passwords or credentials are collected.\n',
                     b'{"scope":"client-key-data and kubeconfig content are excluded; token checks are synthetic","source":"scripts/token_policy_test.py"}']:
            with self.subTest(harmless=safe):self.assertEqual(ci.normalize_for_upload(safe),safe)


class CleanupAndProcesses(unittest.TestCase):
    def cleanup(self,scenario):
        module=ast.parse((ci.LAB/'scripts/kind_acceptance.py').read_text());main=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        functions=[n for n in main.body if isinstance(n,ast.FunctionDef) and n.name in ('cleanup_cluster','cleanup_images')]
        tags=['wiki-p3-manager-0123456789ab:local','wiki-p3-operand-0123456789ab:local']
        state={'now':630.,'calls':[],'removed':set(),'events':[]}
        def command(argv,timeout,deadline,**kwargs):
            state['calls'].append(list(argv))
            cost=timeout+2-.1 if scenario=='slow' else .1
            if state['now']+cost>deadline:raise RuntimeError('insufficient independently reserved budget')
            state['now']+=cost
            if argv[:3]==['docker','image','rm']:
                if scenario=='first-image-fails' and argv[-1]==tags[0]:raise RuntimeError('synthetic first image removal error')
                state['removed'].add(argv[-1])
            absent=argv[:3]==['docker','image','inspect'] and argv[-1] in state['removed']
            return SimpleNamespace(returncode=1 if absent else 0,stdout='',stderr='No such image' if absent else '')
        env={'time':SimpleNamespace(monotonic=lambda:state['now']),'command':command,'event':lambda event_name,status,**d:state['events'].append({'event':event_name,'status':status,**d}),
             'cluster_attempted':True,'cluster':'wiki-p3-0123456789ab','tools':{'kind':'kind','docker':'docker'},'cleanup_deadline':770.,'image_attempts':tags}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'<actual cleanup helpers>','exec'),env)
        errors=[]
        for name in ['cleanup_cluster','cleanup_images']:
            try:env[name]()
            except RuntimeError as exc:errors.append(str(exc))
        return state,errors,tags

    def test_complete_worst_case_reserve_and_independent_images(self):
        state,errors,tags=self.cleanup('slow');self.assertEqual(errors,[]);self.assertEqual(state['removed'],set(tags));self.assertLessEqual(state['now'],750)
        state,errors,tags=self.cleanup('first-image-fails')
        self.assertTrue(errors);self.assertEqual(state['removed'],{tags[1]})
        self.assertTrue(any(e['event']=='image_delete' and e.get('tag')==tags[0] and e['status']=='fail' for e in state['events']))
        self.assertTrue(any(e['event']=='image_delete' and e.get('tag')==tags[1] and e['status']=='pass' for e in state['events']))
        self.assertTrue(all(not ('prune' in c or any('node'==a for a in c)) for c in state['calls']))

    def test_owned_group_normal_exit_and_failure_paths(self):
        process=SimpleNamespace(pid=4321,poll=lambda:0,wait=mock.Mock(return_value=0))
        with mock.patch.object(owned,'group_exists',side_effect=[True,False,False]),mock.patch.object(owned.os,'killpg') as kill:
            result=owned.finish_group(process)
        self.assertTrue(result['lingering_children']);self.assertTrue(result['process_group_cleanup']);kill.assert_called_once_with(4321,owned.signal.SIGKILL)
        with mock.patch.object(owned,'group_exists',return_value=False),mock.patch.object(owned.os,'killpg') as kill:
            result=owned.finish_group(process)
        self.assertFalse(result['lingering_children']);self.assertTrue(result['process_group_cleanup']);kill.assert_not_called()
        running=SimpleNamespace(pid=4321,poll=lambda:None,wait=mock.Mock(return_value=-9))
        with mock.patch.object(owned,'group_exists',side_effect=[True,False,False]),mock.patch.object(owned.os,'killpg') as kill:
            result=owned.finish_group(running)
        self.assertTrue(result['process_group_cleanup']);self.assertTrue(result['parent_reaped']);kill.assert_called_once_with(4321,owned.signal.SIGKILL)
        with mock.patch.object(owned,'group_exists',return_value=True),mock.patch.object(owned.os,'killpg'),\
             mock.patch.object(owned.time,'monotonic',side_effect=[0,0,3]),mock.patch.object(owned.time,'sleep'):
            result=owned.finish_group(process)
        self.assertFalse(result['process_group_cleanup'])

    def test_actual_kind_command_rejects_nominal_exit_with_child(self):
        module=ast.parse((ci.LAB/'scripts/kind_acceptance.py').read_text());main=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        command=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='command')
        class Stream:
            closed=False
            def fileno(self):return 42
            def close(self):self.closed=True
        class Selector:
            def __init__(self):self.entries={}
            def register(self,obj,_event,data):self.entries[id(obj)]=SimpleNamespace(fd=42,fileobj=obj,data=data)
            def get_map(self):return self.entries
            def select(self,_timeout):return [(v,None) for v in list(self.entries.values())]
            def unregister(self,obj):del self.entries[id(obj)]
            def close(self):pass
        proc=SimpleNamespace(pid=4321,stdin=None,stdout=Stream(),stderr=Stream(),wait=lambda timeout:0)
        report={'commands':[]};finish=mock.Mock(return_value={'owned_process_group':4321,'process_group_cleanup':True,'lingering_children':True})
        env={'time':SimpleNamespace(monotonic=lambda:1.),'work_deadline':20.,'active':'ToolVersions','hashlib':hashlib,
             'selectors':SimpleNamespace(DefaultSelector=Selector,EVENT_READ=1,EVENT_WRITE=2),
             'os':SimpleNamespace(set_blocking=lambda *a:None,read=lambda *a:b''),
             'subprocess':SimpleNamespace(Popen=lambda *a,**k:proc,PIPE=1,DEVNULL=2,TimeoutExpired=TimeoutError),
             'HERE':ci.LAB,'env':{},'report':report,'flush':lambda:None,'finish_group':finish}
        exec(compile(ast.Module(body=[command],type_ignores=[]),'<actual command helper>','exec'),env)
        with self.assertRaisesRegex(RuntimeError,'survived'):env['command'](['go','version'])
        self.assertEqual(report['commands'][0]['exit_code'],0);self.assertTrue(report['commands'][0]['lingering_children']);finish.assert_called_once_with(proc,seconds=2)


class KubectlAndCredentialBoundary(unittest.TestCase):
    # The exact thirteen r5 independent false greens. Values are invented sentinels.
    overrides = {
        'server': ['--server=https://not-owned.example.invalid'],
        'server_short': ['-s', 'https://not-owned.example.invalid'],
        'namespace': ['--namespace', 'not-owned'], 'namespace_short': ['-n', 'not-owned'],
        'user': ['--user', 'not-owned'], 'cluster': ['--cluster', 'not-owned'],
        'impersonation': ['--as=system:admin'], 'token': ['--token=SYNTHETIC_NOT_A_SECRET'],
    }
    credentials = {
        'quoted_authorization_yaml': "'authorization': 'Bearer SYNTHETIC_NOT_A_SECRET'\n",
        'quoted_authorization_fragment': '"authorization": "Bearer SYNTHETIC_NOT_A_SECRET"\n',
        'nested_quoted_authorization': json.dumps({'Output': '"authorization": "Bearer SYNTHETIC_NOT_A_SECRET"'}),
        'cli_token_equals': '--token=SYNTHETIC_NOT_A_SECRET',
        'cli_token_argv': json.dumps({'argv': ['kubectl', '--token', 'SYNTHETIC_NOT_A_SECRET']}),
    }
    harmless = {
        'plain_policy': 'Do not collect tokens, passwords, client-key-data or credentials',
        'json_policy': json.dumps({'scope': 'client-key-data and kubeconfig content are excluded; token checks are synthetic'}),
        'token_mount_field': json.dumps({'spec': {'automountServiceAccountToken': False}}),
        'source_filename': json.dumps({'source': 'scripts/token_policy_test.py'}),
        'kubeconfig_policy': json.dumps({'kubeconfig_policy': 'exclusive temporary file; never uploaded; deleted in finally'}),
    }

    def collected(self, override=None, text=None):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);lab=root/'lab';lab.mkdir();private=root/'private';private.mkdir()
            upload=root/'upload';output=root/'github-output'
            with mock.patch.object(ci, 'PRIVATE', private): files,before=fx.fixture(ci,lab)
            if override is not None:
                report=json.loads(files['kind-report.json'])
                next(c for c in report['commands'] if c['case_id']=='ReadyPodAndCurrentCondition')['argv'].extend(override)
                files['kind-report.json']=json.dumps(report).encode()
            if text is not None: files['kind.log']=text.encode()
            paths={name:private/name for name in ci.PUBLIC_FILES | {'kind.log'}}
            paths.update({'kind-report.json':private/'kind/kind-report.json', 'kind-manager.log':private/'kind/manager.log',
                          'kind-events.json':private/'kind/events.json', 'kind-resources.json':private/'kind/resources.json'})
            for name,data in files.items():
                path=paths[name];path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            with mock.patch.multiple(ci,TEMP=root,PRIVATE=private,UPLOAD=upload,LAB=lab,CONTRACT=lab/'reviewed.json'), \
                    mock.patch.object(ci,'source_identity',return_value=before), \
                    mock.patch.dict(os.environ,{'GITHUB_OUTPUT':str(output)}):
                if override is not None:
                    with self.assertRaises(ValueError):ci.validate_reports(files,before)
                error=None
                try:ci.collect()
                except ValueError as exc:error=str(exc)
            return json.loads((upload/'validation.json').read_text()),error,{p.name:p.read_bytes() for p in upload.iterdir()}

    def test_thirteen_false_greens_through_actual_collection(self):
        for name,flags in self.overrides.items():
            with self.subTest(original='kubectl_override_'+name):
                validation,error,uploaded=self.collected(override=flags)
                self.assertEqual(validation['status'],'fail');self.assertIsNotNone(error)
                if name=='token':self.assertNotIn('kind-report.json',uploaded)
        for name,value in self.credentials.items():
            with self.subTest(original='credential_'+name):
                validation,error,uploaded=self.collected(text=value)
                self.assertEqual(validation['status'],'fail');self.assertIsNotNone(error)
                self.assertNotIn('kind.log',uploaded)
                self.assertFalse(any(b'SYNTHETIC_NOT_A_SECRET' in data for data in uploaded.values()))
        for name,value in self.harmless.items():
            with self.subTest(control=name):
                validation,error,uploaded=self.collected(text=value)
                self.assertEqual(validation['status'],'pass');self.assertIsNone(error)
                self.assertEqual(uploaded['kind.log'],value.encode())

    def test_exact_identity_namespace_and_label_profiles(self):
        identity='--as=system:serviceaccount:p3-lab:manager'
        expected='Kubernetes API Forbidden for manager service account'
        denied=[[identity,'get','secrets','-o','name'],[identity,'get','deployments','-n','p3-other','-o','name'],
                [identity,'get','namespaces','-o','name']]
        allowed=[identity,'get','deployments','-o','name']
        for args,outcome in [(a,expected) for a in denied]+[(allowed,None)]:
            with self.subTest(valid_identity=args):
                self.assertEqual(ci.validate_kubectl_profile('ManagerNamespacedRBAC',args,'a'*12,outcome),args[1:])
            for extra in [['--as=system:admin'],['--as','system:admin'],['--as-group=system:masters'],
                          ['--as-uid=0'],['-n','p3-other'],['--namespace=p3-lab'],['--user','other'],['--cluster=other'],['-shttps://other.invalid']]:
                with self.subTest(probe=args,override=extra),self.assertRaises(ValueError):
                    ci.validate_kubectl_profile('ManagerNamespacedRBAC',args+extra,'a'*12,outcome)
            with self.subTest(wrong_label=args),self.assertRaises(ValueError):
                ci.validate_kubectl_profile('ReadyPodAndCurrentCondition',args,'a'*12,outcome)
            with self.subTest(wrong_outcome=args),self.assertRaises(ValueError):
                ci.validate_kubectl_profile('ManagerNamespacedRBAC',args,'a'*12,None if outcome else expected)
        for args in denied:
            for index,replacement in [(0,'--as=system:admin'),(2,'pods')]:
                changed=list(args);changed[index]=replacement
                with self.subTest(wrong_probe=changed),self.assertRaises(ValueError):
                    ci.validate_kubectl_profile('ManagerNamespacedRBAC',changed,'a'*12,expected)
        with self.subTest(case="other_namespace_read"),self.assertRaises(ValueError):
            ci.validate_kubectl_profile('ManagerNamespacedRBAC',[identity,'get','deployments','-n','p3-other','-o','name'],'a'*12,None)

    def test_quoted_basic_and_cli_spellings(self):
        values=["'Authorization' = 'Basic SYNTHETIC_NOT_A_SECRET'", '"authorization"="Bearer SYNTHETIC_NOT_A_SECRET"',
                "'auth\\u006frization': 'Bearer SYNTHETIC_NOT_A_SECRET'"]
        flags=['--token','--token-file','--tokenFile','--username','--password','--client-key','--client-key-data',
               '--client-certificate','--client-certificate-data','--certificate-authority','--certificate-authority-data']
        for flag in flags:
            values.extend([flag+'=SYNTHETIC_NOT_A_SECRET', flag+' SYNTHETIC_NOT_A_SECRET',
                           json.dumps({'argv':['kubectl',flag,'SYNTHETIC_NOT_A_SECRET']})])
        for value in values:
            for encoded in [value,json.dumps({'Output':value}),json.dumps({'Output':json.dumps({'Output':value})})]:
                with self.subTest(credential=encoded),self.assertRaises(ValueError):ci.normalize_for_upload(encoded.encode())


if __name__=='__main__':unittest.main(verbosity=2)
