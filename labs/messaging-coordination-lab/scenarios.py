"""Named schedules with precise state and side-effect assertions."""
from dataclasses import replace
from protocol_model import Authority, Broker, Consumer, Parking, Resource, Store, event


class Violation(Exception):
    def __init__(self, code, observed):
        super().__init__(code)
        self.code, self.observed = code, observed


def require(condition, code, observed):
    if not condition:
        raise Violation(code, observed)


def message_result(broker, consumer):
    return {"broker": broker.store.read(), "consumer": consumer.store.read(),
            "handler_calls": consumer.calls, "unsettled_tags": len(broker.tags)}


def lost_confirm(variant):
    b, c = Broker(), Consumer()
    first, answer1 = b.publish(event(), lose_confirm=True)
    checkpoint = b.store.read()
    second, answer2 = b.publish(event())
    answers = []
    for serial in (first, second):
        tag, msg = b.take(serial)
        answers.append(c.apply(msg, variant))
        b.settle(tag)
    out = message_result(b, c)
    out.update(publisher_answers=[answer1, answer2], after_lost_confirm=checkpoint,
               consumer_answers=answers)
    require(checkpoint["records"][0]["state"] == "ready" and answer1 == "unknown",
            "CONFIRM_OBSERVATION", out)
    require(c.store.read()["totals"] == {"shop-a/order-7": 5}
            and len(c.store.read()["effects"]) == 1,
            "DUPLICATE_MESSAGE_EFFECT", out)
    require(answers == ["applied", "duplicate"] and c.calls == 2
            and len(b.store.read()["records"]) == 2 and not b.tags
            and all(r["state"] == "done" for r in b.store.read()["records"]),
            "MESSAGE_FINAL_STATE", out)
    return out


def commit_before_ack(variant):
    b, c = Broker(), Consumer()
    serial, _ = b.publish(event())
    tag, msg = b.take(serial)
    if variant == "ack-before-commit":
        b.settle(tag)  # Incorrect: lose the only delivery before business commit.
    else:
        c.apply(msg, variant)
    before = message_result(b, c)
    b.close_channel()  # Deterministic channel failure; no actual TCP or crash.
    c = Consumer(c.store.restart())
    b = Broker(b.store.restart(), channel="ch-2")
    answers = []
    for record in b.store.read()["records"]:
        if record["state"] == "ready":
            delivery, redelivery = b.take(record["serial"])
            answers.append(c.apply(redelivery))
            b.settle(delivery)
    out = {"before_failure": before, "after_restart": message_result(b, c),
           "redelivery_answers": answers}
    state = c.store.read()
    require(state["totals"] == {"shop-a/order-7": 5},
            "BUSINESS_COMMIT_BOUNDARY", out)
    require(len(state["effects"]) == 1 and len(state["inbox"]) == 1,
            "INBOX_EFFECT_ATOMICITY", out)
    require(answers == ["duplicate"] and not b.tags
            and b.store.read()["records"][0]["attempts"] == 2,
            "REDELIVERY_FINAL_STATE", out)
    return out


def poison_and_order(variant):
    b, c, parking = Broker(), Consumer(), Parking()
    events = [event("A1", "A", sequence=1, poison=True),
              event("A2", "A", sequence=2), event("B1", "B", sequence=1)]
    for msg in events:
        b.publish(msg)
    for attempt in range(1, 3):
        tag, msg = b.take(1)
        require(c.apply(msg) == "poison", "POISON_CLASSIFICATION", message_result(b, c))
        if attempt < 2:
            b.settle(tag, requeue=True)
        elif variant == "discard-poison":
            b.settle(tag)
        else:
            parking.park(msg, attempt)
            # Fail after parking, before ack. Restart reuses the same parking identity.
            b.close_channel()
            parking = Parking(parking.store.restart())
            tag, msg = b.take(1)
            require(parking.park(msg, 3) == "already-parked", "PARKING_DEDUP", {})
            b.settle(tag)
    tag, msg = b.take(2)
    gap = c.apply(msg, variant)
    b.settle(tag, requeue=gap == "gap")
    tag, msg = b.take(3)
    c.apply(msg)
    b.settle(tag)
    out = message_result(b, c)
    out.update(parking=parking.store.read(), gap_answer=gap)
    require(parking.store.read()["records"] == {
                "A1": {"message": events[0], "reason": "poison", "attempts": 2}},
            "POISON_EVIDENCE_MISSING", out)
    require(gap == "gap" and c.store.read()["totals"] == {"B": 5}
            and c.store.read()["versions"] == {"B": 1}, "KEY_ORDER_BROKEN", out)
    require([r["state"] for r in b.store.read()["records"]] == ["done", "ready", "done"]
            and [r["attempts"] for r in b.store.read()["records"]] == [3, 1, 1]
            and c.calls == 4 and not b.tags and len(c.store.read()["effects"]) == 1,
            "POISON_FINAL_STATE", out)
    return out


def channel_identity(variant):
    b = Broker()
    b.publish(event())
    tag, _ = b.take(1)
    before = b.store.committed
    caught = None
    try:
        b.settle(("other-channel", tag[1]))
    except ValueError as error:
        caught = str(error)
    require(caught == "UNKNOWN_DELIVERY_TAG" and b.store.committed == before,
            "CHANNEL_IDENTITY", b.store.read())
    b.close_channel()
    return {"rejected": caught, "broker": b.store.read(), "unsettled_tags": len(b.tags)}


def fencing_takeover(variant):
    a = Authority()
    old = a.acquire("shop-a/order-7:g1", "worker-A")
    locally_checked = a.valid_now(old)
    a.advance(5)  # worker-A is paused; only the coordinator's model time advances.
    new = a.acquire(old.scope, "worker-B")
    r = Resource(a)
    newer = r.write("worker-B", new, new.scope, "new-write", 10)
    checkpoint = r.store.committed
    resumed = r.write("worker-A", old, old.scope, "late-write", 99, variant)
    out = {"local_check_before_pause": locally_checked, "old_valid_now": a.valid_now(old),
           "new_answer": newer, "old_answer": resumed, "resource": r.store.read()}
    require(resumed == {"status": "stale"} and r.store.committed == checkpoint,
            "STALE_HOLDER_EFFECT", out)
    require(newer == {"status": "applied", "value": 10}
            and len(r.store.read()["effects"]) == 1, "TAKEOVER_FINAL_STATE", out)
    return out


def before_new_fence(variant):
    a = Authority()
    old = a.acquire("R:g1", "A")
    a.advance(5)
    new = a.acquire("R:g1", "B")
    r = Resource(a)
    first = r.write("A", old, old.scope, "late-before-fence", 1)
    second = r.write("B", new, new.scope, "new-after", 10)
    third = r.write("A", old, old.scope, "late-after-fence", 100)
    out = {"old_valid_now": a.valid_now(old), "answers": [first, second, third],
           "resource": r.store.read()}
    require(first == {"status": "applied", "value": 1}
            and second == {"status": "applied", "value": 11}
            and third == {"status": "stale"}
            and len(r.store.read()["effects"]) == 2, "FENCE_TIMING_SCOPE", out)
    return out


def same_token(variant):
    a = Authority()
    grant = a.acquire("R:g1", "A")
    r = Resource(a)
    first = r.write("A", grant, grant.scope, "op-1", 5, variant)
    # The receipt-loss boundary retains values, watermarks, operations and effects.
    persisted = r.store.read()
    r = Resource(a, r.store.restart())
    replay = r.write("A", grant, grant.scope, "op-1", 5, variant)
    require(replay == {"status": "replayed", "value": 5}
            and r.store.read() == persisted, "SAME_OPERATION_REPLAY", {
                "first": first, "replay": replay, "persisted": persisted,
                "resource": r.store.read()})
    second = r.write("A", grant, grant.scope, "op-2", 7, variant)
    require(second == {"status": "applied", "value": 12}, "SAME_TOKEN_NEW_OPERATION",
            {"second": second, "resource": r.store.read()})
    before = r.store.committed
    before_conflict = r.store.read()
    conflict = r.write("A", grant, grant.scope, "op-1", 999, variant)
    require(conflict == {"status": "conflict"} and before == r.store.committed,
            "OPERATION_PAYLOAD_CONFLICT", {"answer": conflict, "before": before_conflict,
                                            "after": r.store.read()})
    a.advance(5)
    next_grant = a.acquire(grant.scope, "B")
    cross_lease = r.write("B", next_grant, grant.scope, "op-1", 5)
    require(cross_lease == {"status": "replayed", "value": 5}
            and r.store.read()["watermarks"] == {grant.scope: 2}
            and r.store.read()["values"] == {grant.scope: 12}
            and len(r.store.read()["effects"]) == 2, "CROSS_LEASE_REPLAY", r.store.read())
    return {"answers": [first, replay, second, conflict, cross_lease], "resource": r.store.read()}


def resource_scope(variant):
    a = Authority()
    small = a.acquire("shop-a/R:g1", "A")
    large = a.acquire("shop-a/S:g1", "B")
    r = Resource(a)
    r.write("B", large, large.scope, "op-1", 9, variant)
    independent = r.write("A", small, small.scope, "op-1", 4, variant)
    require(independent == {"status": "applied", "value": 4}, "RESOURCE_SCOPE_COUPLED",
            {"answer": independent, "resource": r.store.read()})
    before = r.store.committed
    attempts = [r.write("attacker", large, large.scope, "evil-owner", 100, variant),
                r.write("B", large, "shop-b/R:g1", "evil-scope", 100, variant),
                r.write("B", large, "shop-a/S:g2", "evil-generation", 100, variant),
                r.write("B", replace(large, token=1000), large.scope, "evil-token", 100, variant)]
    require(attempts == [{"status": "unauthorized"}] * 4 and before == r.store.committed,
            "GRANT_IDENTITY_BYPASS", {"attempts": attempts, "resource": r.store.read()})
    return {"independent_resource": independent, "rejected_grants": attempts,
            "resource": r.store.read()}


def retained_watermark(variant):
    a = Authority()
    old = a.acquire("R:g1", "A")
    a.advance(5)
    new = a.acquire("R:g1", "B")
    r = Resource(a)
    r.write("B", new, new.scope, "new", 10)
    before = r.store.read()
    recovered = r.store.restart()
    if variant == "forget-watermark":
        recovered.transaction(lambda s: s["watermarks"].clear())
    r = Resource(a, recovered)
    answer = r.write("A", old, old.scope, "late", 99)
    require(answer == {"status": "stale"} and r.store.read() == before,
            "WATERMARK_ROLLBACK", {"before": before, "answer": answer, "after": r.store.read()})
    return {"answer": answer, "resource": r.store.read()}


def issuer_reset(variant):
    a = Authority()
    old = a.acquire("R:g1", "A")
    r = Resource(a)
    r.write("A", old, old.scope, "old", 5)
    # Explicit offline recovery: old writers stopped, new epoch installed at receiver.
    r.activate_epoch(2)
    a2 = Authority(epoch=2)
    r.authority = a2
    new = a2.acquire("R:g1", "B")  # counter restarts, epoch must distinguish it.
    a2.issued.add(old)  # Simulate still-valid old issuance proof, not current ownership.
    reject = r.write("A", old, old.scope, "late", 99)
    answer = r.write("B", new, new.scope, "new", 10)
    out = {"old_answer": reject, "new_answer": answer, "resource": r.store.read()}
    require(reject == {"status": "wrong-epoch"} and answer == {"status": "applied", "value": 15}
            and len(r.store.read()["effects"]) == 2, "ISSUER_EPOCH_RESET", out)
    return out


SCENARIOS = {
    "lost-confirm": lost_confirm,
    "commit-before-ack": commit_before_ack,
    "poison-and-order": poison_and_order,
    "channel-identity": channel_identity,
    "fencing-takeover": fencing_takeover,
    "before-new-fence": before_new_fence,
    "same-token": same_token,
    "resource-scope": resource_scope,
    "retained-watermark": retained_watermark,
    "issuer-reset": issuer_reset,
}

MUTANTS = [
    ("lost-confirm", "no-dedup", "DUPLICATE_MESSAGE_EFFECT"),
    ("commit-before-ack", "ack-before-commit", "BUSINESS_COMMIT_BOUNDARY"),
    ("commit-before-ack", "effect-before-receipt", "BUSINESS_COMMIT_BOUNDARY"),
    ("poison-and-order", "discard-poison", "POISON_EVIDENCE_MISSING"),
    ("poison-and-order", "ignore-gap", "KEY_ORDER_BROKEN"),
    ("fencing-takeover", "no-fence", "STALE_HOLDER_EFFECT"),
    ("fencing-takeover", "lie-stale", "STALE_HOLDER_EFFECT"),
    ("same-token", "reject-equal", "SAME_OPERATION_REPLAY"),
    ("same-token", "no-operation-dedup", "SAME_OPERATION_REPLAY"),
    ("same-token", "effect-before-operation", "SAME_OPERATION_REPLAY"),
    ("same-token", "lie-conflict", "OPERATION_PAYLOAD_CONFLICT"),
    ("resource-scope", "global-watermark", "RESOURCE_SCOPE_COUPLED"),
    ("resource-scope", "trust-token", "GRANT_IDENTITY_BYPASS"),
    ("retained-watermark", "forget-watermark", "WATERMARK_ROLLBACK"),
]
