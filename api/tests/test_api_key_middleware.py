import json
from datetime import datetime

from fastapi.testclient import TestClient

from src.main import app
from src.auth import dependencies
from src.auth.jwt import hash_api_key


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def incr(self, key):
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    async def expire(self, key, seconds):
        # noop for test
        return True

    async def close(self):
        return


def test_missing_api_key_is_rejected():
    client = TestClient(app)
    resp = client.get("/api/v1/sentiment/current/FOO")
    assert resp.status_code == 401
    data = resp.json()
    assert data.get("error") == "missing_api_key"


def test_usage_counter_increments_with_api_key():
    # Attach fake redis
    fake = FakeRedis()
    dependencies.redis_client = fake

    client = TestClient(app)
    test_key = "sb_live_testkey_for_middleware"
    headers = {"X-API-Key": test_key}

    resp = client.get("/api/v1/sentiment/current/FOO", headers=headers)

    # Request should pass through middleware; endpoint may 404 or return content
    assert resp.status_code in (200, 404, 422)

    # Check fake redis for usage key
    key_hash = hash_api_key(test_key)
    minute_key = f"usage:{key_hash}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"

    # increment should have been called at least once
    assert fake.store.get(minute_key, 0) >= 1
