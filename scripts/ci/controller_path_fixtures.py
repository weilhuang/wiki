"""Synthetic complete records for evidence-gate tests; never execution evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil


def stream(expected, terminal='pass', marker=None, leaf=None):
    events=[]
    for package,names in expected.items():
        events.append({'Action':'start','Package':package})
        for name in names:
            events.extend([{'Action':'run','Package':package,'Test':name},
                {'Action':'output','Package':package,'Test':name,'OutputType':'frame','Output':'=== RUN   '+name+'\n'}])
        if marker:
            events.append({'Action':'output','Package':package,'Test':leaf,'OutputType':'error',
                           'Output':'    contract_test.go:10: SEMANTIC_ASSERT '+json.dumps({'marker':marker,'got':'wrong','want':'correct'})+'\n'})
        for name in reversed(names):
            events.extend([{'Action':'output','Package':package,'Test':name,'OutputType':'frame','Output':'--- '+terminal.upper()+': '+name+' (0.01s)\n'},
                           {'Action':terminal,'Package':package,'Test':name}])
        events.append({'Action':'output','Package':package,'OutputType':'frame','Output':terminal.upper()+'\n'})
        summary={'Action':'output','Package':package,'Output':('ok' if terminal=='pass' else 'FAIL')+'\t'+package+'\t0.01s\n'}
        if terminal=='fail': summary['OutputType']='frame'
        events.extend([summary,{'Action':terminal,'Package':package}])
    return events


def command_trace(ci,cluster):
    owner=cluster['lifecycle']['cluster_name']; tags=cluster['lifecycle']['image_tags']; commands=[]
    config=cluster['lifecycle']['kubeconfig']
    prefix=['kubectl','--kubeconfig',config,'--context','kind-'+owner,'--request-timeout=10s','--cache-dir',str(Path(config).parent/'kubectl-cache'),'-n','p3-lab']
    def add(case,argv,expected=None,stdout=''):
        stderr=('Forbidden: fixture' if expected and 'Forbidden' in expected else 'Error: No such image: '+argv[-1] if expected else '')
        argv=[cluster['tool_paths'][argv[0]],*argv[1:]]
        commands.append({'id':len(commands)+1,'case_id':case,'argv':argv,'timeout_seconds':30,'elapsed_seconds':.01,
            'exit_code':1 if expected else 0,'stdout_sha256':hashlib.sha256(stdout.encode()).hexdigest(),
            'stderr_sha256':hashlib.sha256(stderr.encode()).hexdigest(),'stdin_sha256':hashlib.sha256(b'').hexdigest(),
            'stdout_tail':stdout,'stderr_tail':stderr,'stdout_bytes':len(stdout.encode()),'stderr_bytes':len(stderr.encode()),'stdin_bytes':0,
            'allow_failure':expected is not None,'expected_failure':expected,'output_limit_bytes':524288,
            'process_group_cleanup':True,'owned_process_group':10000+len(commands),'lingering_children':False,'parent_reaped':True,'termination_sent':False})
    for case,operations in ci.COMMAND_COVERAGE.items():
        if case=='DiagnosticsCollected':
            add(case,prefix+['logs','deployment/manager','--tail=150','--limit-bytes=32768'],stdout='{"level":"info","msg":"fixture"}\n')
            for resource in ['events','appservices,deployments,replicasets,services,pods']:
                add(case,prefix+['get',resource,'-o','json'],stdout='{"apiVersion":"v1","kind":"List","items":[]}\n')
            continue
        if case=='BuildLocalImages':
            for tag in tags:add(case,['docker','image','inspect','--format','{{.Id}}',tag],'No such image or No such object proves generated tag initially absent')
        for operation in sorted(operations):
            tool,verb=operation.split(':',1)
            if tool=='kubectl':
                if case=='ToolVersions': argv=['kubectl','version','--client=true','-o','json']
                else:
                    get_targets = {
                        'OwnedDeploymentService':['appservice','sample'], 'ReadyPodAndCurrentCondition':['appservice','sample'],
                        'WorkloadSecurityContract':['pods'], 'HTTPThroughServiceDNS':['pod','request'],
                        'ScaleToTwoAndBack':['deployment','sample'], 'CurrentGenerationNotReady':['appservice','sample'],
                        'ForeignResourcesPreserved':['service','foreign-service'], 'DriftRepaired':['service','sample'],
                        'DeletedChildRecreated':['service','sample'], 'ControllerRestartConverges':['pods'],
                        'OwnerGarbageCollection':['replicasets'],
                    }
                    if verb=='get':
                        tail = (['--as=system:serviceaccount:p3-lab:manager','get','deployments','-o','name']
                                if case=='ManagerNamespacedRBAC' else ['get',*get_targets[case],'--ignore-not-found','-o','json'])
                    elif verb=='patch':
                        resource,payload = {
                            'ScaleToTwoAndBack':('appservice/sample',{'spec':{'replicas':2}}),
                            'CurrentGenerationNotReady':('appservice/sample',{'spec':{'image':'wiki-p3-unavailable-'+cluster['run_id']+':must-not-pull'}}),
                            'DriftRepaired':('service/sample',{'spec':{'selector':{'lab.wiki.example/owner-uid':'wrong'}}}),
                            'ControllerRestartConverges':('service/sample',{'spec':{'selector':{'lab.wiki.example/owner-uid':'stopped-drift'}}}),
                        }[case]
                        tail=['patch',resource,'--type=merge','-p',json.dumps(payload)]
                    elif verb=='delete':tail=['delete','appservice/sample','--cascade=background','--wait=true','--timeout=20s'] if case=='OwnerGarbageCollection' else ['delete','service/sample','--wait=true','--timeout=20s']
                    elif verb=='rollout':tail=['rollout','status','deployment/manager','--timeout='+('80s' if case=='ManagerNamespacedRBAC' else '60s')]
                    elif verb=='logs':tail=['logs','pod/'+('request' if case=='HTTPThroughServiceDNS' else 'request-after-restart'),'--limit-bytes=1024']
                    elif verb=='version':tail=['version','-o','json']
                    elif verb=='wait':tail=['wait','--for=condition=Established','--timeout=30s','crd/appservices.lab.wiki.example']
                    elif verb=='scale':tail=['scale','deployment/manager','--replicas=0']
                    elif verb=='apply':tail=['apply','-f','-']
                    else:raise AssertionError('fixture operation missing')
                    argv=prefix+tail
                add(case,argv)
            elif tool=='kind':
                argv=['kind',*verb.split()]
                if verb.startswith(('create','load','delete')):argv+=['--name',owner]
                if verb=='create cluster':argv+=['--image',cluster['node_image'],'--kubeconfig',config,'--wait','100s']
                if verb=='load docker-image':argv+=tags
                add(case,argv)
            elif tool=='go':
                if verb=='build':
                    for name in ['manager','operand']:add(case,['go','build','-mod=readonly','-trimpath','-o','/owned/'+name,'./cmd/'+name])
                else:add(case,['go','version'])
            elif tool=='docker':
                if verb=='build':
                    for tag in tags:add(case,['docker','build','--network=none','-t',tag,'/owned/context'])
                elif verb.startswith('image '):
                    for tag in tags:add(case,['docker',*verb.split(),tag])
                else:add(case,['docker','version'])
        if case=='ManagerNamespacedRBAC':
            for resource,extra in [('secrets',[]),('deployments',['-n','p3-other']),('namespaces',[])]:
                add(case,prefix+['--as=system:serviceaccount:p3-lab:manager','get',resource]+extra+['-o','name'],'Kubernetes API Forbidden for manager service account')
        if case=='OwnedImagesRemoved':
            for tag in tags:add(case,['docker','image','inspect','--format','{{.Id}}',tag],'No such image or No such object for the generated image tag')
    return commands


def fixture(ci,root):
    inventory={'unit':{'pkg':['TestContract']},'integration':{'integration':['TestAPI','TestAPI/Example']},
               'kind':list(ci.COMMAND_COVERAGE),'harness_unit':['SyntheticOracle'],
               'mutants':['foreign-deployment-write','stale-rollout-ready','recreated-uid-stamped','allocated-service-ip-erased']}
    (root/'test-inventory.json').write_text(json.dumps(inventory));(root/'scripts').mkdir()
    for name in ['check_mutants.py','go_events.py','owned_process.py']:
        shutil.copyfile(ci.LAB/'scripts'/name,root/'scripts'/name)
    before={}
    for name in ['api/v1alpha1/zz_generated.deepcopy.go','config/crd/lab.wiki.example_appservices.yaml','internal/controller/reconciler.go']:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ci.LAB/name,target)
        before['labs/go-cloudnative-controller-path/'+name]=hashlib.sha256(target.read_bytes()).hexdigest()
    identity=ci.source_id(before);encoded=lambda value:json.dumps(value).encode()
    (root/'reviewed.json').write_bytes(encoded({'source_id':identity,'source_sha256':before}))
    files={name:b'' for name in ci.PUBLIC_FILES|{'kind.log','kind-manager.log','kind-events.json','kind-resources.json'}}
    files['source-before.json']=files['source-after.json']=encoded(before)
    files['provenance.json']=encoded({'source_id':identity,'repository':'weilhuang/wiki','scope':'p3-api-cache-reconcile-real-envtest-and-kind',
        'checkout_sha':'a'*40,'pr_head_sha':'b'*40,'pr_base_sha':'c'*40,'contract_sha256':hashlib.sha256((root/'reviewed.json').read_bytes()).hexdigest()})
    pins=json.loads(ci.PIN_FILE.read_text())
    files['assets.json']=encoded({'status':'verified','pins_sha256':hashlib.sha256(ci.PIN_FILE.read_bytes()).hexdigest(),
        'downloads':{name:{'sha256':pins[name]['sha256']} for name in ['kind','kubectl','envtest']}})
    stage={'status':'pass','exit_code':0,'process_group_cleanup':True,'timed_out':False,'output_bound_exceeded':False,'source_id':identity}
    for name in ['dependencies','module-verify','harness-oracle','unit','integration','kind','generated','mutants']:
        files[name+'-stage.json']=encoded({**stage,'command':ci.expected_stage_commands(identity)[name]})
    for name in ['unit','integration']:
        files[name+'.jsonl']=b''.join(encoded(e)+b'\n' for e in stream(inventory[name]))
        files[name+'-stage.json']=encoded({**stage,'command':ci.expected_stage_commands(identity)[name],'tests':ci.test_events(files[name+'.jsonl'],inventory[name])})
    files['harness-oracle.json']=encoded({'schema_version':1,'status':'pass','exit_code':0,'source_id':identity,'layer':'pure-harness-oracle','cases':[{'id':'SyntheticOracle','status':'pass'}]})
    generator='sigs.k8s.io/controller-tools/cmd/controller-gen@v0.22.0'
    files['generated.json']=encoded({'status':'pass','exit_code':0,'source_id':identity,'layer':'pinned-controller-gen-golden',
        'temporary_copy_removed':True,'generator':generator,'generator_exit_code':0,
        'command':['go','run',generator,'object','crd','paths=./api/...','output:crd:artifacts:config=config/crd'],
        'outputs_removed_before_run':True,'source_tree_unchanged':True,'unexpected_outputs':False,'private_root_mode':0o700,
        'files':[{'path':name.removeprefix('labs/go-cloudnative-controller-path/'),'sha256':value,'expected_sha256':value,
                  'identical':True,'fresh_regular_file':True,'mode':0o644} for name,value in before.items() if 'reconciler.go' not in name]})
    spec=importlib.util.spec_from_file_location('fixture_mutants',root/'scripts/check_mutants.py');mutants=importlib.util.module_from_spec(spec);spec.loader.exec_module(mutants)
    rows=[];original=(root/'internal/controller/reconciler.go').read_text()
    for m in mutants.MUTANTS:
        encode_stream=lambda v:'\n'.join(json.dumps(e) for e in v)
        rows.append({'id':m['id'],'status':'pass','baseline_exit_code':0,'exit_code':1,'test':m['test'],'assertion':m['message'],
            'command':mutants.command_for(m),'mutant_file_sha256':hashlib.sha256(mutants.changed_source(original,m).encode()).hexdigest(),
            'baseline_jsonl':encode_stream(stream({mutants.PACKAGE:m['names']})),
            'mutant_jsonl':encode_stream(stream({mutants.PACKAGE:m['names']},'fail',m['message'],m['test']))})
    files['mutants.json']=encoded({'status':'pass','exit_code':0,'source_id':identity,'layer':'go-unit-semantic-mutants','temporary_copies_removed':True,'cases':rows})
    files['envtest-report.json']=encoded({'schema_version':1,'status':'pass','exit_code':0,'source_id':identity,'layer':'envtest-real-manager','server_version':pins['kubernetes'],
        'readiness_inputs':'simulated','cases':[{'id':'Example','status':'pass'}],
        'lifecycle':[{'event':e,'status':'pass'} for e in ['control_plane_start','server_version','manager_start','manager_cache_sync','manager_stop','manager_start','manager_cache_sync','manager_stop','control_plane_stop']]})
    suffix='a'*12;owner='wiki-p3-'+suffix;tags=['wiki-p3-manager-'+suffix+':local','wiki-p3-operand-'+suffix+':local']
    cluster={'schema_version':1,'status':'pass','exit_code':0,'run_id':suffix,'source_id':identity,'layer':'kind-real-workloads','node_image':pins['kind_node_image'],
        'tool_paths':{'go':'/fixture/bin/go','docker':'/fixture/bin/docker','kind':str(ci.PRIVATE/'tools/kind'),'kubectl':str(ci.PRIVATE/'tools/kubectl')},
        'cases':[{'id':case,'status':'pass'} for case in inventory['kind']],
        'lifecycle':{'cluster_name':owner,'namespace':'p3-lab','image_tags':tags,'cleanup_budget_seconds':{'cluster':64,'images':[28,28],'filesystem_and_reporting':20,'total':140},'kubeconfig':'/tmp/'+owner+'-fixture/kubeconfig',
            'events':[{'event':'image_absence_before_build','status':'pass','tag':tag} for tag in tags]+[{'event':'cluster_delete','status':'pass','name':owner}]+
                     [{'event':'image_delete','status':'pass','tag':tag} for tag in tags]+[{'event':'private_workspace_remove','status':'pass','kubeconfig_absent':True}]}}
    cluster['commands']=command_trace(ci,cluster);files['kind-report.json']=encoded(cluster)
    for name,tail in [('kind-manager.log','deployment/manager'),('kind-events.json','events'),('kind-resources.json','appservices,deployments,replicasets,services,pods')]:
        files[name]=next(c['stdout_tail'].encode() for c in cluster['commands'] if c['case_id']=='DiagnosticsCollected' and c['argv'][11]==tail)
    return files,before
