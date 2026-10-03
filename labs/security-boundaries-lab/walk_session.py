from dataclasses import replace
from model import (ActiveCache, SessionRecord, VerifiedClaims, cache_accepts,
                   online_accepts, session_accepts, snapshot_accepts)

claims = VerifiedClaims("issuer-A", "alice", frozenset({"orders-api"}),
                        "access", 10, 20, "fixture-t1")
session = SessionRecord("alice", 20)
cache = ActiveCache(True, 11, min(11 + 5, claims.expires))

session = replace(session, revoked=True)
revoked = {claims.token_id}
print("t12 session:", session_accepts(session, 12))
print("t12 offline:", snapshot_accepts(claims, 12))
print("t12 online:", online_accepts(claims, 12, revoked))
print("t12 cached:", cache_accepts(claims, cache, 12))
print("t16 cached:", cache_accepts(claims, cache, 16))
print("t20 offline:", snapshot_accepts(claims, 20))
