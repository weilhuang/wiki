from protocol_model import Broker, Consumer, event

broker, consumer = Broker(), Consumer()
serial, confirmed = broker.publish(event())
delivery, message = broker.take(serial)
first = consumer.apply(message)
saved = consumer.store.read()
assert confirmed == "confirmed" and first == "applied"
assert len(saved["effects"]) == 1 and len(saved["inbox"]) == 1

broker.close_channel()
consumer = Consumer(consumer.store.restart())
broker = Broker(broker.store.restart(), channel="ch-2")
delivery, message = broker.take(serial)
second = consumer.apply(message)
assert second == "duplicate" and consumer.store.read() == saved
broker.settle(delivery)

assert broker.store.read()["records"][0]["attempts"] == 2
assert broker.store.read()["records"][0]["state"] == "done"
assert not broker.tags
print({"first": first, "replay": second, "total": saved["totals"],
       "effects": len(saved["effects"]), "deliveries": 2})
