#!/usr/bin/env python3
"""Allowlisted source and text-evidence ZIP packaging. SPDX-License-Identifier: MIT."""
import argparse,hashlib,json,pathlib,tempfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parent
ROOT_FILES={'README.md','LICENSE','run.py','check_evidence.py','regression_probes.py','verify_revision.py','package_public.py','sources.json','source-review.json','runtime.json','snippets.json','verification.json'}
JAVA_FILES={'ChildFailures.java','Publication.java','JmmLab.java','ExecutorLab.java','DiagnosticLab.java','PoolCleanup.java','HarnessContracts.java'}
UPSTREAM={'ThreadPoolExecutor','AbstractExecutorService','FutureTask'}
PROOF_FILES={'java-version.txt','javac-version.txt','compile.txt','jmm.txt','executor.txt','negative-volatile.txt','negative-max-first.txt','negative-drain.txt','threads-before.txt','threads-after.txt','diagnostic.txt','diagnostic-summary.json','gc.log','result.json','harness-contracts.txt'}
CASES={'atomic-child','diagnostic-child','executor-child','future-wrong-cause','ordinary-future-child'}
def allowed(relative):
 p=pathlib.PurePosixPath(relative);parts=p.parts
 if not parts or p.is_absolute() or any(x.startswith('.') or x=='..' for x in parts):return False
 if len(parts)==1:return parts[0] in ROOT_FILES
 if parts[0]=='src':return len(parts)==2 and parts[1] in JAVA_FILES
 if parts[0]=='licenses':return len(parts)==2 and parts[1] in {'LICENSE-openjdk','ADDITIONAL_LICENSE_INFO','ASSEMBLY_EXCEPTION'}
 if parts[0]=='sources':
  if len(parts)==2:return any(parts[1]==cls+suffix for cls in UPSTREAM for suffix in ['-jdk-21+35.java','-runtime-21.0.12.1.java'])
  if relative in {'sources/history/jcmd-attempt/run.py','sources/history/jcmd-attempt/src/DiagnosticLab.java'}:return True
  if parts[1:3]==('history','r2-review'):
   return (len(parts)==4 and parts[3] in {'run.py','runtime_probes.py'}) or (len(parts)==5 and parts[3]=='src' and parts[4] in {'ChildFailures.java','Publication.java','JmmLab.java','ExecutorLab.java','DiagnosticLab.java'})
  return False
 if parts[0]=='proof':
  if len(parts)==2:return parts[1] in {'jcmd-attempt.json','evidence-check.json','package-check.json'}
  if parts[1:3]==('history','r2-review'):
   return len(parts)==4 and parts[3] in {'baseline-negative-max-first.txt','baseline-result.json','executor-child-exception.txt','failure-summary.json'}
  if parts[1]=='run-r4':return len(parts)==3 and parts[2] in PROOF_FILES
  if parts[1]=='r3-regressions':
   if len(parts)==3:return parts[2]=='result.json'
   if parts[2] not in CASES:return False
   if len(parts)==4:return parts[3] in {'mutation.diff','run.py','runner.txt'}
   if len(parts)==5 and parts[3]=='src':return parts[4] in JAVA_FILES
   if len(parts)==5 and parts[3]=='proof':return parts[4] in PROOF_FILES
 return False

def package(destination):
 selected=[];excluded=[]
 for p in sorted(ROOT.rglob('*')):
  if p.is_symlink():raise AssertionError('no symlinks allowed in public package')
  if not p.is_file():continue
  relative=p.relative_to(ROOT).as_posix()
  if not allowed(relative):excluded.append(relative);continue
  selected.append((relative,p))
 # Reject regressions in the policy itself, independent of whether residue currently exists.
 rejected=['.attach_pid143','.attach_pid999','src/Bad.class','src/.cache.java','__pycache__/run.pyc','proof/run-r4/heap.hprof','proof/run-r4/lib.so','unrelated.txt','../secret','/tmp/private','proof/.attach_pid1']
 assert all(not allowed(p) for p in rejected)
 assert all(allowed(p) for p in ['src/JmmLab.java','proof/run-r4/gc.log','sources/history/jcmd-attempt/run.py','licenses/ADDITIONAL_LICENSE_INFO'])
 record={'status':'pass','policy':'Explicit paths for source, licenses, metadata and text evidence only; no hidden/runtime/cache/binary files','deniedFixturePaths':rejected,'excludedFiles':excluded}
 (ROOT/'proof/package-check.json').write_text(json.dumps(record,indent=2)+'\n')
 if not any(x[0]=='proof/package-check.json' for x in selected):selected.append(('proof/package-check.json',ROOT/'proof/package-check.json'))
 with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for relative,p in sorted(selected):
   b=p.read_bytes()
   assert all(x not in b for x in [b'/' + b'workspace/',b'/' + b'home/agent/',b'/' + b'root/.']),relative+' leaks private path'
   info=zipfile.ZipInfo('java-service-mechanisms-lab/'+relative,(2026,10,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,b)
 return {'fileCount':len(selected),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'excludedFiles':excluded}
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=pathlib.Path);args=parser.parse_args()
 if args.output.exists():raise SystemExit('Refusing to overwrite package')
 print(json.dumps(package(args.output),indent=2))
