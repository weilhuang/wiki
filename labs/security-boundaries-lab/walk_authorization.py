from model import Request, TrustedIdentity, fixture

store = fixture()
carol = TrustedIdentity("carol")
read = Request("red", "o1", "read")
decision, payload = store.read(carol, read, now=10)
print("delegate read:", decision.reason, payload)

alice = TrustedIdentity("alice")
update = Request("red", "o1", "update-note")
prepared = store.prepare_update(alice, update, "new-note", now=10)
store.transfer_fixture("red", "o1", "bob")
result = store.commit_update(alice, prepared, now=11)
print("old approval:", result.reason, store.effects)

decision, payload = store.read(carol, read, now=11)
print("old grant:", decision.reason, payload)
decision, payload = store.read(TrustedIdentity("bob"), read, now=11)
print("new owner:", decision.reason, payload)
