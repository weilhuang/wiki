from review_model import ReviewModel

model = ReviewModel()
print(model.cancel("alice", "red", "o1", "c1", 1, mode="async"))
event = "red/o1/cancel/2"
print(model.state["orders"]["red/o1"]["status"])
print(model.release(event, 7, fault="after-release"))
print(model.state["releaseEffects"])

print(model.release(event, 8))
print(model.state["releaseEffects"])
print(model.confirm(event))
print(model.cancel("alice", "red", "o1", "c1", 1, mode="async"))
print(model.rollback_allowed())
