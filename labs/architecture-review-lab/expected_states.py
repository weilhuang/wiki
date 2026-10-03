"""Independent literal reference states; never imports or runs the model."""
from copy import deepcopy


def initial():
    return {
        "orders": {
            "red/o1": {"owner": "alice", "status": "CONFIRMED", "version": 1, "epoch": 1},
            "blue/o1": {"owner": "mallory", "status": "CONFIRMED", "version": 1, "epoch": 1}},
        "reserved": {"red/o1": True, "blue/o1": True},
        "available": {"red": 0, "blue": 0},
        "operations": {}, "outbox": {}, "receipts": {}, "fences": {},
        "audit": [], "releaseEffects": [], "acks": [],
    }


def pending_reference():
    state = initial()
    state["orders"]["red/o1"] = {"owner": "alice", "status": "CANCEL_PENDING", "version": 2, "epoch": 1}
    state["operations"] = {"red/alice/c1": {
        "fingerprint": ["o1", "customer-request", "async"], "result": "PENDING"}}
    state["outbox"] = {"red/o1/cancel/2": {"key": "red/o1", "version": 2, "operation": "red/alice/c1"}}
    state["audit"] = [{"actor": "alice", "key": "red/o1", "action": "cancel-accepted"}]
    return state


def local_completed_reference():
    state = initial()
    state["orders"]["red/o1"] = {"owner": "alice", "status": "CANCELLED", "version": 2, "epoch": 1}
    state["reserved"]["red/o1"] = False
    state["available"]["red"] = 1
    state["operations"] = {"red/alice/c1": {
        "fingerprint": ["o1", "customer-request", "local"], "result": "CANCELLED"}}
    state["audit"] = [{"actor": "alice", "key": "red/o1", "action": "cancel-accepted"}]
    state["releaseEffects"] = ["red/o1"]
    return state


def async_completed_reference():
    state = pending_reference()
    state["orders"]["red/o1"] = {"owner": "alice", "status": "CANCELLED", "version": 3, "epoch": 1}
    state["reserved"]["red/o1"] = False
    state["available"]["red"] = 1
    state["operations"]["red/alice/c1"]["result"] = "CANCELLED"
    state["receipts"] = {"red/o1/cancel/2": {"key": "red/o1", "version": 2}}
    state["fences"] = {"red/o1": 7}
    state["releaseEffects"] = ["red/o1"]
    state["acks"] = ["red/o1/cancel/2"]
    return state


def signature(code, expected, actual):
    return {"type": "CheckFailure", "code": code, "expected": expected, "actual": actual}


def outcome(result, state):
    return {"result": result, "state": state}


def all_oracles():
    out = {}
    for name, actor, before_version, code, before_result in [
        ("allow-member", "bob", 1, "denial-has-no-effects", "DENIED"),
        ("skip-current-membership", "alice", 1, "current-membership", "DENIED"),
        ("ignore-version", "alice", 2, "current-version", "STALE_VERSION")]:
        before = initial()
        before["orders"]["red/o1"]["version"] = before_version
        after = deepcopy(before)
        after["orders"]["red/o1"] = {"owner": "alice", "status": "CANCELLED", "version": before_version + 1, "epoch": 1}
        after["reserved"]["red/o1"] = False
        after["available"]["red"] = 1
        after["operations"] = {"red/" + actor + "/c1": {
            "fingerprint": ["o1", "customer-request", "local"], "result": "CANCELLED"}}
        after["audit"] = [{"actor": actor, "key": "red/o1", "action": "cancel-accepted"}]
        after["releaseEffects"] = ["red/o1"]
        out[name] = signature(code, outcome(before_result, before), outcome("CANCELLED", after))
    before = initial()
    after = deepcopy(before)
    after["orders"]["red/o1"] = {"owner": "alice", "status": "CANCELLED", "version": 2, "epoch": 1}
    out["split-local-commit"] = signature("local-atomicity", outcome("STORAGE_ABORT", before), outcome("STORAGE_ABORT", after))
    out["missing-outbox"] = signature("pending-has-responsibility", pending_reference()["outbox"], {})
    out["premature-final"] = signature("pending-not-final",
        {"owner": "alice", "status": "CANCEL_PENDING", "version": 2, "epoch": 1},
        {"owner": "alice", "status": "CANCELLED", "version": 2, "epoch": 1})
    before = pending_reference()
    after = deepcopy(before)
    after["acks"] = ["red/o1/cancel/2"]
    out["ack-first"] = signature("ack-after-commit", outcome("WORKER_ABORT", before), outcome("WORKER_ABORT", after))
    out["repeat-release"] = signature("one-release-effect",
        {"effects": ["red/o1"], "available": {"red": 1, "blue": 0}},
        {"effects": ["red/o1", "red/o1"], "available": {"red": 2, "blue": 0}})
    before = pending_reference()
    before["fences"] = {"red/o1": 8}
    after = deepcopy(before)
    after["reserved"]["red/o1"] = False
    after["available"]["red"] = 1
    after["receipts"] = {"red/o1/cancel/2": {"key": "red/o1", "version": 2}}
    after["releaseEffects"] = ["red/o1"]
    after["acks"] = ["red/o1/cancel/2"]
    out["ignore-fence"] = signature("resource-rejects-old-token", outcome("STALE_TOKEN", before), outcome("RELEASED", after))
    out["forget-tenant"] = signature("independent-resource-token", "RELEASED", "STALE_TOKEN")
    out["unsafe-rollback"] = signature("rollback-requires-compatible-state", False, True)
    out["ignore-surge"] = signature("expanded-surge-budget", {"used": 104, "limit": 100, "fits": False}, {"used": 72, "limit": 100, "fits": True})
    out["exclude-rejections"] = signature("rejections-remain-in-denominator",
        {"total": 10000, "bad": 6, "allowed": "10", "remaining": "4", "ratio": "4997/5000"},
        {"total": 9998, "bad": 4, "allowed": "4999/500", "remaining": "2999/500", "ratio": "4997/4999"})
    for name, error in [("internal-import", "internal-access:reports->orders"),
                        ("foreign-write", "foreign-write:reports->orders"), ("cycle", "module-cycle")]:
        out[name] = signature("declared-boundaries", [], [error])
    before = initial()
    after = deepcopy(before)
    after["orders"]["red/o1"] = {"owner": "alice", "status": "CANCEL_PENDING", "version": 2, "epoch": 1}
    out["async-abort-only-half-commit"] = signature("async-abort-full-state", before, after)
    before = local_completed_reference()
    after = deepcopy(before)
    after["audit"].append({"wrong": "replay-effect"})
    out["revoked-replay-only-side-effect"] = signature("revoked-replay-full-state", before, after)
    state = async_completed_reference()
    out["completed-outbox-rollback"] = signature("completed-outbox-rejects-v1",
        {"allowed": False, "state": state}, {"allowed": True, "state": deepcopy(state)})
    return out
