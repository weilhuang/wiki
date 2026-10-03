from lifecycle import Process

p = Process()
p.startup_complete()
assert p.admit("old") == "accepted"
p.delete(now=0, grace=10)
p.publish_endpoint()
assert not p.endpoint["ready"] and p.router_has_endpoint
p.stop_admission()
assert p.admit("late") == "rejected"
p.refresh_router()
assert p.admit("new") == "not-routed"
assert p.finish("old") == "completed"
assert p.close_dependency() == "closed"
assert p.exit_clean() == "clean"
print({"completed": p.completed, "rejected": p.rejected,
       "close_count": p.close_count, "forced": p.forced})
