"""Original finite decision model. NOT an authentication or cryptographic library.

Precondition: trusted adapters have verified credentials/cryptography and mapped
issuer+subject to an internal actor. Objects below are fixtures, NOT proof that a
caller is authenticated. No wire parser, cookies, keys, token issuer or network.
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TrustedIdentity:
    actor: str


@dataclass(frozen=True)
class VerifiedClaims:
    issuer: str
    subject: str
    audience: frozenset[str]
    purpose: str
    not_before: int
    expires: int
    token_id: str


def snapshot_accepts(claims, now):
    """After trusted cryptographic verification; fixed teaching profile, no skew."""
    return (
        claims.issuer == "issuer-A"
        and bool(claims.subject)
        and "orders-api" in claims.audience
        and claims.purpose == "access"
        and claims.not_before <= now < claims.expires
    )


@dataclass(frozen=True)
class SessionRecord:
    actor: str
    expires: int
    revoked: bool = False


def session_accepts(record, now):
    """record is a trusted lookup result; opaque handle verification is excluded."""
    return record is not None and not record.revoked and now < record.expires


def online_accepts(claims, now, revoked):
    return snapshot_accepts(claims, now) and claims.token_id not in revoked


@dataclass(frozen=True)
class ActiveCache:
    active: bool
    observed_at: int
    valid_until: int


def cache_accepts(claims, cache, now):
    """One fixture token per cache; real caches must key all security context."""
    return (snapshot_accepts(claims, now) and cache.active
            and cache.observed_at <= now < cache.valid_until)


@dataclass(frozen=True)
class Order:
    tenant: str
    order_id: str
    owner: str
    ownership_epoch: int = 1
    revision: int = 1
    note: str = "original"


@dataclass(frozen=True)
class Grant:
    grant_id: str
    tenant: str
    order_id: str
    grantor: str
    delegate: str
    actions: frozenset[str]
    expires: int
    ownership_epoch: int = 1
    revoked: bool = False


@dataclass(frozen=True)
class Request:
    tenant: str
    order_id: str
    action: str


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    grant_id: str | None = None


def decide(identity, request, order, memberships, grants, now):
    """All facts except Request are trusted current server-side inputs.

    Fixture policy: owners may read/update notes; delegates may only read.
    Tenant and object ID come from the request and never establish permission.
    """
    if identity is None or not identity.actor:
        return Decision(False, "identity-required")
    if request.action not in {"read", "update-note"}:
        return Decision(False, "unknown-action")
    if (order is None or (order.tenant, order.order_id)
            != (request.tenant, request.order_id)):
        return Decision(False, "object-scope")
    if (order.tenant, identity.actor) not in memberships:
        return Decision(False, "tenant-membership")
    if identity.actor == order.owner:
        return Decision(True, "owner")
    for grant in grants:
        if (
            not grant.revoked and now < grant.expires
            and (grant.tenant, grant.order_id) == (order.tenant, order.order_id)
            and grant.delegate == identity.actor
            and grant.grantor == order.owner
            and (order.tenant, grant.grantor) in memberships
            and grant.ownership_epoch == order.ownership_epoch
            and request.action == "read" and request.action in grant.actions
        ):
            return Decision(True, "delegated-read", grant.grant_id)
    return Decision(False, "no-object-permission")


@dataclass(frozen=True)
class PreparedUpdate:
    actor: str
    request: Request
    revision: int
    note: str


class Store:
    """Sequential in-memory model: commit check and effect are assumed atomic.

    Does not implement a DB transaction, row lock, durable audit or HTTP status.
    Authentication must be fresh enough under the application's revocation policy.
    """
    def __init__(self, orders, memberships, grants=()):
        self.orders = {(o.tenant, o.order_id): o for o in orders}
        self.memberships = set(memberships)
        self.grants = tuple(grants)
        self.effects = []

    def read(self, identity, request, now, policy=decide):
        if request.action != "read":
            return Decision(False, "wrong-operation"), None
        order = self.orders.get((request.tenant, request.order_id))
        decision = policy(identity, request, order, self.memberships, self.grants, now)
        return (decision, order.note if decision.allowed else None)

    def prepare_update(self, identity, request, note, now, policy=decide):
        if request.action != "update-note":
            return None
        order = self.orders.get((request.tenant, request.order_id))
        decision = policy(identity, request, order, self.memberships, self.grants, now)
        if not decision.allowed:
            return None
        return PreparedUpdate(identity.actor, request, order.revision, note)

    def commit_update(self, identity, prepared, now):
        if prepared is None or identity is None or prepared.actor != identity.actor:
            return Decision(False, "invalid-preparation")
        request = prepared.request
        if request.action != "update-note":
            return Decision(False, "wrong-operation")
        order = self.orders.get((request.tenant, request.order_id))
        if order is None or order.revision != prepared.revision:
            return Decision(False, "stale-object")
        decision = decide(identity, request, order, self.memberships, self.grants, now)
        if not decision.allowed:
            return decision
        self.orders[(order.tenant, order.order_id)] = replace(
            order, revision=order.revision + 1, note=prepared.note)
        self.effects.append((identity.actor, order.tenant, order.order_id, "note-updated"))
        return decision

    def transfer_fixture(self, tenant, order_id, new_owner):
        """Trusted test event, NOT a public ownership-transfer endpoint."""
        order = self.orders[(tenant, order_id)]
        self.orders[(tenant, order_id)] = replace(
            order, owner=new_owner, ownership_epoch=order.ownership_epoch + 1,
            revision=order.revision + 1)


def fixture():
    return Store(
        [Order("red", "o1", "alice"), Order("red", "o2", "bob"),
         Order("blue", "o1", "mallory")],
        {("red", "alice"), ("red", "bob"), ("red", "carol"),
         ("blue", "mallory")},
        [Grant("g1", "red", "o1", "alice", "carol", frozenset({"read"}), 20)],
    )
