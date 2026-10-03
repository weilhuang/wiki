"""Finite sequential application/router model, NOT Kubernetes execution.

Logical integer time is supplied by the caller. No threads, sleeps, network,
signals, persistence, kubelet, load balancer, HTTP implementation or scheduler.
"""
from dataclasses import dataclass, field


def endpoint_conditions(pod_ready, terminating, publish_not_ready=False,
                        variant="correct"):
    # Original restatement of v1.34.0 podToEndpoint's three-condition relation.
    if variant == "ignore-terminating":
        ready = publish_not_ready or pod_ready
    elif variant == "ignore-publish-exception":
        ready = pod_ready and not terminating
    else:
        ready = publish_not_ready or (pod_ready and not terminating)
    return {"ready": ready, "serving": pod_ready, "terminating": terminating}


@dataclass
class Process:
    variant: str = "correct"
    started: bool = False
    ready: bool = False
    accepting: bool = False
    terminating: bool = False
    router_has_endpoint: bool = False
    endpoint: dict = field(default_factory=lambda: endpoint_conditions(False, False))
    active: set = field(default_factory=set)
    completed: list = field(default_factory=list)
    rejected: list = field(default_factory=list)
    uncertain: list = field(default_factory=list)
    dependency_open: bool = True
    close_count: int = 0
    deadline: int | None = None
    grace: int | None = None
    exited: bool = False
    forced: bool = False
    last_time: int = -1

    def tick(self, now):
        if now < self.last_time:
            raise ValueError("logical time must not decrease")
        self.last_time = now

    def startup_complete(self):
        if self.terminating or self.exited:
            raise ValueError("cannot start a terminating/exited model")
        self.started = self.ready = self.accepting = True
        self.endpoint = endpoint_conditions(True, False)
        self.router_has_endpoint = True

    def delete(self, now, grace):
        self.tick(now)
        if grace <= 0:
            raise ValueError("this model only covers positive graceful periods")
        if not self.terminating:
            self.terminating = True
            self.deadline, self.grace = now + grace, grace

    def publish_endpoint(self):
        self.endpoint = endpoint_conditions(self.ready, self.terminating)
        if self.variant == "instant-propagation":
            self.router_has_endpoint = self.endpoint["ready"]

    def refresh_router(self):
        # Only ordinary ready-based routing. Local fallback is source-reviewed.
        self.router_has_endpoint = self.endpoint["ready"]

    def stop_admission(self):
        self.ready = False
        self.accepting = (not self.accepting if self.variant == "toggle-gate"
                          else False)

    def admit(self, request_id, *, existing_connection=False):
        if self.exited:
            return "process-gone"
        if not existing_connection and not self.router_has_endpoint:
            return "not-routed"
        if not self.accepting:
            self.rejected.append(request_id)
            return "rejected"
        if request_id in self.active or request_id in self.completed:
            raise ValueError("fixture request identity reused")
        self.active.add(request_id)
        return "accepted"

    def finish(self, request_id):
        if self.exited or request_id not in self.active:
            return "not-active"
        self.active.remove(request_id)
        if not self.dependency_open:
            self.uncertain.append(request_id)
            return "dependency-closed"
        self.completed.append(request_id)
        return "completed"

    def close_dependency(self):
        if self.active and self.variant != "early-close":
            return "busy"
        if self.dependency_open or self.variant == "double-close":
            self.dependency_open = False
            self.close_count += 1
        return "closed"

    def hook_finished(self, now):
        self.tick(now)
        if self.variant == "restart-grace":
            self.deadline = now + self.grace

    def expire(self, now):
        self.tick(now)
        if self.deadline is None or now < self.deadline or self.exited:
            return "not-expired"
        self.forced = True
        self.uncertain.extend(sorted(self.active))
        self.active.clear()
        self.accepting = False
        self.exited = True
        return "clean" if self.variant == "force-is-clean" else "forced"

    def exit_clean(self):
        if self.active or self.accepting or self.dependency_open or self.forced:
            return "blocked"
        self.exited = True
        return "clean"
