"""Exact semantic oracles; startup errors and wrong failures cannot turn green."""
import argparse
import json
from pathlib import Path
from boundaries import changed, fixture, inspect
from review_model import ReviewModel, connection_budget, slo_report
from expected_states import (all_oracles, initial, local_completed_reference,
                             async_completed_reference)
from source_mutations import PATCHES, mutated_model


class CheckFailure(AssertionError):
    def __init__(self, code, expected, actual):
        self.code, self.expected, self.actual = code, expected, actual
        super().__init__(code)


def equal(code, expected, actual):
    if expected != actual:
        raise CheckFailure(code, expected, actual)


def outcome(model, result):
    return {"result": result, "state": model.snapshot()}


def pending(variant="good"):
    model = ReviewModel(variant)
    equal("fixture-accepted", "PENDING", model.cancel("alice", "red", "o1", "c1", 1, mode="async"))
    return model


def authorization(variant="good"):
    rows = [(None, "red", "o1", 10, "DENIED"), ("bob", "red", "o1", 10, "DENIED"),
            ("mallory", "red", "o1", 10, "DENIED"), ("alice", "blue", "o1", 10, "DENIED"),
            ("alice", "red", "absent", 10, "DENIED"), ("support", "red", "o1", 20, "DENIED"),
            ("alice", "red", "o1", 10, "CANCELLED"), ("support", "red", "o1", 19, "CANCELLED"),
            ("mallory", "blue", "o1", 10, "CANCELLED")]
    for actor, tenant, order_id, now, expected in rows:
        model = ReviewModel(variant)
        before = model.snapshot()
        result = model.cancel(actor, tenant, order_id, "c1", 1, now=now)
        if expected == "DENIED":
            equal("denial-has-no-effects", {"result": expected, "state": before}, outcome(model, result))
        else:
            equal("authorized-result", expected, result)
            equal("authorized-local-effect", [tenant + "/" + order_id], model.state["releaseEffects"])
            equal("authorized-stock-return", 1, model.state["available"][tenant])
            other = "blue" if tenant == "red" else "red"
            equal("other-tenant-unchanged", before["orders"][other + "/o1"], model.state["orders"][other + "/o1"])
            equal("other-stock-unchanged", 0, model.state["available"][other])
    return {"rows": len(rows), "denialPreservesFullState": True}


def revoked(variant="good"):
    model = ReviewModel(variant)
    model.members.remove(("alice", "red"))
    before = model.snapshot()
    result = model.cancel("alice", "red", "o1", "c1", 1)
    equal("current-membership", {"result": "DENIED", "state": before}, outcome(model, result))
    return {"result": result, "stateUnchanged": True}


def stale(variant="good"):
    model = ReviewModel(variant)
    model.state["orders"]["red/o1"]["version"] = 2
    before = model.snapshot()
    result = model.cancel("alice", "red", "o1", "c1", 1)
    equal("current-version", {"result": "STALE_VERSION", "state": before}, outcome(model, result))
    return {"result": result, "stateUnchanged": True}


def atomic(variant="good"):
    model = ReviewModel(variant)
    before = model.snapshot()
    result = model.cancel("alice", "red", "o1", "c1", 1, fault="after-order")
    equal("local-atomicity", {"result": "STORAGE_ABORT", "state": before}, outcome(model, result))
    return {"result": result, "stateUnchanged": True}


def reviewed_model(variant):
    return mutated_model(variant)() if variant in PATCHES else ReviewModel(variant)


def async_atomic(variant="good"):
    model = reviewed_model(variant)
    equal("async-abort-initial", initial(), model.snapshot())
    result = model.cancel("alice", "red", "o1", "c1", 1, mode="async", fault="after-order")
    equal("async-abort-result", "STORAGE_ABORT", result)
    equal("async-abort-full-state", initial(), model.snapshot())
    return {"result": result, "state": model.snapshot()}


def revoked_replay(variant="good"):
    model = reviewed_model(variant)
    equal("revoked-replay-setup", "CANCELLED", model.cancel("alice", "red", "o1", "c1", 1))
    equal("revoked-replay-initial", local_completed_reference(), model.snapshot())
    model.members.remove(("alice", "red"))
    result = model.cancel("alice", "red", "o1", "c1", 1)
    equal("revoked-replay-result", "DENIED", result)
    equal("revoked-replay-full-state", local_completed_reference(), model.snapshot())
    return {"result": result, "state": model.snapshot()}


def completed_rollback(variant="good"):
    model = reviewed_model(variant)
    event = "red/o1/cancel/2"
    equal("completed-rollback-pending", "PENDING", model.cancel("alice", "red", "o1", "c1", 1, mode="async"))
    equal("completed-rollback-release", "RELEASED", model.release(event, 7))
    equal("completed-rollback-confirm", "CANCELLED", model.confirm(event))
    equal("completed-rollback-fixture", async_completed_reference(), model.snapshot())
    allowed = model.rollback_allowed()
    equal("completed-outbox-rejects-v1", {"allowed": False, "state": async_completed_reference()},
          {"allowed": allowed, "state": model.snapshot()})
    return {"allowed": allowed, "state": model.snapshot()}


def handoff(variant="good"):
    model = pending(variant)
    equal("pending-has-responsibility", {"red/o1/cancel/2": {
        "key": "red/o1", "version": 2, "operation": "red/alice/c1"}}, model.state["outbox"])
    equal("pending-not-final", {"owner": "alice", "status": "CANCEL_PENDING", "version": 2, "epoch": 1}, model.state["orders"]["red/o1"])
    equal("pending-reserved", True, model.state["reserved"]["red/o1"])
    equal("pending-not-returned", 0, model.state["available"]["red"])
    return {"status": "CANCEL_PENDING", "outbox": ["red/o1/cancel/2"], "reserved": True}


def failed_worker(variant="good"):
    model = pending(variant)
    before = model.snapshot()
    result = model.release("red/o1/cancel/2", 7, fault="before-release")
    equal("ack-after-commit", {"result": "WORKER_ABORT", "state": before}, outcome(model, result))
    return {"result": result, "acks": [], "effects": []}


def redelivery(variant="good"):
    model = pending(variant)
    event = "red/o1/cancel/2"
    equal("lost-ack-identity", "ACK_LOST", model.release(event, 7, fault="after-release"))
    equal("receipt-survives", {"key": "red/o1", "version": 2}, model.state["receipts"][event])
    equal("lost-ack-not-sent", [], model.state["acks"])
    equal("redelivery-result", "RELEASED", model.release(event, 8))
    equal("one-release-effect", {"effects": ["red/o1"], "available": {"red": 1, "blue": 0}},
          {"effects": model.state["releaseEffects"], "available": model.state["available"]})
    equal("duplicate-is-acked", [event], model.state["acks"])
    equal("confirm-result", "CANCELLED", model.confirm(event))
    equal("final-order", {"owner": "alice", "status": "CANCELLED", "version": 3, "epoch": 1}, model.state["orders"]["red/o1"])
    before = model.snapshot()
    equal("confirm-replay", "CANCELLED", model.confirm(event))
    equal("confirm-replay-no-write", before, model.snapshot())
    return {"effects": ["red/o1"], "available": 1, "status": "CANCELLED", "version": 3}


def fencing(variant="good"):
    model = pending(variant)
    model.state["fences"]["red/o1"] = 8  # Input premise: receiver already saw 8.
    before = model.snapshot()
    result = model.release("red/o1/cancel/2", 7)
    equal("resource-rejects-old-token", {"result": "STALE_TOKEN", "state": before}, outcome(model, result))
    return {"result": result, "stateUnchanged": True}


def tenant_fence(variant="good"):
    model = pending(variant)
    equal("blue-accepted", "PENDING", model.cancel("mallory", "blue", "o1", "c1", 1, mode="async"))
    equal("red-high-token", "RELEASED", model.release("red/o1/cancel/2", 9))
    equal("independent-resource-token", "RELEASED", model.release("blue/o1/cancel/2", 1))
    equal("tenant-effects", ["red/o1", "blue/o1"], model.state["releaseEffects"])
    equal("tenant-stock", {"red": 1, "blue": 1}, model.state["available"])
    return {"available": {"red": 1, "blue": 1}, "fences": {"red/o1": 9, "blue/o1": 1}}


def rollback(variant="good"):
    equal("prewrite-rollback", True, ReviewModel(variant).rollback_allowed())
    equal("rollback-requires-compatible-state", False, pending(variant).rollback_allowed())
    return {"beforeNewWrites": True, "afterNewWrites": False}


def budget(variant="good"):
    equal("expanded-surge-budget", {"used": 104, "limit": 100, "fits": False}, connection_budget(surge=2, variant=variant))
    equal("normal-surge-budget", {"used": 88, "limit": 100, "fits": True}, connection_budget(variant=variant))
    return {"surge1": 88, "surge2": 104, "limit": 100}


def denominator(variant="good"):
    result = slo_report(variant=variant)
    equal("rejections-remain-in-denominator", {"total": 10000, "bad": 6, "allowed": "10", "remaining": "4", "ratio": "4997/5000"}, result)
    return result


def operation_identity(variant="good"):
    model = ReviewModel(variant)
    equal("first-cancel", "CANCELLED", model.cancel("alice", "red", "o1", "c1", 1))
    before = model.snapshot()
    equal("same-key-result", "CANCELLED", model.cancel("alice", "red", "o1", "c1", 1))
    equal("same-key-no-effects", before, model.snapshot())
    equal("key-payload-conflict", "KEY_CONFLICT", model.cancel("alice", "red", "o1", "c1", 1, reason="other"))
    equal("key-conflict-no-effects", before, model.snapshot())
    model.members.remove(("alice", "red"))
    equal("replay-rechecks-authority", "DENIED", model.cancel("alice", "red", "o1", "c1", 1))
    equal("revoked-replay-full-state", before, model.snapshot())
    return {"replay": "CANCELLED", "conflict": "KEY_CONFLICT", "revokedReplay": "DENIED"}


def fact_identity(variant="good"):
    model = pending(variant)
    event = "red/o1/cancel/2"
    before = model.snapshot()
    equal("missing-fact", "NO_RELEASE_FACT", model.confirm(event))
    equal("missing-fact-no-write", before, model.snapshot())
    model.state["receipts"][event] = {"key": "blue/o1", "version": 2}
    before = model.snapshot()
    equal("wrong-scope-fact", "NO_RELEASE_FACT", model.confirm(event))
    equal("wrong-scope-no-write", before, model.snapshot())
    return {"missing": "NO_RELEASE_FACT", "wrongTenant": "NO_RELEASE_FACT"}


def grant_scope(variant="good"):
    model = ReviewModel(variant)
    equal("support-not-reader", False, model.allowed("support", "red", "o1", 10, "read"))
    equal("unknown-action", False, model.allowed("alice", "red", "o1", 10, "delete"))
    model.state["orders"]["red/o1"]["epoch"] = 2
    before = model.snapshot()
    result = model.cancel("support", "red", "o1", "c1", 1)
    equal("old-grant", {"result": "DENIED", "state": before}, outcome(model, result))
    return {"read": False, "delete": False, "oldEpoch": "DENIED"}


def boundaries(variant="good"):
    result = inspect(changed(fixture(), variant))
    equal("declared-boundaries", [], result)
    return {"errors": result, "scope": "declarations only"}


CASES = {f.__name__: f for f in [authorization, revoked, stale, atomic, handoff,
    failed_worker, redelivery, fencing, tenant_fence, rollback, budget, denominator,
    operation_identity, fact_identity, grant_scope, boundaries,
    async_atomic, revoked_replay, completed_rollback]}
MUTANTS = {
    "allow-member": "authorization", "skip-current-membership": "revoked", "ignore-version": "stale",
    "split-local-commit": "atomic", "missing-outbox": "handoff", "premature-final": "handoff",
    "ack-first": "failed_worker", "repeat-release": "redelivery", "ignore-fence": "fencing",
    "forget-tenant": "tenant_fence", "unsafe-rollback": "rollback", "ignore-surge": "budget",
    "exclude-rejections": "denominator", "internal-import": "boundaries", "foreign-write": "boundaries", "cycle": "boundaries",
    "async-abort-only-half-commit": "async_atomic", "revoked-replay-only-side-effect": "revoked_replay",
    "completed-outbox-rollback": "completed_rollback"}
ORACLES = all_oracles()


def check_rejection(name, override=None):
    try:
        (override or CASES[MUTANTS[name]])(name)
    except CheckFailure as error:
        failure = {"type": "CheckFailure", "code": error.code, "expected": error.expected, "actual": error.actual}
        if error.expected == error.actual or failure != ORACLES[name]:
            raise RuntimeError("wrong failure identity or expected/actual state signature") from error
        return {"mutant": name, "case": MUTANTS[name], "status": "target-rejected", "failure": failure}
    except Exception as error:
        raise RuntimeError("unrelated failure: " + type(error).__name__) from error
    raise RuntimeError("mutant escaped target oracle")


def regression_probes():
    probes = {
        "startup-error": lambda _: (_ for _ in ()).throw(ImportError("synthetic missing module")),
        "syntax-error": lambda _: (_ for _ in ()).throw(SyntaxError("synthetic invalid syntax")),
        "wrong-assertion": lambda _: equal("unrelated-assertion", 1, 2),
        "silent-success": lambda _: None,
        "empty-difference": lambda _: (_ for _ in ()).throw(CheckFailure("local-atomicity", 1, 1)),
        "right-code-wrong-state": lambda _: equal("local-atomicity", {"state": "unrelated"}, {}),
    }
    results = []
    for name, probe in probes.items():
        try:
            check_rejection("split-local-commit", override=probe)
        except RuntimeError as error:
            results.append({"probe": name, "status": "refused", "reason": str(error)})
        else:
            raise AssertionError("harness accepted " + name)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutant", choices=sorted(MUTANTS))
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.mutant:
        print(json.dumps(check_rejection(args.mutant), sort_keys=True))
        return 2
    report = {"revision": "A-r3-reconstructed", "status": "pass", "execution": "new finite sequential execution; synthetic inputs",
        "correct": [{"case": name, "status": "pass", "observation": f()} for name, f in CASES.items()],
        "mutants": [check_rejection(name) for name in MUTANTS], "verifierRegressions": regression_probes(),
        "notRun": ["database", "broker", "network", "threads", "identity provider", "framework", "Kubernetes", "production SLO"]}
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f'{len(report["correct"])} model cases; {len(report["mutants"])} target rejections; {len(report["verifierRegressions"])} unrelated outcomes refused')
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckFailure as error:
        print(json.dumps({"status": "FAIL", "failure": {"type": "CheckFailure", "code": error.code,
            "expected": error.expected, "actual": error.actual}}, sort_keys=True))
        raise SystemExit(1)
