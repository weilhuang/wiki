#!/usr/bin/env python3
"""Synthetic artifact boundary tests only; never real MySQL/Redis proof."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("evidence", SOURCE / "scripts/ci/data_evidence.py")
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wiki-evidence-unit-")
        self.root = Path(self.temp.name)
        e.ROOT = self.root
        e.LAB = self.root / "labs/data-consistency"
        shutil.copytree(SOURCE / "labs/data-consistency", e.LAB)
        e.TEMP = self.root / "temp"
        e.TEMP.mkdir()
        e.PRIVATE = e.TEMP / "wiki-data-evidence-private"
        e.UPLOAD = e.TEMP / "wiki-data-evidence-upload"
        e.PRIVATE.mkdir()
        self.output = self.root / "github-output"
        self.env = patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output)})
        self.env.start()
        self.manifest = e.source_manifest()
        e.write(e.PRIVATE / "source-before.json", self.manifest)
        e.write(e.PRIVATE / "provenance.json", {"unit_test": True, "not_service_evidence": True})
        self.run = e.LAB / "results" / ("a" * 32)
        self.run.mkdir(parents=True)
        cases = e.expected_cases()
        ledger = dict(line.split("=", 1) for line in (e.LAB / "infra/versions.env").read_text().splitlines() if line and not line.startswith("#"))
        self.report = {"status": "PASS", "chapter": "all", "scope": "real_mysql_redis_single_node_controlled_delivery_receiver",
                       "production_or_real_broker_verified": False, "expected_cases": cases,
                       "cases": [{"case": name, "status": "PASS", "observed": {"unit_fixture": True}} for name in cases],
                       "environment": {"images": ledger, "mysql": ["8.4.7\tREPEATABLE-READ\t1\tInnoDB"], "redis_server": "redis_version:7.4.7"},
                       "source_sha256": self.manifest,
                       **{key: 0 for key in ("run_exit_code", "cleanup_exit_code", "logs_exit_code", "ps_exit_code")}}
        for filename in e.REQUIRED:
            (self.run / filename).write_text("Synthetic unit fixture, not service evidence\n")
        e.write(self.run / "result.json", self.report)
        (self.run / "exit-codes.txt").write_text("run_exit_code=0\ncleanup_exit_code=0\nlogs_exit_code=0\nps_exit_code=0\n")
        trace = [{"kind": kind, "name": name} for name in cases for kind in ("case_begin", "case_pass")]
        trace += [{"kind": "sql_result"}, {"kind": "redis"}]
        (self.run / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
        (self.run / "image-ids.txt").write_text(("sha256:" + "b" * 64 + "\n") * 2)
        (self.run / "image-digests.txt").write_text((json.dumps(["unit/image@sha256:" + "c" * 64]) + "\n") * 2)

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def validation(self):
        return json.loads((e.UPLOAD / "validation.json").read_text())

    def test_bounded_valid_fixture(self):
        self.assertEqual(e.collect(), 0)
        self.assertEqual(self.validation()["cases"], 23)
        self.assertEqual(self.output.read_text(), "upload_ready=true\n")

    def test_missing_case_fails_and_retains_safe_diagnostics(self):
        self.report["cases"].pop()
        e.write(self.run / "result.json", self.report)
        self.assertEqual(e.collect(), 1)
        self.assertEqual(self.validation()["status"], "FAIL")
        self.assertTrue((e.UPLOAD / "trace.jsonl").exists())

    def test_existing_upload_directory_never_authorized(self):
        e.UPLOAD.mkdir()
        (e.UPLOAD / "untrusted.txt").write_text("do not upload")
        self.assertEqual(e.collect(), 1)
        self.assertFalse(self.output.exists())

    def test_symbolic_upload_directory_never_authorized(self):
        target = self.root / "outside-upload"
        target.mkdir()
        e.UPLOAD.symlink_to(target, target_is_directory=True)
        self.assertEqual(e.collect(), 1)
        self.assertFalse(self.output.exists())

    def test_symbolic_results_parent_rejected(self):
        original = e.LAB / "results"
        outside = self.root / "outside-results"
        original.rename(outside)
        original.symlink_to(outside, target_is_directory=True)
        self.assertEqual(e.collect(), 1)
        self.assertEqual(list(e.UPLOAD.iterdir()), [e.UPLOAD / "validation.json"])

    def test_symlink_file_rejected(self):
        (self.run / "start.log").unlink()
        (self.run / "start.log").symlink_to(e.LAB / "README.md")
        self.assertEqual(e.collect(), 1)
        self.assertTrue(self.validation()["raw_proof_withheld"])

    def test_oversize_file_rejected(self):
        (self.run / "start.log").write_bytes(b"x" * (e.PER_FILE + 1))
        self.assertEqual(e.collect(), 1)
        self.assertTrue(self.validation()["raw_proof_withheld"])

    def test_source_mutation_rejected(self):
        with (e.LAB / "README.md").open("a") as stream:
            stream.write("\nChanged after execution\n")
        self.assertEqual(e.collect(), 1)
        self.assertIn("source changed", self.validation()["reason"])

    def test_nonzero_cleanup_rejected(self):
        self.report["cleanup_exit_code"] = 1
        e.write(self.run / "result.json", self.report)
        self.assertEqual(e.collect(), 1)
        self.assertIn("cleanup failed", self.validation()["reason"])

    def test_optimizer_guard_runs_before_any_service(self):
        e.check_optimizer()


if __name__ == "__main__":
    unittest.main()
