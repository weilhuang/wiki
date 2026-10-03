"""Bounded subprocess verification with exact rejection attribution."""
import copy
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from scenarios import SCENARIOS, MUTANTS


def valid_rejection(code, payload, scenario, variant, reason):
    return (code == 1 and payload.get("status") == "rejected"
            and payload.get("error_type") == "Violation" and payload.get("code") == reason
            and payload.get("scenario") == scenario and payload.get("variant") == variant
            and isinstance(payload.get("observed"), dict) and bool(payload["observed"]))


def launch(scenario, variant):
    command = [sys.executable, "-B", "scenario_runner.py", "--scenario", scenario,
               "--variant", variant]
    run = subprocess.run(command, cwd=Path(__file__).parent, text=True,
                         capture_output=True, timeout=10)
    if run.stderr:
        raise RuntimeError("Unexpected stderr: " + run.stderr)
    payload = json.loads(run.stdout)
    return {"command": "python3 -B " + " ".join(command[2:]),
            "exitCode": run.returncode, "result": payload}


def main():
    positives, negatives = [], []
    for scenario in SCENARIOS:
        run = launch(scenario, "correct")
        if run["exitCode"] != 0 or run["result"].get("status") != "pass":
            raise RuntimeError(json.dumps(run))
        positives.append(run)
    for scenario, variant, reason in MUTANTS:
        run = launch(scenario, variant)
        if not valid_rejection(run["exitCode"], run["result"], scenario, variant, reason):
            raise RuntimeError("Wrong rejection: " + json.dumps(run))
        run.update(expectedExitCode=1, expectedReason=reason, expectation="expected-rejection")
        negatives.append(run)
    # The classifier must not turn startup errors, green exits, wrong scenario,
    # wrong exception class or an incidental substring into a target failure.
    sample = negatives[0]["result"]
    probes = []
    for label, code, change in [
        ("zero-exit", 0, {}), ("startup-error", 2, {"status": "error"}),
        ("wrong-exception", 1, {"error_type": "ValueError"}),
        ("wrong-reason", 1, {"code": "OTHER_DUPLICATE_MESSAGE_EFFECT"}),
        ("wrong-scenario", 1, {"scenario": "different"}),
        ("missing-observation", 1, {"observed": {}}),
    ]:
        candidate = copy.deepcopy(sample)
        candidate.update(change)
        if valid_rejection(code, candidate, *MUTANTS[0]):
            raise RuntimeError("Verifier accepted " + label)
        probes.append({"probe": label, "accepted_as_target_failure": False})
    root = Path(__file__).parent
    files = ["protocol_model.py", "scenarios.py", "scenario_runner.py", "verify.py",
             "walk_delivery.py", "walk_fencing.py"]
    report = {"status": "pass", "runtime": platform.python_version(),
              "platform": platform.system(), "model": "finite sequential logical snapshots",
              "sourceFiles": [{"path": file, "sha256": hashlib.sha256((root / file).read_bytes()).hexdigest()}
                              for file in files],
              "positive": positives, "negative": negatives, "verifier_probes": probes,
              "cleanup": {"subprocesses_joined": len(positives) + len(negatives),
                          "servers_started": 0, "threads_started": 0, "temporary_resources": 0},
              "limitations": ["No real broker, DB, Redis, etcd, disk crash, rebalance or partition",
                              "Logical commit snapshots assume atomicity and retained bytes",
                              "Trusted identities and issuance proofs are model inputs"]}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
