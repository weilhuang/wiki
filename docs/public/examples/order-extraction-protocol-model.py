#!/usr/bin/env python3
"""A sequential teaching model, not a database, broker or service implementation.

Run: python3 order_extraction_model.py
Only standard-library dependencies. No network, persistent storage or processes.
Checks: replay identity, snapshot compatibility, single-writer migration gates,
and declared module-dependency fixtures. See the accompanying article for gaps.
"""

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import unittest


def digest(value):
    """Canonicalization is limited to these JSON fixtures, not arbitrary APIs."""
    data = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class Rejected(ValueError):
    pass


@dataclass
class Store:
    # An operation result and its order are modeled as one indivisible transition.
    orders: dict = field(default_factory=dict)
    operations: dict = field(default_factory=dict)


class Migration:
    """One tenant; an epoch stands for a write-time checked fencing token.

    A real implementation must enforce the gate at the database write boundary.
    An API/router check alone does not provide this model's atomic transitions.
    """

    def __init__(self):
        self.stores = {"old": Store(), "new": Store()}
        self.owner = "old"
        self.epoch = 1
        self.writes_open = True

    def create(self, target, epoch, key, payload):
        if not self.writes_open or (target, epoch) != (self.owner, self.epoch):
            raise Rejected("writer fenced")
        store = self.stores[target]
        fingerprint = digest(payload)
        if key in store.operations:
            saved = store.operations[key]
            if saved["fingerprint"] != fingerprint:
                raise Rejected("same key, different request")
            return deepcopy(saved["result"])
        # The fixture's key includes tenant and operation scope.
        order_id = "order-" + payload["business_id"]
        if order_id in store.orders:
            raise Rejected("business identity already exists; do not create again")
        result = {"order_id": order_id, "state": "CONFIRMED", "version": 1}
        store.orders[order_id] = dict(result, quantity=payload["quantity"])
        store.operations[key] = {"fingerprint": fingerprint, "result": result}
        return deepcopy(result)

    def fence(self, target, epoch):
        if (target, epoch) != (self.owner, self.epoch):
            raise Rejected("wrong owner")
        self.writes_open = False
        # In this sequential model there are no in-flight transactions to drain.

    def copy_from_owner(self, target):
        if target == self.owner:
            raise Rejected("copy target must be the inactive store")
        self.stores[target] = deepcopy(self.stores[self.owner])

    def activate(self, target):
        if self.writes_open or target == self.owner:
            raise Rejected("fence current owner first")
        if self.stores[target] != self.stores[self.owner]:
            raise Rejected("orders AND operation results must match")
        self.owner = target
        self.epoch += 1
        self.writes_open = True


class Projection:
    """Only complete snapshots; version gaps are NOT safe for delta events."""

    def __init__(self):
        self.seen = {}
        self.rows = {}
        # Retain semantic fingerprints for every observed version in this process.
        # No pruning or crash recovery is modeled; production retention needs a contract.
        self.version_fingerprints = {}

    def apply(self, event):
        fingerprint = digest(event)
        event_id = event["event_id"]
        if event_id in self.seen:
            if self.seen[event_id] != fingerprint:
                raise Rejected("same event id, different payload")
            return "duplicate"
        if event["schema_version"] != 1:
            raise Rejected("unsupported schema")
        if event["state"] not in {"CONFIRMED", "CANCELLED"}:
            raise Rejected("unsupported state")
        row = {k: event[k] for k in ("order_id", "version", "state", "quantity")}
        version_key = (row["order_id"], row["version"])
        version_fingerprint = digest(row)
        known_fingerprint = self.version_fingerprints.get(version_key)
        if known_fingerprint is not None and known_fingerprint != version_fingerprint:
            raise Rejected("same aggregate version, different snapshot")
        old = self.rows.get(row["order_id"])
        if old and row["version"] <= old["version"]:
            self.version_fingerprints[version_key] = version_fingerprint
            self.seen[event_id] = fingerprint
            return "stale"
        # One indivisible transition in the model, not a real durable transaction.
        self.rows[row["order_id"]] = row
        self.version_fingerprints[version_key] = version_fingerprint
        self.seen[event_id] = fingerprint
        return "applied"


def check_dependencies(edges):
    """Validate a declared fixture, not inferred Java/Python production imports."""
    allowed = {"checkout": {"orders", "inventory"}, "orders": set(),
               "inventory": set(), "reporting": {"orders"}}
    graph = {module: set() for module in allowed}
    problems = []
    for source, target, public_api in edges:
        if source not in allowed or target not in allowed:
            problems.append("unknown module")
            continue
        graph[source].add(target)
        if not public_api:
            problems.append("internal package access")
        if target not in allowed[source]:
            problems.append("undeclared dependency")
    visiting, done = set(), set()

    def visit(node):
        if node in visiting:
            return True
        if node in done:
            return False
        visiting.add(node)
        cyclic = any(visit(child) for child in graph[node])
        visiting.remove(node)
        done.add(node)
        return cyclic

    if any(visit(module) for module in graph):
        problems.append("cycle")
    return problems


def snapshot(event_id="e1", version=1, state="CONFIRMED", **extra):
    event = {"event_id": event_id, "schema_version": 1, "order_id": "o17",
             "version": version, "state": state, "quantity": 2}
    return dict(event, **extra)


class ProtocolTests(unittest.TestCase):
    def test_lost_response_replay_keeps_one_order(self):
        migration = Migration()
        payload = {"business_id": "purchase-17", "quantity": 2}
        expected = {"order_id": "order-purchase-17", "state": "CONFIRMED", "version": 1}
        # Check fixed contract facts before dropping the response and replaying.
        first = migration.create("old", 1, "tenant7-create-k1", payload)
        self.assertEqual(first, expected)
        replay = migration.create("old", 1, "tenant7-create-k1", payload)
        self.assertEqual(replay, expected)
        expected_orders = {
            "order-purchase-17": {"order_id": "order-purchase-17", "state": "CONFIRMED",
                                  "version": 1, "quantity": 2}}
        expected_operations = {
            "tenant7-create-k1": {
                "fingerprint": "a893edaf36ab592c615d2d8806c723fdc58dcfe07806e59d76d1f80064e14bd2",
                "result": {"order_id": "order-purchase-17", "state": "CONFIRMED", "version": 1}}}
        self.assertEqual(migration.stores["old"].orders, expected_orders)
        self.assertEqual(migration.stores["old"].operations, expected_operations)
        # A second business identity must create its own correct order.
        second = migration.create("old", 1, "tenant7-create-k2",
                                  {"business_id": "purchase-18", "quantity": 3})
        self.assertEqual(second, {"order_id": "order-purchase-18", "state": "CONFIRMED", "version": 1})
        expected_orders["order-purchase-18"] = {
            "order_id": "order-purchase-18", "state": "CONFIRMED", "version": 1, "quantity": 3}
        expected_operations["tenant7-create-k2"] = {
            "fingerprint": "fa0594cca8e10348ca45aa7d6d3f15339571fe1131005abf7827dcab46256c70",
            "result": {"order_id": "order-purchase-18", "state": "CONFIRMED", "version": 1}}
        self.assertEqual(migration.stores["old"].orders, expected_orders)
        self.assertEqual(migration.stores["old"].operations, expected_operations)

    def test_same_key_changed_request_is_rejected(self):
        migration = Migration()
        migration.create("old", 1, "k1", {"business_id": "purchase-17", "quantity": 2})
        before = deepcopy(migration.stores)
        with self.assertRaisesRegex(Rejected, "different request"):
            migration.create("old", 1, "k1", {"business_id": "purchase-17", "quantity": 3})
        self.assertEqual(migration.stores, before)

    def test_new_key_cannot_create_same_business_order(self):
        migration = Migration()
        payload = {"business_id": "purchase-17", "quantity": 2}
        migration.create("old", 1, "k1", payload)
        before = deepcopy(migration.stores)
        with self.assertRaisesRegex(Rejected, "business identity already exists"):
            migration.create("old", 1, "k2", payload)
        self.assertEqual(migration.stores, before)

    def test_route_change_without_fence_is_rejected(self):
        migration = Migration()
        migration.copy_from_owner("new")
        before = deepcopy(migration.__dict__)
        with self.assertRaisesRegex(Rejected, "fence"):
            migration.activate("new")
        self.assertEqual(migration.__dict__, before)
        migration.fence("old", 1)
        fenced = deepcopy(migration.__dict__)
        # This is the current owner and current epoch, but writes are now CLOSED.
        with self.assertRaisesRegex(Rejected, "writer fenced"):
            migration.create("old", 1, "k1", {"business_id": "purchase-17", "quantity": 2})
        self.assertEqual(migration.__dict__, fenced)

    def test_stale_writer_and_token_are_rejected_after_cutover(self):
        migration = Migration()
        migration.fence("old", 1)
        migration.copy_from_owner("new")
        migration.activate("new")
        self.assertEqual((migration.owner, migration.epoch, migration.writes_open), ("new", 2, True))
        before = deepcopy(migration.stores)
        for target, epoch in (("old", 1), ("new", 1)):
            with self.assertRaisesRegex(Rejected, "writer fenced"):
                migration.create(target, epoch, "k1", {"business_id": "purchase-17", "quantity": 2})
            self.assertEqual(migration.stores, before)
        self.assertEqual(migration.create("new", 2, "k1", {"business_id": "purchase-17", "quantity": 2}),
                         {"order_id": "order-purchase-17", "state": "CONFIRMED", "version": 1})
        self.assertEqual(migration.stores["new"].orders["order-purchase-17"]["quantity"], 2)

    def test_replay_after_cutover_uses_copied_operation_result(self):
        migration = Migration()
        result = migration.create("old", 1, "k1", {"business_id": "purchase-17", "quantity": 2})
        migration.fence("old", 1)
        migration.copy_from_owner("new")
        migration.activate("new")
        self.assertEqual(result, migration.create("new", 2, "k1", {"business_id": "purchase-17", "quantity": 2}))
        self.assertEqual(len(migration.stores["new"].orders), 1)

    def test_copying_orders_without_operations_cannot_activate(self):
        migration = Migration()
        migration.create("old", 1, "k1", {"business_id": "purchase-17", "quantity": 2})
        migration.fence("old", 1)
        migration.copy_from_owner("new")
        migration.stores["new"].operations.clear()  # Intentional defect.
        with self.assertRaisesRegex(Rejected, "operation results"):
            migration.activate("new")

    def test_blind_rollback_fails_until_reverse_copy(self):
        migration = Migration()
        migration.fence("old", 1)
        migration.copy_from_owner("new")
        migration.activate("new")
        new_order = migration.create("new", 2, "k2", {"business_id": "purchase-17", "quantity": 2})
        migration.fence("new", 2)
        with self.assertRaisesRegex(Rejected, "must match"):
            migration.activate("old")
        migration.copy_from_owner("old")
        migration.activate("old")
        replay = migration.create("old", 3, "k2", {"business_id": "purchase-17", "quantity": 2})
        self.assertEqual(new_order, replay)

    def test_duplicate_event_identity_and_conflict(self):
        projection = Projection()
        event = snapshot()
        self.assertEqual(projection.apply(event), "applied")
        self.assertEqual(projection.apply(event), "duplicate")
        with self.assertRaisesRegex(Rejected, "different payload"):
            projection.apply(dict(event, quantity=9))
        self.assertEqual(projection.rows["o17"]["quantity"], 2)

    def test_full_snapshot_can_skip_old_version(self):
        projection = Projection()
        self.assertEqual(projection.apply(snapshot("e2", 2, "CANCELLED")), "applied")
        self.assertEqual(projection.apply(snapshot()), "stale")
        self.assertEqual(projection.rows["o17"]["state"], "CANCELLED")

    def test_equal_version_conflict_is_not_silently_ignored(self):
        projection = Projection()
        projection.apply(snapshot())
        before = deepcopy(projection.__dict__)
        with self.assertRaisesRegex(Rejected, "different snapshot"):
            projection.apply(snapshot("e-another", quantity=9))
        self.assertEqual(projection.__dict__, before)
        # After v2, an independently identified conflicting v1 must still fail.
        projection.apply(snapshot("e2", 2, "CANCELLED"))
        before = deepcopy(projection.__dict__)
        with self.assertRaisesRegex(Rejected, "different snapshot"):
            projection.apply(snapshot("e-old-conflict", 1, "CONFIRMED", quantity=9))
        self.assertEqual(projection.__dict__, before)
        self.assertNotIn("e-old-conflict", projection.seen)
        # An old snapshot with matching semantic content is harmless and recorded.
        self.assertEqual(projection.apply(snapshot("e-old-identical")), "stale")
        self.assertEqual(projection.rows["o17"], {
            "order_id": "o17", "version": 2, "state": "CANCELLED", "quantity": 2})

    def test_additive_field_and_unknown_schema_or_state(self):
        projection = Projection()
        self.assertEqual(projection.apply(snapshot(note="optional")), "applied")
        for extra in ({"schema_version": 2}, {"state": "PENDING_RESERVATION"}):
            event = dict(snapshot("e2", 2), **extra)
            with self.assertRaises(Rejected):
                projection.apply(event)
            self.assertNotIn("e2", projection.seen)

    def test_module_dependency_positive_and_negative_fixtures(self):
        good = [("checkout", "orders", True), ("checkout", "inventory", True)]
        self.assertEqual(check_dependencies(good), [])
        self.assertIn("internal package access",
                      check_dependencies([("reporting", "orders", False)]))
        self.assertIn("cycle", check_dependencies(
            [("orders", "inventory", True), ("inventory", "orders", True)]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
