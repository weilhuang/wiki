#!/usr/bin/env python3
"""CI evidence boundary. Only the owned run's bounded, regular files are uploaded."""
from __future__ import annotations
import ast
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = ROOT / "labs/data-consistency"
TEMP = Path(os.environ.get("RUNNER_TEMP", "/tmp/wiki-data-ci-test")).resolve()
PRIVATE = TEMP / "wiki-data-evidence-private"
UPLOAD = TEMP / "wiki-data-evidence-upload"
PER_FILE = 8 * 1024 * 1024
TOTAL = 32 * 1024 * 1024
ALLOWED = {"result.json", "trace.jsonl", "exception.txt", "python-version.txt", "docker-version.txt",
           "compose-version.txt", "start.log", "containers.log", "containers.txt", "cleanup.log",
           "exit-codes.txt", "image-ids.txt", "image-digests.txt"}
REQUIRED = ALLOWED - {"exception.txt"}
EXPECTED_COUNTS = {"d1": 5, "d2": 6, "d3": 5, "d4": 5, "d5": 2}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def regular_bytes(path):
    require(not path.is_symlink() and stat.S_ISREG(path.lstat().st_mode), "Non-regular evidence file")
    require(path.stat().st_size <= PER_FILE, "Evidence file exceeds 8 MiB")
    return path.read_bytes()


def source_manifest():
    manifest = {}
    for path in sorted(LAB.rglob("*")):
        relative = path.relative_to(LAB)
        if any(part in ("results", "__pycache__") for part in relative.parts):
            continue
        require(not path.is_symlink(), "Harness contains a symbolic link")
        if path.is_file():
            manifest[relative.as_posix()] = hashlib.sha256(regular_bytes(path)).hexdigest()
    require(bool(manifest), "Empty harness source")
    return manifest


def expected_cases():
    tree = ast.parse((LAB / "lab.py").read_text())
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "EXPECTED_CASES" for t in node.targets))
    groups = ast.literal_eval(assignment.value)
    require({key: len(value) for key, value in groups.items()} == EXPECTED_COUNTS, "Case inventory differs from reviewed 23-case contract")
    cases = [name for values in groups.values() for name in values]
    require(len(set(cases)) == 23, "Duplicate case ID")
    return cases


def prepare():
    require(not os.environ.get("PYTHONOPTIMIZE") and not sys.flags.optimize, "Python optimization is forbidden")
    require(not PRIVATE.exists() and not UPLOAD.exists(), "Evidence staging directory already exists")
    PRIVATE.mkdir(parents=True)
    manifest = source_manifest()
    reviewed = json.loads((ROOT / "labs/data-consistency-reviewed.json").read_text())
    require(manifest == reviewed["source_sha256"], "Harness differs from independently reviewed frozen source")
    write(PRIVATE / "source-before.json", manifest)
    write(PRIVATE / "provenance.json", {
        "checkout_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "pr_head_sha": os.environ.get("PR_HEAD_SHA"), "pr_base_sha": os.environ.get("PR_BASE_SHA"),
        "repository": os.environ.get("GITHUB_REPOSITORY"), "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"), "runner_os": os.environ.get("RUNNER_OS"),
        "reviewed_manifest_sha256": hashlib.sha256((ROOT / "labs/data-consistency-reviewed.json").read_bytes()).hexdigest(),
        "ci_validator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "ci_workflow_sha256": hashlib.sha256((ROOT / ".github/workflows/data-lab.yml").read_bytes()).hexdigest()
    })
    expected_cases()


def check_optimizer():
    for script in ("check_static.py", "lab.py"):
        completed = subprocess.run([sys.executable, "-O", str(LAB / script)], cwd=LAB,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        require(completed.returncode != 0 and "Optimized Python is forbidden" in completed.stderr,
                "Optimization guard was removed")


def inspect_report(staged, before, after):
    text = lambda name: staged[name].decode("utf-8")
    require(before == after, "Harness source changed during execution")
    report = json.loads(text("result.json"))
    expected = expected_cases()
    require(report.get("status") == "PASS" and report.get("chapter") == "all", "Real-service run did not pass")
    require(report.get("scope") == "real_mysql_redis_single_node_controlled_delivery_receiver", "Unexpected evidence scope")
    require(report.get("production_or_real_broker_verified") is False, "Evidence overclaims broker/production coverage")
    require(report.get("expected_cases") == expected, "Expected case inventory differs")
    require([case.get("case") for case in report.get("cases", [])] == expected, "Missing, duplicate or unexpected case")
    require(all(case.get("status") == "PASS" for case in report["cases"]), "A case did not pass")
    fields = ["run_exit_code", "cleanup_exit_code", "logs_exit_code", "ps_exit_code"]
    exits = dict(line.split("=", 1) for line in text("exit-codes.txt").splitlines())
    require(all(report.get(key) == 0 and exits.get(key) == "0" for key in fields), "Run, diagnostics or exact-project cleanup failed")
    ledger = dict(line.split("=", 1) for line in (LAB / "infra/versions.env").read_text().splitlines() if line and not line.startswith("#"))
    environment = report.get("environment", {})
    require(environment.get("images") == ledger, "Image ledger differs")
    mysql_patch = ledger["MYSQL_IMAGE"].split(":", 1)[1]
    redis_patch = ledger["REDIS_IMAGE"].split(":", 1)[1].split("-", 1)[0]
    require(environment.get("mysql") == [mysql_patch + "\tREPEATABLE-READ\t1\tInnoDB"], "MySQL runtime does not match contract")
    redis = dict(line.split(":", 1) for line in environment.get("redis_server", "").splitlines() if ":" in line and not line.startswith("#"))
    require(redis.get("redis_version") == redis_patch, "Redis runtime does not match contract")
    require(report.get("source_sha256") == after, "Reported source differs from executed source")
    trace = [json.loads(line) for line in text("trace.jsonl").splitlines()]
    events = [(record.get("kind"), record.get("name")) for record in trace if record.get("kind") in ("case_begin", "case_pass", "case_fail")]
    require(events == [(kind, name) for name in expected for kind in ("case_begin", "case_pass")], "Case trace is missing, truncated or out of order")
    require(any(record.get("kind") == "sql_result" for record in trace) and any(record.get("kind") == "redis" for record in trace), "Raw database/cache evidence missing")
    ids = text("image-ids.txt").splitlines()
    digests = text("image-digests.txt").splitlines()
    require(len(ids) == len(digests) == 2 and all(re.fullmatch(r"sha256:[a-f0-9]{64}", i) for i in ids), "Runtime image identities missing")
    require(all(isinstance(items := json.loads(line), list) and items and all("@sha256:" in item for item in items) for line in digests), "Registry image digests missing")
    return {"status": "PASS", "cases": 23, "scope": report["scope"], "production_or_real_broker_verified": False}


def upload_ready():
    require(not UPLOAD.is_symlink() and UPLOAD.is_dir(), "Unsafe upload directory")
    files = list(UPLOAD.iterdir())
    allowed = ALLOWED | {"validation.json", "source-before.json", "source-after.json", "provenance.json"}
    require(all(path.name in allowed for path in files), "Unexpected staged file")
    require(sum(len(regular_bytes(path)) for path in files) <= TOTAL, "Staged evidence exceeds limit")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("upload_ready=true\n")


def collect():
    # If this path already exists, never authorize the always-upload step.
    try:
        UPLOAD.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Evidence staging directory is unavailable; upload blocked", file=sys.stderr)
        return 1
    staged = {}
    try:
        before = json.loads(regular_bytes(PRIVATE / "source-before.json"))
        after = source_manifest()
        results = LAB / "results"
        for directory in [LAB.parent, LAB, results, PRIVATE]:
            require(not directory.is_symlink() and directory.is_dir(), "Symbolic or missing evidence ancestor")
        require(results.resolve().parent == LAB.resolve(), "Results directory escapes harness")
        runs = list(results.iterdir())
        require(len(runs) == 1 and not runs[0].is_symlink() and runs[0].is_dir() and re.fullmatch(r"[a-f0-9]{32}", runs[0].name), "Expected exactly one owned run directory")
        run = runs[0]
        require(run.resolve().parent == results.resolve(), "Run directory escapes results")
        files = list(run.iterdir())
        require({p.name for p in files}.issubset(ALLOWED), "Unexpected file in evidence directory")
        for path in files:
            require(path.resolve().parent == run.resolve(), "Evidence path escapes owned run")
            staged[path.name] = regular_bytes(path)
        staged["source-before.json"] = regular_bytes(PRIVATE / "source-before.json")
        staged["source-after.json"] = (json.dumps(after, sort_keys=True, indent=2) + "\n").encode()
        staged["provenance.json"] = regular_bytes(PRIVATE / "provenance.json")
        require(sum(map(len, staged.values())) <= TOTAL, "Evidence exceeds 32 MiB")
        sensitive = re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|Authorization:\s*Bearer\s+\S+)", re.I)
        require(not any(sensitive.search(data) for data in staged.values()), "Potential credential detected; raw evidence withheld")
        for name, data in staged.items():
            (UPLOAD / name).write_bytes(data)
        require(REQUIRED.issubset(staged), "Required evidence file missing")
        summary = inspect_report(staged, before, after)
        write(UPLOAD / "validation.json", summary)
    except Exception as error:
        # Do not expose arbitrary exception text, file contents or local paths.
        message = str(error) if isinstance(error, ValueError) else type(error).__name__
        write(UPLOAD / "validation.json", {"status": "FAIL", "reason": message,
              "raw_proof_withheld": len(list(UPLOAD.iterdir())) == 0, "note": "Missing or unsafe evidence cannot be treated as a passing run."})
        print("Evidence validation failed; inspect the bounded validation artifact", file=sys.stderr)
        upload_ready()
        return 1
    upload_ready()
    return 0


def main():
    require(not sys.flags.optimize and not os.environ.get("PYTHONOPTIMIZE"), "Python optimization is forbidden")
    action = sys.argv[1] if len(sys.argv) == 2 else ""
    require(action in ("prepare", "check-optimizer", "collect"), "Unknown CI evidence action")
    return {"prepare": prepare, "check-optimizer": check_optimizer, "collect": collect}[action]() or 0

if __name__ == "__main__":
    raise SystemExit(main())
