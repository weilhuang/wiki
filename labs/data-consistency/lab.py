#!/usr/bin/env python3
"""Real MySQL/Redis integration candidate. Standard library; no simulated DB.
Only run.sh's label-verified, isolated containers are accepted. Do not import this
module and label its helper tests a MySQL/Redis pass. See RESULT-CONTRACT.md.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCOPE = "shop-a/create-order:v1"
EXPECTED_CASES = {
    "d1": ["D1.naive_lost_update", "D1.conditional_update", "D1.locking_read", "D1.snapshot_vs_current", "D1.deadlock_cycle"],
    "d2": ["D2.concurrent_same_key", "D2.payload_conflict", "D2.before_commit_disconnect", "D2.after_commit_response_lost", "D2.retention_boundary", "D2.saved_rejection"],
    "d3": ["D3.business_commit_before_relay", "D3.publish_before_mark", "D3.consumer_before_commit", "D3.consumer_after_commit", "D3.split_commit_negative_control"],
    "d4": ["D4.stale_refill", "D4.version_watermark", "D4.invalidation_delivery_loss", "D4.expiry_and_watermark_loss", "D4.concurrent_fill_after_floor"],
    "d5": ["D5.six_failure_recovery", "D5.schema_v2_backwards_compatible_snapshot"],
}


def require(condition, message="contract violated"):
    if not condition:
        raise AssertionError(message)


def only_sql_error(lines, code):
    # Error frames must contain exactly the expected error, not a mixture of
    # duplicate-key/deadlock and an unrelated syntax or connection failure.
    errors = [line for line in lines if line.startswith("ERROR ")]
    return len(lines) == 1 and len(errors) == 1 and errors[0].startswith(f"ERROR {code} ")


def q(value):
    """Data values as hex expressions: never interpolate untrusted SQL syntax."""
    return "CONVERT(0x" + str(value).encode().hex() + " USING utf8mb4)"


def canonical_hash(business_id, quantity):
    body = {"business_id": business_id, "quantity": quantity, "sku": "sku-a"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SqlError(RuntimeError):
    def __init__(self, lines):
        super().__init__("\n".join(lines))
        self.lines = lines


class Conflict(RuntimeError):
    pass


class UnknownResult(RuntimeError):
    pass


class Evidence:
    def __init__(self, out):
        self.out = out
        self.lock = threading.Lock()
        self.records = []

    def log(self, kind, **fields):
        record = {"kind": kind, "monotonic_ns": time.monotonic_ns(), **fields}
        with self.lock:
            with (self.out / "trace.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def case(self, name, fn):
        self.log("case_begin", name=name)
        try:
            details = fn()
        except BaseException as error:
            self.records.append({"case": name, "status": "FAIL", "error": str(error)})
            self.log("case_fail", name=name, error=repr(error))
            raise
        self.records.append({"case": name, "status": "PASS", "observed": details})
        self.log("case_pass", name=name, observed=details)


class Session:
    """One live mysql CLI equals one physical server session.

    --force lets the sentinel execute after a deliberate SQL error. The harness
    raises SqlError on every ERROR line; it never silently commits after it.
    """
    def __init__(self, container, evidence, name):
        self.evidence, self.name = evidence, name
        self.lines = queue.Queue()
        self.pending = None
        self.proc = subprocess.Popen(
            ["docker", "exec", "-i", container, "mysql", "--protocol=socket", "-uroot",
             "--batch", "--raw", "--skip-column-names", "--unbuffered", "--force",
             "--skip-reconnect", "--default-character-set=utf8mb4", "consistency_lab"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        self.query("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ; SET autocommit=1")
        self.cid = int(self.query("SELECT CONNECTION_ID()")[0])
        evidence.log("session_open", name=name, connection_id=self.cid)

    def _read(self):
        for line in self.proc.stdout:
            self.lines.put(line.rstrip("\n"))
        self.lines.put(None)

    def send(self, sql):
        if self.pending is not None:
            raise RuntimeError("Only one in-flight request is permitted per session")
        self.pending = "__KS_END_" + uuid.uuid4().hex
        self.evidence.log("sql_send", session=self.name, sql=sql)
        self.proc.stdin.write(sql.rstrip().rstrip(";") + ";\nSELECT '" + self.pending + "';\n")
        self.proc.stdin.flush()

    def receive(self, timeout=25, allow_error=False):
        token = self.pending
        if token is None:
            raise RuntimeError("No in-flight request")
        deadline, result = time.monotonic() + timeout, []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{self.name}: SQL frame did not finish")
            line = self.lines.get(timeout=remaining)
            if line is None:
                raise RuntimeError(f"{self.name}: mysql CLI exited with partial output {result!r}")
            if line == token:
                break
            result.append(line)
        self.pending = None
        self.evidence.log("sql_result", session=self.name, connection_id=getattr(self, "cid", None), lines=result)
        if not allow_error and any(line.startswith("ERROR ") for line in result):
            raise SqlError(result)
        return result

    def query(self, sql, allow_error=False):
        self.send(sql)
        return self.receive(allow_error=allow_error)

    def close(self):
        # Normal SQL rollback is evidence. If a frame is still blocked, the owned
        # container teardown kills the connection and MySQL rolls its tx back.
        if self.proc.poll() is None and self.pending is None:
            try:
                self.query("ROLLBACK")
                self.proc.stdin.close()
                self.proc.wait(timeout=3)
            except Exception as error:
                self.evidence.log("session_close_error", session=self.name, error=repr(error))
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=3)
        self.evidence.log("session_closed", session=self.name, client_exit_code=self.proc.returncode)


class Lab:
    def __init__(self, args, evidence):
        self.args, self.ev = args, evidence
        for container in (args.mysql, args.redis):
            if not re.fullmatch(r"[a-f0-9]{12,64}", container):
                raise ValueError("An explicit run-owned container ID is required")
            owner = subprocess.check_output(
                ["docker", "inspect", "--format", '{{index .Config.Labels "knowledge-station.owner"}}', container],
                text=True, timeout=10).strip()
            if owner != args.owner:
                raise RuntimeError("Container owner label mismatch; refusing access")
        self.sessions = []
        self.db = self.session("observer")
        self.db.query((ROOT / "sql/schema.sql").read_text())
        self.redis_keys = set()

    def session(self, name):
        result = Session(self.args.mysql, self.ev, name)
        self.sessions.append(result)
        return result

    def reset(self, stock=10):
        # Only newly-created schema in label-verified, run-owned container.
        self.db.query(";".join("DELETE FROM " + table for table in (
            "effect_log", "order_projection", "consumer_dedup", "delivery_receipts",
            "outbox", "operations", "orders", "inventory")))
        self.db.query(f"INSERT INTO inventory VALUES ('sku-a',{stock},{stock},0),('sku-b',{stock},{stock},0)")
        if self.redis_keys:
            self.redis("DEL", *sorted(self.redis_keys))

    def scalar(self, sql):
        result = self.db.query(sql)
        if len(result) != 1:
            raise AssertionError(result)
        return result[0]

    def wait_for_lock(self, waiting_cid):
        sql = ("SELECT COUNT(*) FROM performance_schema.data_lock_waits w "
               "JOIN performance_schema.threads t ON w.REQUESTING_THREAD_ID=t.THREAD_ID "
               f"WHERE t.PROCESSLIST_ID={int(waiting_cid)}")
        deadline = time.monotonic() + 8
        while int(self.scalar(sql)) == 0:
            if time.monotonic() >= deadline:
                raise AssertionError("No engine lock wait observed before the barrier deadline")
            time.sleep(0.02)  # Poll a server predicate, never infer ordering from a delay.
        self.db.query("SELECT w.REQUESTING_ENGINE_TRANSACTION_ID,w.BLOCKING_ENGINE_TRANSACTION_ID,"
                      "l.OBJECT_NAME,l.INDEX_NAME,l.LOCK_TYPE,l.LOCK_MODE,l.LOCK_DATA "
                      "FROM performance_schema.data_lock_waits w JOIN performance_schema.data_locks l "
                      "ON w.REQUESTING_ENGINE_LOCK_ID=l.ENGINE_LOCK_ID")

    def redis(self, *args):
        result = subprocess.run(["docker", "exec", self.args.redis, "redis-cli", "--raw", *map(str, args)],
                                capture_output=True, text=True, timeout=10)
        self.ev.log("redis", argv=list(map(str, args)), stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode)
        if result.returncode or result.stdout.startswith(("ERR ", "OOM ", "NOAUTH ")):
            raise RuntimeError(result.stdout + result.stderr)
        return result.stdout.rstrip("\n")

    def keys(self, order_id):
        # Hash tag ensures a potential cluster port preserves same-slot Lua keys.
        prefix = "ks:" + self.args.owner + ":{" + order_id + "}"
        result = (prefix + ":floor", prefix + ":value")
        self.redis_keys.update(result)
        return result

    def cache_fill(self, order_id, version, payload, ttl=60000):
        return int(self.redis("EVAL", (ROOT / "lua/fill.lua").read_text(), 2, *self.keys(order_id), version, payload, ttl))

    def invalidate(self, order_id, version):
        return int(self.redis("EVAL", (ROOT / "lua/invalidate.lua").read_text(), 2, *self.keys(order_id), version))

    def begin_operation(self, session, key, business_id, quantity=1):
        session.query("START TRANSACTION")
        digest = canonical_hash(business_id, quantity)
        session.query(f"INSERT INTO operations(scope,idem_key,request_hash,status) VALUES ({q(SCOPE)},{q(key)},{q(digest)},'pending')")

    def finish_operation(self, session, key, business_id, quantity=1, fault=None):
        order_id = "ord-" + business_id
        rows = session.query(f"UPDATE inventory SET available=available-{int(quantity)},version=version+1 "
                             f"WHERE sku='sku-a' AND available>={int(quantity)}; SELECT ROW_COUNT()")
        if rows != ["1"]:
            response = {"status": "rejected", "reason": "insufficient_stock"}
            session.query(f"UPDATE operations SET status='rejected',response_json={q(json.dumps(response))} WHERE scope={q(SCOPE)} AND idem_key={q(key)}")
        else:
            session.query(f"INSERT INTO orders VALUES ({q(order_id)},{q(SCOPE)},{q(business_id)},'sku-a',{int(quantity)},'reserved',1)")
            event_id = "evt-" + order_id
            payload = {"schema_version": 1, "order_id": order_id, "quantity": quantity, "state": "reserved", "version": 1}
            session.query(f"INSERT INTO outbox(event_id,order_id,aggregate_version,schema_version,payload) VALUES ({q(event_id)},{q(order_id)},1,1,{q(json.dumps(payload))})")
            response = {"status": "committed", "order_id": order_id, "quantity": quantity}
            session.query(f"UPDATE operations SET status='committed',order_id={q(order_id)},response_json={q(json.dumps(response))} WHERE scope={q(SCOPE)} AND idem_key={q(key)}")
        if fault == "before_commit":
            # Terminate just this MySQL server connection, not the DB process.
            self.db.query(f"KILL CONNECTION {session.cid}")
            raise UnknownResult("connection killed before commit")
        session.query("COMMIT")
        if fault == "after_commit":
            raise UnknownResult("committed response deliberately discarded by caller adapter")
        return response

    def create(self, key, business_id, quantity=1, fault=None):
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        session = self.session("create-" + key)
        try:
            try:
                self.begin_operation(session, key, business_id, quantity)
            except SqlError as error:
                session.query("ROLLBACK")
                if not only_sql_error(error.lines, 1062):
                    raise
                saved = session.query(f"SELECT request_hash,response_json FROM operations WHERE scope={q(SCOPE)} AND idem_key={q(key)}")
                if len(saved) != 1:
                    raise AssertionError("Missing durable operation after duplicate-key arbitration")
                digest, response = saved[0].split("\t", 1)
                if digest != canonical_hash(business_id, quantity):
                    raise Conflict("Same idempotency scope/key, different canonical payload")
                return json.loads(response)
            return self.finish_operation(session, key, business_id, quantity, fault)
        except BaseException:
            if fault != "before_commit" and session.proc.poll() is None:
                session.query("ROLLBACK")
            raise
        finally:
            session.close()

    def inventory_check(self):
        violations = self.db.query((ROOT / "sql/reconcile.sql").read_text().split(";")[0])
        if violations:
            raise AssertionError("inventory conservation violated: " + repr(violations))

    def relay(self, fault=None):
        # Deliberately one relay process. A multi-worker lease algorithm is a
        # design exercise, not falsely claimed as tested by this serial relay.
        rows = self.db.query("SELECT event_id,payload FROM outbox WHERE sent=0 ORDER BY created_at,event_id LIMIT 1")
        if not rows:
            return None
        event_id, payload = rows[0].split("\t", 1)
        self.db.query(f"UPDATE outbox SET attempts=attempts+1 WHERE event_id={q(event_id)}")
        receiver = self.session("delivery-receiver")
        try:
            receiver.query(f"START TRANSACTION; INSERT INTO delivery_receipts(event_id,payload) VALUES ({q(event_id)},{q(payload)}); COMMIT")
        finally:
            receiver.close()
        if fault == "after_publish":
            raise UnknownResult("receiver committed; relay omitted sent update")
        self.db.query(f"UPDATE outbox SET sent=1 WHERE event_id={q(event_id)}")
        return event_id

    def consume(self, receipt_id, fault=None):
        row = self.db.query(f"SELECT event_id,payload FROM delivery_receipts WHERE receipt_id={int(receipt_id)}")
        if len(row) != 1:
            raise AssertionError("one receipt required")
        event_id, raw = row[0].split("\t", 1)
        payload = json.loads(raw)
        if payload["schema_version"] not in (1, 2):
            raise ValueError("unsupported event schema; quarantine, do not acknowledge")
        for field in ("order_id", "quantity", "state", "version"):
            if field not in payload:
                raise ValueError("missing required field: " + field)
        if payload["state"] != "reserved" or payload["quantity"] <= 0:
            raise ValueError("invalid snapshot domain")
        session = self.session("consumer")
        try:
            session.query("START TRANSACTION")
            try:
                session.query(f"INSERT INTO consumer_dedup VALUES ('orders-v1',{q(event_id)})")
            except SqlError as error:
                session.query("ROLLBACK")
                if only_sql_error(error.lines, 1062):
                    return "duplicate"
                raise
            order_id, version = payload["order_id"], int(payload["version"])
            existing = session.query(f"SELECT version FROM order_projection WHERE order_id={q(order_id)} FOR UPDATE")
            if not existing:
                session.query(f"INSERT INTO order_projection VALUES ({q(order_id)},{int(payload['quantity'])},{q(payload['state'])},{version})")
            elif int(existing[0]) < version:
                session.query(f"UPDATE order_projection SET quantity={int(payload['quantity'])},state={q(payload['state'])},version={version} WHERE order_id={q(order_id)}")
            session.query(f"INSERT INTO effect_log(event_id,order_id) VALUES ({q(event_id)},{q(order_id)})")
            if fault == "before_commit":
                self.db.query(f"KILL CONNECTION {session.cid}")
                raise UnknownResult("consumer connection killed before commit")
            session.query("COMMIT")
            if fault == "after_commit":
                raise UnknownResult("consumer committed; delivery acknowledgment deliberately omitted")
            return "applied"
        except BaseException:
            if fault != "before_commit" and session.proc.poll() is None:
                session.query("ROLLBACK")
            raise
        finally:
            session.close()

    def expect_unknown(self, fn):
        try:
            fn()
        except UnknownResult as error:
            self.ev.log("injected_failure", error=str(error))
        else:
            raise AssertionError("Fault injection was not reached")

    def d1(self):
        def naive():
            self.reset(1)
            a, b = self.session("naive-a"), self.session("naive-b")
            a.query("START TRANSACTION"); b.query("START TRANSACTION")
            require(a.query("SELECT available FROM inventory WHERE sku='sku-a'") == ["1"], "contract violated")
            require(b.query("SELECT available FROM inventory WHERE sku='sku-a'") == ["1"], "contract violated")
            # The two completed reads form the explicit barrier.
            for s, oid in ((a, "na"), (b, "nb")):
                s.query(f"UPDATE inventory SET available=0 WHERE sku='sku-a'; INSERT INTO orders VALUES ('{oid}','naive','{oid}','sku-a',1,'reserved',1); COMMIT")
            observed = self.scalar("SELECT CONCAT((SELECT available FROM inventory WHERE sku='sku-a'),':',(SELECT SUM(quantity) FROM orders))")
            require(observed == "0:2", observed)
            a.close(); b.close()
            return {"available": 0, "reserved": 2, "negative_control_detected": True}
        self.ev.case("D1.naive_lost_update", naive)

        def conditional():
            self.reset(1)
            a, b = self.session("condition-a"), self.session("condition-b")
            a.query("START TRANSACTION")
            require(a.query("UPDATE inventory SET available=available-1 WHERE sku='sku-a' AND available>=1; SELECT ROW_COUNT()") == ["1"], "contract violated")
            b.query("START TRANSACTION")
            b.send("UPDATE inventory SET available=available-1 WHERE sku='sku-a' AND available>=1; SELECT ROW_COUNT()")
            self.wait_for_lock(b.cid)
            a.query("INSERT INTO orders VALUES ('ca','conditional','ca','sku-a',1,'reserved',1); COMMIT")
            require(b.receive() == ["0"], "contract violated")
            b.query("ROLLBACK")
            self.inventory_check()
            a.close(); b.close()
            return {"affected_rows": [1, 0], "lock_wait_observed": True}
        self.ev.case("D1.conditional_update", conditional)

        def locking():
            self.reset(1)
            a, b = self.session("locking-a"), self.session("locking-b")
            a.query("START TRANSACTION"); b.query("START TRANSACTION")
            require(a.query("SELECT available FROM inventory WHERE sku='sku-a' FOR UPDATE") == ["1"], "contract violated")
            b.send("SELECT available FROM inventory WHERE sku='sku-a' FOR UPDATE")
            self.wait_for_lock(b.cid)
            a.query("UPDATE inventory SET available=0 WHERE sku='sku-a'; INSERT INTO orders VALUES ('la','locking','la','sku-a',1,'reserved',1); COMMIT")
            require(b.receive() == ["0"], "contract violated")
            b.query("ROLLBACK")
            self.inventory_check()
            a.close(); b.close()
            return {"locked_read_values": [1, 0]}
        self.ev.case("D1.locking_read", locking)

        def snapshot():
            self.reset(1)
            a = self.session("snapshot")
            a.query("START TRANSACTION")
            require(a.query("SELECT available FROM inventory WHERE sku='sku-a'") == ["1"], "contract violated")
            self.db.query("UPDATE inventory SET available=0 WHERE sku='sku-a'")
            require(a.query("SELECT available FROM inventory WHERE sku='sku-a'") == ["1"], "contract violated")
            require(a.query("SELECT available FROM inventory WHERE sku='sku-a' FOR UPDATE") == ["0"], "contract violated")
            a.query("ROLLBACK"); a.close()
            return {"repeatable_read_snapshot": 1, "locking_read": 0}
        self.ev.case("D1.snapshot_vs_current", snapshot)

        def deadlock():
            self.reset(1)
            a, b = self.session("deadlock-a"), self.session("deadlock-b")
            a.query("START TRANSACTION; SELECT available FROM inventory WHERE sku='sku-a' FOR UPDATE")
            b.query("START TRANSACTION; SELECT available FROM inventory WHERE sku='sku-b' FOR UPDATE")
            a.send("SELECT available FROM inventory WHERE sku='sku-b' FOR UPDATE")
            self.wait_for_lock(a.cid)
            b.send("SELECT available FROM inventory WHERE sku='sku-a' FOR UPDATE")
            ra, rb = a.receive(allow_error=True), b.receive(allow_error=True)
            require((only_sql_error(ra, 1213) and rb == ["1"]) or (only_sql_error(rb, 1213) and ra == ["1"]), (ra, rb))
            a.query("ROLLBACK"); b.query("ROLLBACK")
            self.db.query("SHOW ENGINE INNODB STATUS")
            a.close(); b.close()
            return {"deadlock_victims": 1, "victim_identity_not_assumed": True}
        self.ev.case("D1.deadlock_cycle", deadlock)

    def d2(self):
        def same_key():
            self.reset()
            a, b = self.session("idem-a"), self.session("idem-b")
            self.begin_operation(a, "shared", "same")
            b.query("START TRANSACTION")
            b.send(f"INSERT INTO operations(scope,idem_key,request_hash,status) VALUES ({q(SCOPE)},'shared',{q(canonical_hash('same',1))},'pending')")
            self.wait_for_lock(b.cid)
            first = self.finish_operation(a, "shared", "same")
            result = b.receive(allow_error=True)
            require(only_sql_error(result, 1062), result)
            b.query("ROLLBACK")
            replay = self.create("shared", "same")
            require(replay == first, "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM orders") == "1", "contract violated")
            require(self.scalar("SELECT available FROM inventory WHERE sku='sku-a'") == "9", "contract violated")
            a.close(); b.close()
            return {"orders": 1, "available": 9, "same_saved_result": True}
        self.ev.case("D2.concurrent_same_key", same_key)

        def conflict():
            self.reset(); self.create("key", "conflict")
            try:
                self.create("key", "conflict", 2)
            except Conflict:
                pass
            else:
                raise AssertionError("different payload was accepted")
            self.inventory_check()
            require(self.scalar("SELECT available FROM inventory WHERE sku='sku-a'") == "9", "contract violated")
            return {"conflict_before_second_effect": True}
        self.ev.case("D2.payload_conflict", conflict)

        def precommit():
            self.reset()
            self.expect_unknown(lambda: self.create("before", "before", fault="before_commit"))
            require(self.scalar("SELECT COUNT(*) FROM orders") == "0", "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM operations") == "0", "contract violated")
            require(self.scalar("SELECT available FROM inventory WHERE sku='sku-a'") == "10", "contract violated")
            self.create("before", "before")
            self.inventory_check()
            return {"rolled_back_rows": True, "retry_orders": 1}
        self.ev.case("D2.before_commit_disconnect", precommit)

        def postcommit():
            self.reset()
            self.expect_unknown(lambda: self.create("after", "after", fault="after_commit"))
            result = self.create("after", "after")
            require(result["order_id"] == "ord-after", "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM orders") == "1", "contract violated")
            self.inventory_check()
            return {"adapter_lost_response": True, "orders": 1}
        self.ev.case("D2.after_commit_response_lost", postcommit)

        def retention():
            self.reset(); self.create("expired", "stable")
            self.db.query("DELETE FROM operations")
            try:
                self.create("expired", "stable")
            except SqlError as error:
                require(only_sql_error(error.lines, 1062), error.lines)
            else:
                raise AssertionError("stable business identity failed to block duplicate")
            require(self.scalar("SELECT available FROM inventory WHERE sku='sku-a'") == "9", "contract violated")
            # Distinct business identity is a distinct operation after retention.
            self.create("expired", "fresh-generated-id")
            require(self.scalar("SELECT COUNT(*) FROM orders") == "2", "contract violated")
            self.inventory_check()
            return {"stable_identity_blocks_repeat": True, "expired_key_with_new_identity_orders": 2}
        self.ev.case("D2.retention_boundary", retention)

        def rejected():
            self.reset(0)
            result = self.create("sold-out", "sold-out")
            self.db.query("UPDATE inventory SET initial_qty=1,available=1 WHERE sku='sku-a'")
            require(self.create("sold-out", "sold-out") == result, "contract violated")
            require(result["status"] == "rejected", "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM orders") == "0", "contract violated")
            return {"terminal_rejection_not_recomputed": True}
        self.ev.case("D2.saved_rejection", rejected)

    def receipts(self):
        return [int(x) for x in self.db.query("SELECT receipt_id FROM delivery_receipts ORDER BY receipt_id")]

    def d3(self):
        def business_commit():
            self.reset(); self.create("committed", "committed")
            require(self.scalar("SELECT COUNT(*) FROM outbox WHERE sent=0") == "1", "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM delivery_receipts") == "0", "contract violated")
            self.relay(); self.consume(self.receipts()[0])
            require(self.scalar("SELECT COUNT(*) FROM order_projection") == "1", "contract violated")
            return {"durable_outbox_survives_absent_relay": True}
        self.ev.case("D3.business_commit_before_relay", business_commit)

        def publish_window():
            self.reset(); self.create("publish", "publish")
            self.expect_unknown(lambda: self.relay("after_publish"))
            self.relay()
            require(len(self.receipts()) == 2, "contract violated")
            require([self.consume(r) for r in self.receipts()] == ["applied", "duplicate"], "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM effect_log") == "1", "contract violated")
            return {"deliveries": 2, "effects": 1, "backend": "controlled_receiver_not_broker"}
        self.ev.case("D3.publish_before_mark", publish_window)

        for fault in ("before_commit", "after_commit"):
            def consumer_window(fault=fault):
                self.reset(); self.create(fault, fault); self.relay()
                receipt = self.receipts()[0]
                self.expect_unknown(lambda: self.consume(receipt, fault))
                expected_before = "0" if fault == "before_commit" else "1"
                require(self.scalar("SELECT COUNT(*) FROM consumer_dedup") == expected_before, "contract violated")
                require(self.scalar("SELECT COUNT(*) FROM effect_log") == expected_before, "contract violated")
                require(self.consume(receipt) == ("applied" if fault == "before_commit" else "duplicate"), "contract violated")
                require(self.scalar("SELECT COUNT(*) FROM effect_log") == "1", "contract violated")
                return {"fault": fault, "effects_after_replay": 1}
            self.ev.case("D3.consumer_" + fault, consumer_window)

        def wrong_dedup():
            self.reset(); self.create("wrong", "wrong"); event = self.relay(); receipt = self.receipts()[0]
            # Deliberately broken implementation commits dedup before its effect.
            self.db.query(f"INSERT INTO consumer_dedup VALUES ('orders-v1',{q(event)})")
            require(self.consume(receipt) == "duplicate", "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM order_projection") == "0", "contract violated")
            return {"negative_control_detected": True, "dedup_without_effect": 1}
        self.ev.case("D3.split_commit_negative_control", wrong_dedup)

    def d4(self):
        def refill_race():
            self.reset(); self.create("cache", "cache")
            old = self.db.query("SELECT version,state FROM orders WHERE order_id='ord-cache'")[0]
            self.db.query("UPDATE orders SET version=2 WHERE order_id='ord-cache'")
            floor, key = self.keys("ord-cache")
            self.redis("DEL", key)  # Plain cache-aside invalidation.
            self.redis("SET", key, old, "PX", 60000)  # Paused reader resumes last.
            require(self.redis("GET", key) == "1\treserved", "contract violated")
            require(self.scalar("SELECT version FROM orders WHERE order_id='ord-cache'") == "2", "contract violated")
            return {"negative_control_detected": True, "db_version": 2, "cache_version": 1}
        self.ev.case("D4.stale_refill", refill_race)

        def version_guard():
            self.reset(); floor, key = self.keys("guard")
            require(self.cache_fill("guard", 1, "v1") == 1, "contract violated")
            require(self.invalidate("guard", 2) == 1, "contract violated")
            require(self.cache_fill("guard", 1, "late-v1") == 0, "contract violated")
            require(self.redis("GET", key) == "", "contract violated")
            require(self.cache_fill("guard", 2, "v2") == 1, "contract violated")
            require(self.cache_fill("guard", 1, "late-v1-again") == 0, "contract violated")
            require(self.redis("GET", key) == "v2", "contract violated")
            return {"stale_versions_rejected": 2, "retained_floor": self.redis("GET", floor)}
        self.ev.case("D4.version_watermark", version_guard)

        def invalidation_failure():
            self.reset(); self.create("lost-invalidation", "lost-invalidation")
            require(self.cache_fill("ord-lost-invalidation", 1, "v1", 60000) == 1, "contract violated")
            self.db.query("UPDATE orders SET version=2 WHERE order_id='ord-lost-invalidation'")
            # Fault injection suppresses command delivery; not a Redis failover test.
            _, key = self.keys("ord-lost-invalidation")
            require(self.redis("GET", key) == "v1", "contract violated")
            self.invalidate("ord-lost-invalidation", 2)
            require(self.redis("GET", key) == "", "contract violated")
            return {"lost_command_leaves_stale_cache": True, "retry_invalidates": True}
        self.ev.case("D4.invalidation_delivery_loss", invalidation_failure)

        def expiry():
            self.reset(); floor, key = self.keys("expire")
            self.cache_fill("expire", 2, "v2", 300)
            deadline = time.monotonic() + 5
            while self.redis("EXISTS", key) == "1":
                require(time.monotonic() < deadline, "TTL expiry not observed")
                time.sleep(0.02)
            require(self.redis("GET", floor) == "2", "contract violated")
            require(self.cache_fill("expire", 1, "late") == 0, "contract violated")
            # Deliberately delete watermark: model eviction/lost state, not a
            # real failover claim. An old request becomes admissible again.
            self.redis("DEL", floor)
            require(self.cache_fill("expire", 1, "late") == 1, "contract violated")
            return {"value_expired": True, "watermark_loss_weakens_guarantee": True}
        self.ev.case("D4.expiry_and_watermark_loss", expiry)

        def concurrent_fill():
            self.reset(); self.invalidate("concurrent", 2)
            gate, failures, results = threading.Barrier(3), [], []
            def worker(version):
                try:
                    gate.wait(timeout=5)
                    results.append((version, self.cache_fill("concurrent", version, f"v{version}")))
                except BaseException as error:
                    failures.append(error)
            threads = [threading.Thread(target=worker, args=(v,)) for v in (1, 2)]
            for t in threads: t.start()
            gate.wait(timeout=5)
            for t in threads: t.join(timeout=12)
            require(all(not t.is_alive() for t in threads), "contract violated")
            require(not failures, failures)
            require(sorted(results) == [(1, 0), (2, 1)], results)
            require(self.redis("GET", self.keys("concurrent")[1]) == "v2", "contract violated")
            return {"concurrent_results": sorted(results), "final": "v2"}
        self.ev.case("D4.concurrent_fill_after_floor", concurrent_fill)

    def reconcile(self):
        queries = [x.strip() for x in (ROOT / "sql/reconcile.sql").read_text().split(";") if x.strip()]
        violations = {f"invariant_{i+1}": self.db.query(query) for i, query in enumerate(queries)}
        self.ev.log("reconciliation", violations=violations)
        return violations

    def d5(self):
        def recovery():
            self.reset(3)
            a, b = self.session("capstone-a"), self.session("capstone-b")
            self.begin_operation(a, "capstone", "capstone")
            b.query("START TRANSACTION")
            b.send(f"INSERT INTO operations(scope,idem_key,request_hash,status) VALUES ({q(SCOPE)},'capstone',{q(canonical_hash('capstone',1))},'pending')")
            self.wait_for_lock(b.cid)
            self.expect_unknown(lambda: self.finish_operation(a, "capstone", "capstone", fault="after_commit"))
            require(only_sql_error(b.receive(allow_error=True), 1062), "duplicate-key arbitration required")
            b.query("ROLLBACK"); a.close(); b.close()
            first = self.create("capstone", "capstone")
            require(first["order_id"] == "ord-capstone", "contract violated")
            self.cache_fill("ord-capstone", 0, "not-found-v0", 60000)
            self.expect_unknown(lambda: self.relay("after_publish"))
            require(any(self.reconcile().values()), "Missing consumer should be visible as lag")
            self.relay()
            receipts = self.receipts()
            self.expect_unknown(lambda: self.consume(receipts[0], "before_commit"))
            require(self.consume(receipts[0]) == "applied", "contract violated")
            require(self.consume(receipts[1]) == "duplicate", "contract violated")
            _, key = self.keys("ord-capstone")
            require(self.redis("GET", key) == "not-found-v0", "contract violated")
            self.invalidate("ord-capstone", 1)
            require(self.cache_fill("ord-capstone", 0, "late-not-found") == 0, "contract violated")
            require(self.cache_fill("ord-capstone", 1, "reserved-v1") == 1, "contract violated")
            require(not any(self.reconcile().values()), "contract violated")
            for receipt in receipts:
                require(self.consume(receipt) == "duplicate", "contract violated")
            require(self.scalar("SELECT COUNT(*) FROM effect_log") == "1", "contract violated")
            require(self.scalar("SELECT available FROM inventory WHERE sku='sku-a'") == "2", "contract violated")
            orders = int(self.scalar("SELECT COUNT(*) FROM orders"))
            deliveries = int(self.scalar("SELECT COUNT(*) FROM delivery_receipts"))
            require(orders == 1 and deliveries == 2, {"orders": orders, "deliveries": deliveries})
            return {"orders": orders, "available": 2, "deliveries": deliveries, "effects": 1, "all_reconciliation_queries_empty": True}
        self.ev.case("D5.six_failure_recovery", recovery)

        def migration():
            self.reset(); self.create("migration", "migration"); self.relay()
            old_receipt = self.receipts()[0]
            payload = {"schema_version": 2, "order_id": "ord-migration", "quantity": 1,
                       "state": "reserved", "version": 2, "state_reason": "confirmed_by_migration"}
            self.db.query(f"INSERT INTO delivery_receipts(event_id,payload) VALUES ('evt-migration-v2',{q(json.dumps(payload))})")
            new_receipt = self.receipts()[-1]
            require(self.consume(new_receipt) == "applied", "contract violated")
            require(self.consume(old_receipt) == "applied", "contract violated")
            require(self.scalar("SELECT version FROM order_projection WHERE order_id='ord-migration'") == "2", "contract violated")
            require(self.consume(new_receipt) == "duplicate", "contract violated")
            return {"schema_versions_accepted": [1, 2], "out_of_order_snapshot_did_not_regress": True,
                    "scope": "full_snapshot_projection_only_no_external_effect"}
        self.ev.case("D5.schema_v2_backwards_compatible_snapshot", migration)

    def close(self):
        for session in reversed(self.sessions):
            session.close()


def main():
    if sys.flags.optimize:
        raise RuntimeError("Optimized Python is forbidden for this evidence harness")
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql", required=True)
    parser.add_argument("--redis", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--chapter", choices=["all", "d1", "d2", "d3", "d4", "d5"], default="all")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-f0-9]{32}", args.owner):
        raise ValueError("Invalid run owner")
    args.out.mkdir(parents=True, exist_ok=True)
    evidence, lab = Evidence(args.out), None
    report = {"status": "FAIL", "scope": "real_mysql_redis_single_node_controlled_delivery_receiver",
              "chapter": args.chapter, "production_or_real_broker_verified": False}
    try:
        lab = Lab(args, evidence)
        server = lab.db.query("SELECT VERSION(),@@transaction_isolation,@@autocommit,@@default_storage_engine")
        redis_version = lab.redis("INFO", "server")
        versions = dict(line.split("=", 1) for line in (ROOT / "infra/versions.env").read_text().splitlines() if line and not line.startswith("#"))
        mysql_patch = versions["MYSQL_IMAGE"].split(":", 1)[1]
        redis_patch = versions["REDIS_IMAGE"].split(":", 1)[1].split("-", 1)[0]
        require(server == [mysql_patch + "\tREPEATABLE-READ\t1\tInnoDB"], server)
        redis_fields = dict(line.split(":", 1) for line in redis_version.splitlines() if ":" in line and not line.startswith("#"))
        require(redis_fields.get("redis_version") == redis_patch, redis_version)
        report["environment"] = {"mysql": server, "redis_server": redis_version, "images": versions}
        lab.db.query("SHOW CREATE TABLE inventory; SHOW CREATE TABLE orders; EXPLAIN SELECT * FROM inventory WHERE sku='sku-a' FOR UPDATE")
        chapters = ["d1", "d2", "d3", "d4", "d5"] if args.chapter == "all" else [args.chapter]
        for chapter in chapters:
            getattr(lab, chapter)()
        expected = [name for chapter in chapters for name in EXPECTED_CASES[chapter]]
        actual = [record["case"] for record in evidence.records]
        require(actual == expected, {"expected": expected, "actual": actual})
        require(all(record["status"] == "PASS" for record in evidence.records), "non-pass case")
        require(bool(actual), "empty case inventory")
        report["expected_cases"] = expected
        report["status"] = "PASS"
    except BaseException as error:
        report["error"] = repr(error)
        (args.out / "exception.txt").write_text(traceback.format_exc())
        if lab:
            try:
                lab.db.query("SHOW ENGINE INNODB STATUS")
            except BaseException as diagnostics_error:
                evidence.log("diagnostics_failed", error=repr(diagnostics_error))
        raise
    finally:
        if lab:
            lab.close()
        report["cases"] = evidence.records
        report["source_sha256"] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in sorted(ROOT.rglob("*")) if path.is_file()
                                   and not any(part in ("results", "__pycache__") for part in path.relative_to(ROOT).parts)}
        (args.out / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"{len(evidence.records)} real-service cases passed; evidence capture and cleanup pending; receiver is NOT a real broker")


if __name__ == "__main__":
    main()
