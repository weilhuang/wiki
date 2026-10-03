#!/usr/bin/env python3
"""Finite semantic variants. Baseline compilation/behavior must have passed first."""
import json
import re
import shutil
import tempfile
from pathlib import Path

VARIANTS = [
 {'id':'M01','case':'H10','marker':'HTTP_ERROR_BODY','changes':[
  ('internal/httpapi/http.go',r'writeError\(c, Status\(code\), string\(code\)\)', 'writeError(c, Status(code), err.Error())')]},
 {'id':'M02','case':'H03','marker':'HTTP_FORBIDDEN_STATUS','changes':[
  ('internal/domain/service.go',r'if \(write && !p.Reserve\) \|\| \(!write && !p.Read\)', 'if false')]},
 {'id':'M03','case':'D02','marker':'ROLLBACK_STOCK','changes':[
  ('internal/store/sql.go',r'result, err := tx.ExecContext\(ctx, "UPDATE products', 'result, err := s.DB.ExecContext(ctx, "UPDATE products'),
  ('internal/store/gorm.go',r'result = tx.Exec\("UPDATE products', 'result = s.DB.WithContext(ctx).Exec("UPDATE products')]},
 {'id':'M04','case':'D03','marker':'LAST_ITEM_STATES','changes':[
  ('internal/store/common.go',r'if rows == 0 \{\n\s*return "rejected", nil', 'if rows == 0 {\n return "confirmed", nil')]},
 {'id':'M05','case':'D06','marker':'CANCEL_IDENTITY','changes':[
  ('internal/store/sql.go',r'(func \(s \*SQL\) Reserve\([^\n]+\{)', r'\1\n ctx = context.Background()'),
  ('internal/store/gorm.go',r'(func \(s \*GORM\) Reserve\([^\n]+\{)', r'\1\n ctx = context.Background()')]},
 {'id':'M06','case':'G07','marker':'STREAM_SEND_ERROR','changes':[
  ('internal/grpcapi/grpc.go',r'(if err = stream.Send\(payload\(op\)\); err != nil \{\n\s*)return err', r'\1continue')]},
]

def verify_rejection(raw,variant):
 events=[json.loads(line) for line in raw.decode().splitlines()]
 unit=variant['case']=='G07'
 package='example.com/reservation-service/internal/grpcapi' if unit else 'example.com/reservation-service/tests'
 leaves={'TestG07StreamSendError'} if unit else {f"TestIntegration/{b}/{variant['case']}" for b in ('sql','gorm')}
 names=leaves|{'/'.join(name.split('/')[:i]) for name in leaves for i in range(1,len(name.split('/')))}
 if not events or any(e.get('Package')!=package for e in events):raise ValueError('unexpected package')
 if any(e.get('Action') not in ('start','run','output','fail') for e in events):raise ValueError('unexpected action or non-failing target')
 if sum(e['Action']=='start' and not e.get('Test') for e in events)!=1:raise ValueError('package start count')
 if sum(e['Action']=='fail' and not e.get('Test') for e in events)!=1:raise ValueError('package terminal count')
 if events[0]['Action']!='start' or events[0].get('Test') or events[-1]['Action']!='fail' or events[-1].get('Test'):raise ValueError('package lifecycle order')
 if any((e['Action']=='start' and e.get('Test')) or (e['Action']=='run' and not e.get('Test')) for e in events):raise ValueError('invalid event attribution')
 if {e['Test'] for e in events if e.get('Test')}!=names:raise ValueError('complete test inventory differs')
 for name in names:
  own=[e for e in events if e.get('Test')==name]
  if sum(e['Action']=='run' for e in own)!=1 or sum(e['Action']=='fail' for e in own)!=1:raise ValueError('test run/fail count differs')
  actions=[e['Action'] for e in own]
  if actions[0]!='run' or actions[-1]!='fail':raise ValueError('test lifecycle order')
  assertions=[];fixtures=0
  for event in own:
   if event['Action']!='output':continue
   for line in event.get('Output','').splitlines():
    text=line.strip()
    frame=re.fullmatch(r'(?:=== (?:RUN|NAME)\s+'+re.escape(name)+r'|--- FAIL: '+re.escape(name)+r' \([0-9]+(?:\.[0-9]+)?s\))',text)
    if frame:
     if event.get('OutputType')!='frame':raise ValueError('framework line is not a frame')
     continue
    if name not in leaves:raise ValueError('unclassified parent output')
    if event.get('OutputType')=='frame':raise ValueError('unexpected target frame')
    match=re.fullmatch(r'[A-Za-z0-9_./-]+\.go:[0-9]+: SEMANTIC_ASSERT (.+)',text)
    if match:
     if event.get('OutputType')!='error':raise ValueError('semantic assertion lacks Go error attribution')
     record=json.loads(match.group(1))
     if set(record)!={'marker','got','want'} or not all(isinstance(x,str) for x in record.values()):raise ValueError('invalid structured assertion')
     if record['marker']!=variant['marker']:raise ValueError('wrong semantic assertion')
     assertions.append(record)
    elif event.get('OutputType') is None and not unit and re.fullmatch(r'[A-Za-z0-9_./-]+\.go:[0-9]+: FIXTURE mysql=8\.4\.7 backend='+name.split('/')[1],text):fixtures+=1
    else:raise ValueError('unclassified leaf output or cleanup failure')
  if name in leaves and (len(assertions)!=1 or fixtures!=(0 if unit else 1)):raise ValueError('unique semantic assertion/fixture count differs')
 for event in events:
  if event.get('Test') or event['Action']!='output':continue
  for line in event.get('Output','').splitlines():
   text=line.strip()
   if text=='FAIL':
    if event.get('OutputType')!='frame':raise ValueError('unclassified package frame')
   elif event.get('OutputType')!='frame' or not re.fullmatch(r'FAIL\s+'+re.escape(package)+r'\s+[0-9]+(?:\.[0-9]+)?s',text):raise ValueError('unclassified package output')
 return {'package':package,'leaves':sorted(leaves),'marker':variant['marker'],'status':'uniquely-attributed-semantic-rejection'}


def run_variants(lab,work,run,go,environment):
 results=[]
 for variant in VARIANTS:
  with tempfile.TemporaryDirectory(prefix='variant-'+variant['id']+'-',dir=work) as temp:
   clone=Path(temp)/'source';shutil.copytree(lab,clone,ignore=shutil.ignore_patterns('__pycache__','.git','out','*.test'))
   for filename,pattern,replacement in variant['changes']:
    path=clone/filename;text=path.read_text();changed,count=re.subn(pattern,replacement,text)
    if count!=1:raise ValueError(variant['id']+' patch did not match exactly once')
    path.write_text(changed)
   if variant['case']=='G07':cmd=[go,'test','-tags=nomsgpack','-json','-count=1','-timeout=15s','-run=^TestG07StreamSendError$','./internal/grpcapi']
   else:cmd=[go,'test','-tags=integration,nomsgpack','-json','-count=1','-timeout=15s',f"-run=^TestIntegration$/^(sql|gorm)$/^{variant['case']}$",'./tests']
   result,raw=run(variant['id'],cmd,cwd=clone,env=environment,timeout=45,expected_exit=1)
   verify_rejection(raw,variant)
   results.append({'id':variant['id'],'case':variant['case'],'marker':variant['marker'],'status':'detected','command_record':result})
 return results
