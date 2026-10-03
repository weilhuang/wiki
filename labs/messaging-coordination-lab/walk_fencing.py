from protocol_model import Authority, Resource

authority = Authority()
old = authority.acquire("shop-a/order-7:g1", "worker-A")
authority.advance(5)
new = authority.acquire(old.scope, "worker-B")
resource = Resource(authority)

first = resource.write("worker-B", new, new.scope, "op-1", 5)
resource = Resource(authority, resource.store.restart())
replay = resource.write("worker-B", new, new.scope, "op-1", 5)
second = resource.write("worker-B", new, new.scope, "op-2", 7)
before = resource.store.committed
stale = resource.write("worker-A", old, old.scope, "late", 99)

assert first == {"status": "applied", "value": 5}
assert replay == {"status": "replayed", "value": 5}
assert second == {"status": "applied", "value": 12}
assert stale == {"status": "stale"}
assert resource.store.committed == before
assert len(resource.store.read()["effects"]) == 2
print({"token": new.token, "replay": replay, "second": second, "old": stale})
