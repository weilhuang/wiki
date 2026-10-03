"""Deliberately unsafe policy variants. Never use in applications."""
from dataclasses import replace
from model import Decision, decide

NAMES = ("tenant-from-request", "tenant-member-is-owner", "default-allow",
         "missing-identity-allowed", "delegation-expands-action", "ignore-delegate",
         "ignore-grant-expiry", "ignore-grant-revocation", "ignore-ownership-epoch",
         "ignore-object-id", "cached-allow-after-transfer")


def policy_for(name):
    def policy(identity, request, order, memberships, grants, now):
        if name == "tenant-from-request" and identity:
            memberships = memberships | {(request.tenant, identity.actor)}
        elif name == "tenant-member-is-owner" and identity and order:
            if (order.tenant, identity.actor) in memberships:
                return Decision(True, "mutant-member")
        elif name == "default-allow" and request.action not in {"read", "update-note"}:
            return Decision(True, "mutant-default")
        elif name == "missing-identity-allowed" and identity is None:
            return Decision(True, "mutant-anonymous")
        elif name == "delegation-expands-action" and request.action == "update-note":
            request = replace(request, action="read")
        elif name == "ignore-delegate" and identity:
            grants = tuple(replace(g, delegate=identity.actor) for g in grants)
        elif name == "ignore-grant-expiry":
            grants = tuple(replace(g, expires=now + 1) for g in grants)
        elif name == "ignore-grant-revocation":
            grants = tuple(replace(g, revoked=False) for g in grants)
        elif name == "ignore-ownership-epoch" and order:
            grants = tuple(replace(g, ownership_epoch=order.ownership_epoch) for g in grants)
        elif name == "ignore-object-id" and order:
            request = replace(request, tenant=order.tenant, order_id=order.order_id)
        return decide(identity, request, order, memberships, grants, now)
    return policy


def unsafe_cached_commit(store, prepared):
    """Uses old approval after object ownership changed; actual wrong write."""
    order = store.orders[(prepared.request.tenant, prepared.request.order_id)]
    store.orders[(order.tenant, order.order_id)] = replace(
        order, note=prepared.note, revision=order.revision + 1)
    store.effects.append((prepared.actor, order.tenant, order.order_id, "note-updated"))
    return Decision(True, "mutant-cached-allow")
