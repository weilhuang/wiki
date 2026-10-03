#!/usr/bin/env python3
"""Fail-closed verification of Go JSON test records; no implementation-derived oracle."""
import argparse
import json
from pathlib import Path

MODULE = 'example.com/reservation-service'
PINNED = {
 'go':'go1.27.1', 'mysql':'8.4.7', 'protoc':'libprotoc 36.2',
 'protoc-gen-go':'protoc-gen-go v1.36.11',
 'protoc-gen-go-grpc':'protoc-gen-go-grpc 1.6.1',
 'github.com/gin-gonic/gin':'v1.12.0', 'github.com/go-sql-driver/mysql':'v1.10.1',
 'gorm.io/gorm':'v1.31.2', 'gorm.io/driver/mysql':'v1.6.0',
 'google.golang.org/grpc':'v1.84.0', 'google.golang.org/protobuf':'v1.36.11',
}
INTEGRATION = {f'TestIntegration/{b}/{prefix}{i:02d}' for b in ('sql','gorm') for prefix,count in (('H',11),('D',10),('G',6)) for i in range(1,count+1)} | {f'TestProcess/P{i:02d}' for i in range(1,5)}
UNIT={'TestG07StreamSendError'}

def load_events(path):
 lines=Path(path).read_text().splitlines()
 if not lines:raise ValueError('empty test record')
 events=[json.loads(line) for line in lines]
 if any(not isinstance(e,dict) or 'Action' not in e for e in events):raise ValueError('invalid event')
 return events

def verify(events,expected,package):
 runs={};terminals={};package_terminal=[]
 for event in events:
  if event.get('Package')!=package:raise ValueError('unexpected package')
  action=event['Action'];name=event.get('Test')
  if action in ('skip','fail'):raise ValueError('failed or skipped test/package')
  if action=='run':
   if not name:raise ValueError('run without name')
   runs[name]=runs.get(name,0)+1
  if action=='pass':
   if name:terminals[name]=terminals.get(name,0)+1
   else:package_terminal.append(action)
 if not expected.issubset(runs) or not expected.issubset(terminals):raise ValueError('required case missing')
 if not runs or runs.keys()!=terminals.keys():raise ValueError('empty or incomplete test execution')
 if any(n!=1 for n in list(runs.values())+list(terminals.values())):raise ValueError('duplicate test execution')
 if package_terminal!=['pass']:raise ValueError('missing or duplicate package success')
 return sorted(expected)

def verify_versions(actual):
 if any(actual.get(k)!=v for k,v in PINNED.items()):raise ValueError('missing or wrong version')
 if actual.get('mysql_image')!='mysql@sha256:0426ec38c7a10aa45ba383887df7878f74ee70e2fd589c7b69207f3577901903':raise ValueError('wrong mysql image')
 if actual.get('mysql_architecture')!='amd64':raise ValueError('unexpected mysql architecture')

def main():
 p=argparse.ArgumentParser();p.add_argument('integration');p.add_argument('unit');p.add_argument('versions');p.add_argument('--output',required=True);a=p.parse_args()
 record={'status':'fail','level':'real-mysql-tcp-and-process'}
 try:
  versions=json.loads(Path(a.versions).read_text());verify_versions(versions)
  record.update(integration=verify(load_events(a.integration),INTEGRATION,MODULE+'/tests'),unit=verify(load_events(a.unit),UNIT,MODULE+'/internal/grpcapi'),versions=versions,status='pass')
 except (ValueError,OSError,KeyError,TypeError) as e:
  record['reason']=str(e)
 Path(a.output).write_text(json.dumps(record,indent=2)+'\n')
 return 0 if record['status']=='pass' else 1
if __name__=='__main__':raise SystemExit(main())
