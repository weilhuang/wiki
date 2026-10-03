"""Replay the original review patches against disposable source copies."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from expected_states import all_oracles
from source_mutations import apply_patch, PATCHES


def sha(data):
    return hashlib.sha256(data).hexdigest()


def run(args, cwd):
    result = subprocess.run([sys.executable, "-B", *args], cwd=cwd,
                            capture_output=True, text=True, timeout=10)
    # Successful/target-failing programs emit JSON only; an unrelated error is red.
    if result.stderr:
        raise AssertionError("unexpected stderr, not a semantic target rejection")
    return result.returncode, json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    source = (root / "review_model.py").read_bytes()
    oracles = all_oracles()
    reports = []
    for name in sorted(PATCHES):
        probe = "review_regressions/" + name + ".py"
        patch_path = root / "review_regressions" / (name + ".patch")
        patch = patch_path.read_bytes()
        code, result = run([probe, "."], root)
        assert code == 0 and result == {"status": "PASS"}, "baseline probe must pass"
        baseline = {"exitCode": code, "output": result}
        with tempfile.TemporaryDirectory(prefix="architecture-review-") as temporary:
            copy = Path(temporary) / "lab"
            shutil.copytree(root, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            modified = apply_patch(source.decode(), patch.decode()).encode()
            assert modified != source
            (copy / "review_model.py").write_bytes(modified)
            output_path = "new-suite-output.json"
            assert not (copy / output_path).exists()
            suite_code, suite_result = run(["verify.py", "--output", output_path], copy)
            assert suite_code == 1, "patched public suite must fail"
            assert suite_result == {"status": "FAIL", "failure": oracles[name]}, "wrong public failure"
            assert not (copy / output_path).exists(), "failure wrote a success report"
            probe_code, probe_result = run([probe, "."], copy)
            expected = oracles[name]["expected"]
            actual = oracles[name]["actual"]
            if name == "completed-outbox-rollback":
                expected, actual = expected["allowed"], actual["allowed"]
            assert probe_code == 1
            assert probe_result == {"status": "FAIL", "code": oracles[name]["code"],
                                    "expected": expected, "actual": actual}, "wrong independent failure"
        reports.append({"name": name, "patchSha256": sha(patch),
            "probeSha256": sha((root / probe).read_bytes()), "modifiedModelSha256": sha(modified),
            "baselineProbe": baseline, "patchedPublicSuite": {"exitCode": suite_code, "output": suite_result},
            "patchedIndependentProbe": {"exitCode": probe_code, "output": probe_result},
            "temporaryCopyRemoved": True})
    report = {"revision": "A-r3-reconstructed", "status": "pass", "sourceModelSha256": sha(source),
              "scope": "exact original patches; correct probes pass; patched default public suite and original probes fail at exact semantic signatures",
              "results": reports}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("3 original patches: baseline probes exit0; patched public suites and independent probes exit1 at exact targets")


if __name__ == "__main__":
    main()
