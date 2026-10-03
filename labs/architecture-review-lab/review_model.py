"""Reconstructed original teaching model; sequential, synthetic, no services."""
from copy import deepcopy
from fractions import Fraction

VARIANTS = {"good", "allow-member", "skip-current-membership", "ignore-version",
            "split-local-commit", "missing-outbox", "premature-final", "ack-first",
            "repeat-release", "ignore-fence", "forget-tenant", "unsafe-rollback",
            "ignore-surge", "exclude-rejections"}


class ReviewModel:
    def __init__(self, variant="good"):
        if variant not in VARIANTS:
            raise ValueError("unknown model variant")
        self.variant = variant
        self.members = {("alice", "red"), ("bob", "red"),
                        ("support", "red"), ("mallory", "blue")}
        self.grants = {("support", "red", "o1"): {"expires": 20, "epoch": 1}}
        self.state = {
            "orders": {
                "red/o1": {"owner": "alice", "status": "CONFIRMED", "version": 1, "epoch": 1},
                "blue/o1": {"owner": "mallory", "status": "CONFIRMED", "version": 1, "epoch": 1},
            },
            "reserved": {"red/o1": True, "blue/o1": True},
            "available": {"red": 0, "blue": 0},
            "operations": {}, "outbox": {}, "receipts": {}, "fences": {},
            "audit": [], "releaseEffects": [], "acks": [],
        }

    def snapshot(self):
        return deepcopy(self.state)

    def allowed(self, actor, tenant, order_id, now, action="cancel"):
        order = self.state["orders"].get(tenant + "/" + order_id)
        if not actor or not order or action not in {"read", "cancel"}:
            return False
        if self.variant != "skip-current-membership" and (actor, tenant) not in self.members:
            return False
        if self.variant == "allow-member":
            return True
        if actor == order["owner"]:
            return True
        grant = self.grants.get((actor, tenant, order_id))
        return bool(action == "cancel" and grant and now < grant["expires"]
                    and grant["epoch"] == order["epoch"])

    def cancel(self, actor, tenant, order_id, operation_id, expected_version,
               now=10, mode="local", reason="customer-request", fault=None):
        if mode not in {"local", "async"}:
            raise ValueError("unknown cancellation mode")
        if not self.allowed(actor, tenant, order_id, now):
            return "DENIED"
        key = tenant + "/" + order_id
        operation = tenant + "/" + actor + "/" + operation_id
        fingerprint = [order_id, reason, mode]
        prior = self.state["operations"].get(operation)
        if prior:
            return prior["result"] if prior["fingerprint"] == fingerprint else "KEY_CONFLICT"
        order = self.state["orders"][key]
        if self.variant != "ignore-version" and order["version"] != expected_version:
            return "STALE_VERSION"
        if order["status"] != "CONFIRMED":
            return "STATE_CONFLICT"
        candidate = deepcopy(self.state)
        target = candidate["orders"][key]
        target["version"] += 1
        target["status"] = "CANCELLED" if mode == "local" else "CANCEL_PENDING"
        if mode == "async" and self.variant == "premature-final":
            target["status"] = "CANCELLED"
        if self.variant == "split-local-commit" and mode == "local":
            self.state["orders"][key] = deepcopy(target)
        if fault == "after-order":
            return "STORAGE_ABORT"
        event_id = key + "/cancel/" + str(target["version"])
        if mode == "local":
            candidate["reserved"][key] = False
            candidate["available"][tenant] += 1
            candidate["releaseEffects"].append(key)
            result = "CANCELLED"
        else:
            if self.variant != "missing-outbox":
                candidate["outbox"][event_id] = {
                    "key": key, "version": target["version"], "operation": operation}
            result = "PENDING"
        candidate["operations"][operation] = {"fingerprint": fingerprint, "result": result}
        candidate["audit"].append({"actor": actor, "key": key, "action": "cancel-accepted"})
        self.state = candidate  # Assumed indivisible model commit, not a database proof.
        return result

    def release(self, event_id, token, fault=None):
        event = self.state["outbox"].get(event_id)
        if not event:
            return "UNKNOWN_EVENT"
        key = event["key"]
        resource = key if self.variant != "forget-tenant" else key.split("/")[1]
        previous = self.state["fences"].get(resource, -1)
        if token < previous and self.variant != "ignore-fence":
            return "STALE_TOKEN"
        if event_id in self.state["receipts"] and self.variant != "repeat-release":
            self.state["fences"][resource] = max(previous, token)
            if fault == "after-release":
                return "ACK_LOST"
            self.state["acks"].append(event_id)
            return "RELEASED"
        if self.variant == "ack-first":
            self.state["acks"].append(event_id)
        if fault == "before-release":
            return "WORKER_ABORT"
        candidate = deepcopy(self.state)
        candidate["fences"][resource] = max(previous, token)
        candidate["reserved"][key] = False
        candidate["available"][key.split("/")[0]] += 1
        candidate["releaseEffects"].append(key)
        candidate["receipts"][event_id] = {"key": key, "version": event["version"]}
        self.state = candidate  # Release and receipt share the model commit.
        if fault == "after-release":
            return "ACK_LOST"
        self.state["acks"].append(event_id)
        return "RELEASED"

    def confirm(self, event_id):
        event = self.state["outbox"].get(event_id)
        receipt = self.state["receipts"].get(event_id)
        if not event or receipt != {"key": event["key"], "version": event["version"]}:
            return "NO_RELEASE_FACT"
        order = self.state["orders"][event["key"]]
        if order["status"] == "CANCELLED":
            return "CANCELLED"
        if order["status"] != "CANCEL_PENDING" or order["version"] != event["version"]:
            return "STALE_FACT"
        order["status"], order["version"] = "CANCELLED", order["version"] + 1
        self.state["operations"][event["operation"]]["result"] = "CANCELLED"
        return "CANCELLED"

    def rollback_allowed(self):
        if self.variant == "unsafe-rollback":
            return True
        # v1 cannot represent PENDING or take over the new outbox responsibility.
        return not self.state["outbox"] and all(
            order["status"] != "CANCEL_PENDING" for order in self.state["orders"].values())


def connection_budget(replicas=4, surge=1, pool=16, workers=2, worker_pool=4,
                      total=120, reserve=20, variant="good"):
    instances = replicas if variant == "ignore-surge" else replicas + surge
    used = instances * pool + workers * worker_pool
    return {"used": used, "limit": total - reserve, "fits": used <= total - reserve}


def slo_report(success=9994, errors=4, rejected=2, variant="good"):
    total = success + errors + (0 if variant == "exclude-rejections" else rejected)
    allowed = Fraction(total, 1000)
    bad = total - success
    return {"total": total, "bad": bad, "allowed": str(allowed),
            "remaining": str(allowed - bad), "ratio": str(Fraction(success, total))}
