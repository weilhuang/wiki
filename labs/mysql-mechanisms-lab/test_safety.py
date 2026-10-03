#!/usr/bin/env python3
"""Pure stdlib control-flow regressions; no Docker, no MySQL execution."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cases
import safety
from driver import Evidence, InfraFailure
from trace_contract import required_assertions,validate_assertion_sequence,validate_event

class SafetyTests(unittest.TestCase):
    def test_dotdot_and_symlink_ancestors(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'real').mkdir()
            (p/'link').symlink_to(p/'real',target_is_directory=True)
            for value in [str(p/'link'/'out'),str(p)+'/real/../out']:
                with self.assertRaises(RuntimeError): safety.safe_path(value)
    def test_identity_empty_and_wrong_shape(self):
        env={'GITHUB_ACTIONS':'true','RUNNER_OS':'Linux','GITHUB_RUN_ID':'12','GITHUB_RUN_ATTEMPT':'1','PR_HEAD_SHA':'a'*40,'PR_BASE_SHA':'b'*40,'GITHUB_REPOSITORY':'owner/repo','GITHUB_REF':'refs/pull/1/merge','GITHUB_EVENT_NAME':'pull_request','GITHUB_WORKFLOW_REF':'owner/repo/.github/workflows/mysql-mechanisms-lab.yml@refs/pull/1/merge'}
        with patch.dict(os.environ,env,clear=True):
            self.assertEqual(safety.ci_identity()['github_run_id'],'12')
            for key in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','PR_HEAD_SHA','PR_BASE_SHA'):
                old=os.environ[key]
                for value in ('','../oops','0'):
                    os.environ[key]=value
                    with self.assertRaises(RuntimeError): safety.ci_identity()
                os.environ[key]=old
    def test_bounded_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'index.json'
            p.write_text('{"owner":"'+'a'*2048+'"}')
            with self.assertRaises(RuntimeError): safety.read_json(p,1024)
    def test_missing_pass_and_wrong_semantics(self):
        with self.assertRaises(RuntimeError): safety.validate_mode({'status':'PASS'},'baseline')
        good={'mode':'mutant-rc-for-rr','status':'SEMANTIC_MISMATCH','exit_code':42,'sessions_clean':True,'assertion':'rr.repeat','expected':['10'],'observed':['11']}
        safety.validate_mode(good,'mutant-rc-for-rr')
        for patch_value in ({'exit_code':43},{'assertion':'identity.version'},{'sessions_clean':False},{'observed':['10']}):
            with self.assertRaises(RuntimeError): safety.validate_mode({**good,**patch_value},'mutant-rc-for-rr')
    def test_close_continues_after_exception(self):
        calls=[]
        class Fake:
            def __init__(self,name): self.name=name
            def close(self):
                calls.append(self.name)
                if self.name=='B': raise RuntimeError('synthetic close')
                return True
        with tempfile.TemporaryDirectory() as d:
            lab=cases.Lab(None,Evidence(Path(d)))
            lab.sessions=[Fake('observer'),Fake('A'),Fake('B')]
            self.assertFalse(lab.close())
            self.assertEqual(calls,['B','A','observer'])
    def test_partial_initialize_cleanup_is_owned(self):
        calls=[]
        class Fake:
            def __init__(self,container,ev,name):
                if name=='B': raise InfraFailure('synthetic constructor')
                self.name=name
            def close(self): calls.append(self.name); return True
        class Args: container='b'*64; owner='a'*32
        with tempfile.TemporaryDirectory() as d:
            lab=cases.Lab(Args(),Evidence(Path(d)))
            with patch.object(cases,'Session',Fake),patch.object(cases.subprocess,'check_output',return_value='a'*32):
                with self.assertRaises(InfraFailure): lab.initialize()
            self.assertTrue(lab.close())
            self.assertEqual(calls,['A','observer'])
    def test_fake_empty_business_evidence(self):
        events=[{'kind':'case_pass','case':x} for x in safety.CASE_NAMES]
        with self.assertRaises(RuntimeError): validate_assertion_sequence(events,'baseline',{'status':'PASS'})
        self.assertEqual(len(required_assertions('baseline')),39)
        self.assertEqual(len(required_assertions('mutant-missing-tenant')),2)
        self.assertEqual(required_assertions('mutant-rc-for-rr')[-1][0],'rr.repeat')
        self.assertEqual(required_assertions('mutant-stale-write')[-1][0],'own.mixed-view')
    def test_diagnostic_schema_rejects_environment(self):
        with self.assertRaises(RuntimeError):validate_event({'sequence':1,'kind':'dump_environment','payload':'synthetic'})
    def test_secure_read_rejects_replaced_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'original').write_text('safe')
            (p/'outside').write_text('synthetic-canary')
            self.assertEqual(safety.secure_read(p/'original',100),b'safe')
            (p/'original').unlink()
            (p/'original').symlink_to(p/'outside')
            with self.assertRaises(RuntimeError):safety.secure_read(p/'original',100)
    def test_fifo_is_rejected_without_waiting_for_writer(self):
        with tempfile.TemporaryDirectory() as d:
            fifo=Path(d)/'fifo'
            os.mkfifo(fifo)
            with self.assertRaises(RuntimeError):safety.secure_read(fifo,100)
    def test_malformed_and_oversized_trace(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace.jsonl'
            for text in ('not-json\n','{"sequence":2,"kind":"case_pass"}\n','x'*(513*1024)):
                p.write_text(text)
                with self.assertRaises((RuntimeError,json.JSONDecodeError)):
                    safety.validate_trace(p,'baseline',{'status':'PASS'})

if __name__=='__main__': unittest.main(verbosity=2)
