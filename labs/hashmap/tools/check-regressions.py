#!/usr/bin/env python3
"""显式验证本实验的验证器：隔离修改教学代码，不修改 JDK 或原始源码。需要已安装 JDK21。"""
from pathlib import Path
import difflib, hashlib, json, os, shutil, subprocess, tempfile
root=Path(__file__).resolve().parent.parent
out=root/'proof/r2-regressions'
out.mkdir(parents=True,exist_ok=True)
source=(root/'experiments/src/HashMapLab.java').read_text()
mutants=[
    ('wrong-exception', 'throw new AssertionError("ASSERTION_FAILED: " + message);', 'throw new IllegalStateException("ASSERTION_FAILED: " + message);', ['反向断言未按预期失败: equal-adds', 'java.lang.IllegalStateException: ASSERTION_FAILED: wrong hypothesis equal-adds']),
    ('compute-wrong-value', 'k -> 8);', 'k -> 800);', ['java.lang.AssertionError:', 'eighth value expected=8 actual=800']),
    ('bad-positive', 'equal(1, map.size(), "equal key must not add mapping");', 'equal(99, map.size(), "equal key must not add mapping");', ['java.lang.AssertionError:', 'equal key must not add mapping expected=99 actual=1']),
    ('wrong-negative-scenario', '"wrong hypothesis equal-adds"', '"wrong hypothesis unrelated-scenario"', ['反向断言未按预期失败: equal-adds', 'wrong hypothesis unrelated-scenario']),
    ('negative-unexpected-success', 'equal(2, map.size(), "wrong hypothesis equal-adds");', 'equal(1, map.size(), "wrong hypothesis equal-adds");', ['反向断言未按预期失败: equal-adds', 'Negative hypothesis unexpectedly survived: equal-adds']),
    ('compute-drops-old-mapping', 'equal(8, result, "computeIfAbsent returns independently expected eighth value");', 'map.remove(collision(1));\n        equal(8, result, "computeIfAbsent returns independently expected eighth value");', ['java.lang.AssertionError:', 'adds exactly one mapping expected=8 actual=7']),
    ('compute-corrupts-old-value', 'equal(8, result, "computeIfAbsent returns independently expected eighth value");', 'map.put(collision(3), 300);\n        equal(8, result, "computeIfAbsent returns independently expected eighth value");', ['java.lang.AssertionError:', 'preserves every expected value expected=3 actual=300']),
]
results=[]
with tempfile.TemporaryDirectory(prefix='hashmap-r2-mutants-') as tmp:
    for name,old,new,expected in mutants:
        assert source.count(old)==1,(name,'ambiguous mutation target',source.count(old))
        changed=source.replace(old,new)
        work=Path(tmp)/name
        shutil.copytree(root/'experiments',work,ignore=shutil.ignore_patterns('.run'))
        (work/'src/HashMapLab.java').write_text(changed)
        result=subprocess.run(['bash',str(work/'run.sh'),'verify',str(work/'output')],cwd=work,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=90,env=os.environ.copy())
        case=out/name;case.mkdir(exist_ok=True)
        (case/'console.txt').write_text(result.stdout)
        (case/'mutation.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True),changed.splitlines(True),fromfile='baseline/HashMapLab.java',tofile=name+'/HashMapLab.java')))
        assert result.returncode==1,(name,result.returncode,result.stdout)
        assert 'PASS runner mode=verify' not in result.stdout,(name,'false green')
        for text in expected:assert text in result.stdout,(name,'wrong failure mechanism',text,result.stdout)
        results.append({'name':name,'exitCode':result.returncode,'expectedExitCode':1,'acceptedByVerifier':False,'baselineSourceSHA256':hashlib.sha256(source.encode()).hexdigest(),'mutantSourceSHA256':hashlib.sha256(changed.encode()).hexdigest(),'requiredFailureEvidence':expected,'artifacts':['proof/r2-regressions/'+name+'/console.txt','proof/r2-regressions/'+name+'/mutation.patch']})
        print('REJECTED_MUTANT',name,'exit=1')
(root/'proof/r2-regressions/results.json').write_text(json.dumps({'status':'pass','scope':'Verifier regression tests; mutations target only this educational lab, never the JDK','count':len(results),'results':results},ensure_ascii=False,indent=2)+'\n')
print('PASS verifier regressions='+str(len(results)))
