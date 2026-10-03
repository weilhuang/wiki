"""Original, finite sequential protocol model. No broker, database or network.

Store.committed is a logical durability boundary: restart retains these JSON
bytes. A transaction replaces the whole snapshot in one model step. This is an
assumption, not an implementation of distributed atomicity or disk durability.
"""
import copy
import json
from dataclasses import dataclass


class Store:
    def __init__(self, state):
        self.committed = json.dumps(state, sort_keys=True, separators=(",", ":"))

    def read(self):
        return json.loads(self.committed)

    def transaction(self, change):
        candidate = self.read()
        result = change(candidate)
        self.committed = json.dumps(candidate, sort_keys=True, separators=(",", ":"))
        return result

    def restart(self):
        return Store(self.read())


def event(event_id="E1", key="shop-a/order-7", delta=5, sequence=None, poison=False):
    return {"event_id": event_id, "key": key, "delta": delta,
            "sequence": sequence, "poison": poison}


class Broker:
    """Abstract retained queue; it intentionally has no producer deduplication.

    Explicit take(serial) controls an interleaving; it does not model a real
    broker scheduler. Consumer acknowledgements are scoped to this channel.
    """
    def __init__(self, store=None, channel="ch-1"):
        self.store = store or Store({"records": []})
        self.channel = channel
        self.tags = {}
        self.next_tag = 1

    def publish(self, message, lose_confirm=False):
        def append(state):
            serial = len(state["records"]) + 1
            state["records"].append({"serial": serial, "message": copy.deepcopy(message),
                                     "state": "ready", "attempts": 0})
            return serial
        serial = self.store.transaction(append)
        return serial, "unknown" if lose_confirm else "confirmed"

    def take(self, serial):
        def change(state):
            record = state["records"][serial - 1]
            if record["state"] != "ready":
                raise ValueError("NOT_READY")
            record["state"] = "unacked"
            record["attempts"] += 1
            return copy.deepcopy(record["message"])
        message = self.store.transaction(change)
        tag = self.next_tag
        self.next_tag += 1
        self.tags[tag] = serial
        return (self.channel, tag), message

    def settle(self, delivery, requeue=False):
        channel, tag = delivery
        if channel != self.channel or tag not in self.tags:
            raise ValueError("UNKNOWN_DELIVERY_TAG")
        serial = self.tags.pop(tag)
        def change(state):
            state["records"][serial - 1]["state"] = "ready" if requeue else "done"
        self.store.transaction(change)

    def close_channel(self):
        def change(state):
            for serial in self.tags.values():
                state["records"][serial - 1]["state"] = "ready"
        self.store.transaction(change)
        self.tags.clear()


class Consumer:
    """One trusted consumer identity, one atomic projection/inbox boundary."""
    def __init__(self, store=None, name="orders-view-v1"):
        self.store = store or Store({"inbox": {}, "totals": {}, "versions": {}, "effects": []})
        self.name = name
        self.calls = 0

    def apply(self, message, variant="correct"):
        self.calls += 1
        key = message["key"]
        identity = self.name + ":" + message["event_id"]
        fingerprint = copy.deepcopy(message)
        def change(state):
            if identity in state["inbox"] and variant != "no-dedup":
                saved = state["inbox"][identity]
                return "duplicate" if saved == fingerprint else "conflict"
            if message["poison"]:
                return "poison"
            sequence = message["sequence"]
            if sequence is not None and variant != "ignore-gap":
                if sequence != state["versions"].get(key, 0) + 1:
                    return "gap"
            state["totals"][key] = state["totals"].get(key, 0) + message["delta"]
            if sequence is not None:
                state["versions"][key] = sequence
            state["effects"].append({"event_id": message["event_id"], "key": key,
                                      "delta": message["delta"], "sequence": sequence})
            if variant != "effect-before-receipt":
                state["inbox"][identity] = fingerprint
            return "applied"
        return self.store.transaction(change)


class Parking:
    def __init__(self, store=None):
        self.store = store or Store({"records": {}})

    def park(self, message, attempts):
        def change(state):
            identity = message["event_id"]
            saved = state["records"].get(identity)
            if saved:
                if saved["message"] != message:
                    raise ValueError("PARKING_CONFLICT")
                return "already-parked"
            state["records"][identity] = {"message": copy.deepcopy(message),
                                            "reason": "poison", "attempts": attempts}
            return "parked"
        return self.store.transaction(change)


@dataclass(frozen=True)
class Grant:
    scope: str
    epoch: int
    token: int
    owner: str


class Authority:
    """Trusted model issuer, with a logical clock and retained issuance history.

    Authentication and unforgeable grant transport are assumed. Registry
    membership validates scope/owner/issuance, not current lease validity.
    Expired grants remain recognizable so the resource's fence is exercised.
    """
    def __init__(self, epoch=1):
        self.epoch = epoch
        self.clock = 0
        self.counter = 0
        self.current = {}
        self.issued = set()

    def acquire(self, scope, owner, ttl=5):
        if scope in self.current and self.current[scope][1] > self.clock:
            raise ValueError("LEASE_BUSY")
        self.counter += 1
        grant = Grant(scope, self.epoch, self.counter, owner)
        self.current[scope] = (grant, self.clock + ttl)
        self.issued.add(grant)
        return grant

    def advance(self, ticks):
        self.clock += ticks

    def valid_now(self, grant):
        return (self.current.get(grant.scope, (None, 0))[0] == grant
                and self.current[grant.scope][1] > self.clock)


class Resource:
    """Receiver-side fencing + operation deduplication in one model transaction.

    The resource key includes tenant and stable resource generation. The model
    uses a trusted issuer registry, not signatures. Every write path must use
    this method. JSON snapshots model retained watermarks and saved responses.
    """
    def __init__(self, authority, store=None):
        self.authority = authority
        self.store = store or Store({"epoch": authority.epoch, "watermarks": {},
                                    "values": {}, "operations": {}, "effects": []})

    def write(self, principal, grant, key, operation, delta, variant="correct"):
        def change(state):
            if variant != "trust-token":
                if grant not in self.authority.issued or principal != grant.owner or key != grant.scope:
                    return {"status": "unauthorized"}
            if grant.epoch != state["epoch"]:
                return {"status": "wrong-epoch"}
            watermark = (max(state["watermarks"].values(), default=0)
                         if variant == "global-watermark"
                         else state["watermarks"].get(key, 0))
            stale = grant.token < watermark
            if variant == "reject-equal":
                stale = grant.token <= watermark
            if stale and variant not in ("no-fence", "lie-stale"):
                return {"status": "stale"}
            lied_status = "stale" if stale and variant == "lie-stale" else None
            identity = key + ":" + operation
            fingerprint = {"key": key, "delta": delta}
            saved = state["operations"].get(identity)
            if saved and variant != "no-operation-dedup":
                if saved["fingerprint"] != fingerprint:
                    if variant == "lie-conflict":
                        lied_status = "conflict"
                    else:
                        return {"status": "conflict"}
                else:
                    # A valid newer holder replaying an operation also advances the fence.
                    state["watermarks"][key] = max(watermark, grant.token)
                    return {"status": "replayed", "value": saved["value"]}
            state["watermarks"][key] = max(watermark, grant.token)
            value = state["values"].get(key, 0) + delta
            state["values"][key] = value
            state["effects"].append({"key": key, "operation": operation,
                                      "token": grant.token, "delta": delta})
            if variant != "effect-before-operation":
                state["operations"][identity] = {"fingerprint": fingerprint, "value": value}
            return {"status": lied_status} if lied_status else {"status": "applied", "value": value}
        return self.store.transaction(change)

    def activate_epoch(self, epoch):
        """Admin recovery step after stopping all old writers; no online reset API."""
        def change(state):
            if epoch <= state["epoch"]:
                raise ValueError("EPOCH_MUST_INCREASE")
            state["epoch"] = epoch
            state["watermarks"] = {}
        self.store.transaction(change)
