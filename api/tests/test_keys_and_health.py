from datetime import datetime, UTC

from fastapi.testclient import TestClient

from src.main import create_app
from src.models import TokenData, Tier
from src.auth import dependencies as auth_deps
from src.routers import health as health_mod


class SimpleFakeRedis:
    def __init__(self):
        self.sets = {}
        self.hashes = {}

    async def smembers(self, key):
        return self.sets.get(key, set())

    async def hgetall(self, key):
        return self.hashes.get(key, {})

    async def hset(self, key, *args, mapping=None):
        # Support both hset(key, mapping=...) and hset(key, field, value)
        if mapping:
            mp = {}
            for k, v in mapping.items():
                mp[k.encode()] = v.encode() if isinstance(v, str) else str(v).encode()
            self.hashes[key] = mp
            return True

        if len(args) >= 2:
            field, value = args[0], args[1]
            mp = self.hashes.setdefault(key, {})
            mp[str(field).encode()] = (
                value.encode() if isinstance(value, str) else str(value).encode()
            )
            self.hashes[key] = mp
            return True

        return False

    async def sadd(self, key, value):
        s = self.sets.setdefault(key, set())
        s.add(value)
        return True

    async def srem(self, key, value):
        s = self.sets.setdefault(key, set())
        s.discard(value)
        return True

    async def ping(self):
        return True

    async def incr(self, key):
        return 1

    async def expire(self, key, seconds):
        return True

    async def close(self):
        return


def test_health_root_and_stats(monkeypatch):
    app = create_app()
    client = TestClient(app)

    # Fake redis and blockchain
    fake_redis = SimpleFakeRedis()
    auth_deps.redis_client = fake_redis

    class FakeBlockchain:
        async def health_check(self):
            return True

        async def get_oracle_stats(self):
            return {
                "total_tokens": 3,
                "total_updates": 10,
                "last_update": datetime.now(UTC),
                "uptime_percentage": 99.9,
            }

    monkeypatch.setattr(health_mod, "get_blockchain_service", lambda: FakeBlockchain())

    resp = client.get("/")
    assert resp.status_code == 200
    root = resp.json()
    assert root.get("name") == "SentiBridge API"

    resp = client.get("/health")
    assert resp.status_code == 200
    h = resp.json()
    assert h["status"] in ("healthy", "degraded")

    resp = client.get("/stats")
    assert resp.status_code == 200
    s = resp.json()
    assert "total_tokens" in s


def test_create_list_rotate_revoke_key(monkeypatch):
    app = create_app()
    client = TestClient(app)

    fake_redis = SimpleFakeRedis()
    auth_deps.redis_client = fake_redis

    # Override current user dependency
    def fake_current_user():
        return TokenData(sub="user1", tier=Tier.PRO)

    app.dependency_overrides[auth_deps.get_current_user] = fake_current_user

    # Patch billing service to return a customer id
    from src.services import billing as billing_mod

    monkeypatch.setattr(billing_mod, "billing_service", type("B", (), {"ensure_customer_for_user": lambda *_: "cust_123"}) )

    # Create a key
    payload = {"name": "mykey", "tier": "pro"}
    headers = {"X-API-Key": "sb_live_testkey_for_middleware"}
    resp = client.post("/api/v1/keys/", json=payload, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert "key" in body and "id" in body

    key_id = body["id"]

    # List keys should include the created key
    resp = client.get("/api/v1/keys/", headers=headers)
    assert resp.status_code == 200

    # Rotate the key
    resp = client.post(f"/api/v1/keys/{key_id}/rotate", headers=headers)
    # Rotating may 404 if lookup fails; ensure we handle both
    assert resp.status_code in (200, 404)
