"""Finite business assertions and attributable unsafe-allow probes."""
import argparse
import json
from dataclasses import replace
from itertools import product
from model import (ActiveCache, PreparedUpdate, Request, SessionRecord, TrustedIdentity,
                   VerifiedClaims, cache_accepts, decide, fixture, online_accepts,
                   session_accepts, snapshot_accepts)
from mutants import NAMES, policy_for, unsafe_cached_commit


def require(condition, code):
    if not condition:
        raise AssertionError(code)


def negative_probe(name, policy=decide, unsafe_commit=False):
    store = fixture()
    actor = TrustedIdentity("bob")
    req = Request("red", "o1", "read")
    now = 10
    order = store.orders[("red", "o1")]
    if name == "tenant-from-request":
        # Removed member still owns a stored order. Claiming red cannot restore membership.
        actor = TrustedIdentity("alice")
        store.memberships.remove(("red", "alice"))
    elif name == "default-allow":
        actor, req = TrustedIdentity("alice"), replace(req, action="delete")
    elif name == "missing-identity-allowed":
        actor = None
    elif name == "delegation-expands-action":
        actor, req = TrustedIdentity("carol"), replace(req, action="update-note")
    elif name in {"ignore-grant-expiry", "ignore-grant-revocation", "ignore-ownership-epoch"}:
        actor = TrustedIdentity("carol")
        if name == "ignore-grant-expiry":
            now = 20
        elif name == "ignore-grant-revocation":
            store.grants = tuple(replace(g, revoked=True) for g in store.grants)
        else:
            # ABA: owner comes back, but an old delegation must not revive.
            store.transfer_fixture("red", "o1", "bob")
            store.transfer_fixture("red", "o1", "alice")
            order = store.orders[("red", "o1")]
    elif name == "ignore-object-id":
        actor, req = TrustedIdentity("alice"), replace(req, order_id="o2")
        # Inject an incorrectly loaded order. Policy must reject mismatched object.
    elif name == "cached-allow-after-transfer":
        actor = TrustedIdentity("alice")
        req = replace(req, action="update-note")
        prepared = store.prepare_update(actor, req, "unauthorized-write", now)
        require(prepared is not None, "SETUP_PREPARE")
        store.transfer_fixture("red", "o1", "bob")
        before = dict(store.orders)
        result = (unsafe_cached_commit(store, prepared) if unsafe_commit
                  else store.commit_update(actor, prepared, now))
        require(not result.allowed and store.orders == before and store.effects == [],
                "WRONG_ALLOW:" + name)
        return {"probe": name, "denied": True, "effects": 0}
    before = dict(store.orders)
    if req.action == "update-note":
        prepared = store.prepare_update(actor, req, "unauthorized-write", now, policy)
        require(prepared is None, "WRONG_ALLOW:" + name)
    else:
        decision = policy(actor, req, order, store.memberships, store.grants, now)
        require(not decision.allowed, "WRONG_ALLOW:" + name)
    require(store.orders == before and store.effects == [], "SIDE_EFFECT:" + name)
    return {"probe": name, "denied": True, "effects": 0}


def run_baseline():
    records = []
    token = VerifiedClaims("issuer-A", "alice", frozenset({"orders-api"}), "access", 10, 20, "fixture-t1")
    session = SessionRecord("alice", 20)
    # Cache was populated at 11; revocation happens at 12.
    cache = ActiveCache(True, 11, min(11 + 5, token.expires))
    for now, expected in [(9, False), (10, True), (19, True), (20, False)]:
        require(snapshot_accepts(token, now) == expected, "TOKEN_TIME")
    for field, value in [("issuer", "issuer-B"), ("audience", frozenset({"other-api"})),
                         ("purpose", "id"), ("subject", "")]:
        invalid = replace(token, **{field: value})
        require(not snapshot_accepts(invalid, 12), "TOKEN_PROFILE:" + field)
        require(not online_accepts(invalid, 12, set()), "ONLINE_PROFILE:" + field)
        require(not cache_accepts(invalid, cache, 12), "CACHE_PROFILE:" + field)
    require(online_accepts(token, 12, set()), "ONLINE_VALID_PROFILE")
    for now in (9, 20):
        require(not online_accepts(token, now, set()), "ONLINE_TIME:" + str(now))
        require(not cache_accepts(token, ActiveCache(True, 8, 30), now), "CACHE_TOKEN_TIME:" + str(now))
    require(not cache_accepts(token, ActiveCache(False, 11, 16), 12), "CACHE_INACTIVE")
    require(not cache_accepts(token, ActiveCache(True, 15, 16), 12), "CACHE_NOT_OBSERVED")
    require(session_accepts(session, 11), "SESSION_BEFORE")
    require(not session_accepts(replace(session, revoked=True), 12), "SESSION_REVOKED")
    require(not session_accepts(None, 12), "SESSION_MISSING")
    require(not session_accepts(session, 20), "SESSION_EXPIRED")
    require(snapshot_accepts(token, 12), "OFFLINE_SNAPSHOT_STILL_ACCEPTED")
    require(not online_accepts(token, 12, {token.token_id}), "ONLINE_REVOCATION")
    require(cache_accepts(token, cache, 12) and not cache_accepts(token, cache, 16), "CACHE_WINDOW")
    require(not cache_accepts(token, ActiveCache(True, 11, 50), 20), "CACHE_MUST_NOT_OUTLIVE_EXP")
    records.append({"boundary": "revocation-at-12", "session": False, "offline-snapshot": True,
                    "online-current": False, "cached-at-11-until-16": True})

    # Expected permissions are an explicit business matrix, independent of policy branches.
    expected = {("alice", "red", "o1", "read"), ("alice", "red", "o1", "update-note"),
                ("bob", "red", "o2", "read"), ("bob", "red", "o2", "update-note"),
                ("carol", "red", "o1", "read"), ("mallory", "blue", "o1", "read"),
                ("mallory", "blue", "o1", "update-note")}
    observed = set()
    for actor, tenant, oid, action in product(
            [None, "alice", "bob", "carol", "mallory"], ["red", "blue"],
            ["o1", "o2", "missing"], ["read", "update-note", "delete"]):
        store = fixture()
        identity = TrustedIdentity(actor) if actor else None
        request = Request(tenant, oid, action)
        order = store.orders.get((tenant, oid))
        decision = decide(identity, request, order, store.memberships, store.grants, 10)
        key = (actor, tenant, oid, action)
        require(decision.allowed == (key in expected), "MATRIX:" + repr(key))
        if decision.allowed:
            observed.add(key)
        if action == "read":
            result, payload = store.read(identity, request, 10)
            require(result == decision and payload == ("original" if decision.allowed else None), "READ_DISCLOSURE")
        if action == "update-note":
            before = dict(store.orders)
            prepared = store.prepare_update(identity, request, "changed", 10)
            result = store.commit_update(identity, prepared, 10)
            require(result.allowed == decision.allowed, "UPDATE_DECISION")
            if decision.allowed:
                require(store.orders[(tenant, oid)].note == "changed" and
                        store.effects == [(actor, tenant, oid, "note-updated")], "UPDATE_EFFECT")
                require(all(v == before[k] for k, v in store.orders.items() if k != (tenant, oid)), "UNRELATED_WRITE")
            else:
                require(store.orders == before and store.effects == [], "DENIED_WRITE_EFFECT")
    require(observed == expected, "EXACT_ALLOW_SET")
    records.append({"matrix": "actors x tenants x objects x actions", "combinations": 90,
                    "allowed": [list(k) for k in sorted(observed)]})
    for name in NAMES:
        records.append(negative_probe(name))

    # Only the exact object, current owner and actor can support a delegation.
    for field, value in [("tenant", "blue"), ("order_id", "o2"),
                         ("grantor", "bob"), ("delegate", "bob")]:
        store = fixture()
        store.grants = tuple(replace(g, **{field: value}) for g in store.grants)
        result, payload = store.read(TrustedIdentity("carol"), Request("red", "o1", "read"), 10)
        require(not result.allowed and payload is None, "DELEGATION_BINDING:" + field)
    store = fixture()
    store.memberships.remove(("red", "alice"))
    result, payload = store.read(TrustedIdentity("carol"), Request("red", "o1", "read"), 10)
    require(not result.allowed and payload is None, "GRANTOR_MEMBERSHIP_REMOVED")

    # Delegation identity is insufficient without an explicit allowed action.
    store = fixture()
    store.grants = tuple(replace(g, actions=frozenset()) for g in store.grants)
    before = dict(store.orders)
    result, payload = store.read(TrustedIdentity("carol"), Request("red", "o1", "read"), 10)
    require(not result.allowed and payload is None and store.orders == before and not store.effects,
            "EMPTY_GRANT_ACTIONS")

    # The same owner can change content while another preparation is outstanding.
    store = fixture()
    identity, req = TrustedIdentity("alice"), Request("red", "o1", "update-note")
    older = store.prepare_update(identity, req, "older-note", 10)
    newer = store.prepare_update(identity, req, "newer-note", 10)
    require(older is not None and newer is not None, "SETUP_TWO_PREPARATIONS")
    first = store.commit_update(identity, newer, 11)
    require(first.allowed and store.orders[("red", "o1")].note == "newer-note"
            and store.effects == [("alice", "red", "o1", "note-updated")], "NEWER_COMMIT")
    before, effects = dict(store.orders), list(store.effects)
    stale = store.commit_update(identity, older, 12)
    require(not stale.allowed and stale.reason == "stale-object"
            and store.orders == before and store.effects == effects, "STALE_PREPARATION")

    # A successful commit consumes the prepared revision, even if the owner stays the same.
    store = fixture()
    prepared = store.prepare_update(identity, req, "once", 10)
    require(store.commit_update(identity, prepared, 11).allowed, "SETUP_SINGLE_COMMIT")
    repeated = store.commit_update(identity, prepared, 12)
    require(not repeated.allowed and repeated.reason == "stale-object"
            and store.orders[("red", "o1")].note == "once"
            and store.orders[("red", "o1")].revision == 2
            and store.effects == [("alice", "red", "o1", "note-updated")], "REPLAY_PREPARATION")
    records.append({"boundaries": ["online-profile-and-time", "inactive-or-future-cache",
                                    "empty-delegation-actions", "same-owner-stale-preparation",
                                    "repeated-prepared-commit"],
                    "stale-write-effects": 0, "single-commit-effects": 1, "committed-revision": 2})

    # Revoking membership between prepare and commit is not an object revision change.
    store = fixture()
    identity, req = TrustedIdentity("alice"), Request("red", "o1", "update-note")
    prepared = store.prepare_update(identity, req, "changed", 10)
    store.memberships.remove(("red", "alice"))
    before = dict(store.orders)
    result = store.commit_update(identity, prepared, 11)
    require(not result.allowed and result.reason == "tenant-membership", "COMMIT_CURRENT_MEMBERSHIP")
    require(store.orders == before and store.effects == [], "REVOKED_COMMIT_EFFECT")
    # A preparation for alice cannot be executed by carol.
    store = fixture()
    prepared = store.prepare_update(identity, req, "changed", 10)
    result = store.commit_update(TrustedIdentity("carol"), prepared, 11)
    require(not result.allowed and store.effects == [], "PREPARED_ACTOR_BINDING")
    # A read approval must never turn into a write by choosing a different handler.
    forged = PreparedUpdate("carol", replace(req, action="read"), 1, "wrong-write")
    result = store.commit_update(TrustedIdentity("carol"), forged, 11)
    require(not result.allowed and store.effects == [], "COMMIT_ACTION_BINDING")
    result, payload = store.read(identity, req, 11)
    require(not result.allowed and payload is None, "READ_ACTION_BINDING")
    # Old owner's grant ceases on transfer; new owner succeeds immediately.
    store.transfer_fixture("red", "o1", "bob")
    for actor, allowed in [("alice", False), ("carol", False), ("bob", True)]:
        decision, payload = store.read(TrustedIdentity(actor), replace(req, action="read"), 11)
        require(decision.allowed == allowed and (payload is not None) == allowed, "TRANSFER_CURRENT_OWNER")
    records.append({"transitions": ["membership-revoked-before-commit", "prepared-actor-changed",
                                    "ownership-transferred"], "stale-writes": 0})
    return {"status": "pass", "model": "trusted-input sequential decision model", "records": records}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutant", choices=NAMES)
    args = parser.parse_args()
    if args.mutant:
        try:
            negative_probe(args.mutant, policy_for(args.mutant),
                           unsafe_commit=args.mutant == "cached-allow-after-transfer")
        except AssertionError as exc:
            print(json.dumps({"status": "rejected", "mutant": args.mutant, "assertion": str(exc)}, sort_keys=True))
            return 3
        print(json.dumps({"status": "survived", "mutant": args.mutant}))
        return 0
    print(json.dumps(run_baseline(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
