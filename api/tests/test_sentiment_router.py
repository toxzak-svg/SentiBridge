import asyncio
from datetime import datetime, UTC

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.routers import sentiment as sentiment_mod
from src.models import TokenData, Tier
from src.auth import dependencies as auth_deps


def test_score_to_sentiment_thresholds():
    assert sentiment_mod.score_to_sentiment(8000) == "bullish"
    assert sentiment_mod.score_to_sentiment(6000) == "slightly_bullish"
    assert sentiment_mod.score_to_sentiment(5000) == "neutral"
    assert sentiment_mod.score_to_sentiment(3500) == "slightly_bearish"
    assert sentiment_mod.score_to_sentiment(1000) == "bearish"


def test_get_current_sentiment_endpoint(monkeypatch):
    app = create_app()
    client = TestClient(app)

    # Replace blockchain service with a fake that returns a known value
    class FakeBlockchain:
        async def initialize(self):
            return None

        async def get_latest_sentiment(self, token):
            return {"token": token, "score": 7200, "volume": 150, "timestamp": int(datetime.now(UTC).timestamp())}

    monkeypatch.setattr(sentiment_mod, "get_blockchain_service", lambda: FakeBlockchain())

    # Provide a fake redis client so middleware can record usage without error
    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def incr(self, key):
            self.store[key] = self.store.get(key, 0) + 1
            return self.store[key]

        async def expire(self, key, seconds):
            return True

        async def close(self):
            return

    auth_deps.redis_client = FakeRedis()

    # Override rate-limit dependency to return a valid user
    def fake_check_rate_limit():
        return TokenData(sub="tester", tier=Tier.PRO)

    app.dependency_overrides[auth_deps.check_rate_limit] = fake_check_rate_limit

    headers = {"X-API-Key": "sb_live_testkey_for_middleware"}
    resp = client.get("/api/v1/sentiment/current/FOO", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"] == "FOO"
    assert body["sentiment"] in ("bullish", "slightly_bullish", "neutral", "slightly_bearish", "bearish")


def test_get_batch_sentiment_limit_and_results(monkeypatch):
    app = create_app()
    client = TestClient(app)

    class FakeBlockchain:
        async def initialize(self):
            return None

        async def get_latest_sentiment(self, token):
            return {"token": token, "score": 5000, "volume": 10, "timestamp": int(datetime.now(UTC).timestamp())}

    monkeypatch.setattr(sentiment_mod, "get_blockchain_service", lambda: FakeBlockchain())

    # Return PRO tier allowing many tokens
    def fake_check_rate_limit():
        return TokenData(sub="tester", tier=Tier.PRO)

    app.dependency_overrides[auth_deps.check_rate_limit] = fake_check_rate_limit

    # Provide fake redis and API key header for middleware
    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def incr(self, key):
            self.store[key] = self.store.get(key, 0) + 1
            return self.store[key]

        async def expire(self, key, seconds):
            return True

        async def close(self):
            return

    auth_deps.redis_client = FakeRedis()

    # Request a small batch
    headers = {"X-API-Key": "sb_live_testkey_for_middleware"}
    resp = client.get("/api/v1/sentiment/batch?tokens=A, B, C", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "tokens" in body and isinstance(body["tokens"], list)


def test_get_current_not_found(monkeypatch):
    app = create_app()
    client = TestClient(app)

    class FakeBlockchain:
        async def initialize(self):
            return None

        async def get_latest_sentiment(self, token):
            return None

    monkeypatch.setattr(sentiment_mod, "get_blockchain_service", lambda: FakeBlockchain())

    auth_deps.redis_client = type("R", (), {"incr": (lambda *a, **k: 1), "expire": (lambda *a, **k: True)})()
    # Override both rate limit and current_user used by require_tier
    app.dependency_overrides[auth_deps.check_rate_limit] = lambda: TokenData(sub="tester", tier=Tier.PRO)
    app.dependency_overrides[auth_deps.get_current_user] = lambda: TokenData(sub="tester", tier=Tier.PRO)
    app.dependency_overrides[auth_deps.get_current_user] = lambda: TokenData(sub="tester", tier=Tier.PRO)

    headers = {"X-API-Key": "sb_live_testkey_for_middleware"}
    resp = client.get("/api/v1/sentiment/current/FOO", headers=headers)
    assert resp.status_code == 404


import pytest


@pytest.mark.asyncio
async def test_get_sentiment_history_and_trending(monkeypatch):
    app = create_app()
    client = TestClient(app)

    class FakeBlockchain:
        async def initialize(self):
            return None

        async def get_sentiment_history(self, token, from_timestamp=None):
            return [{"token_symbol": token, "score": 5000, "volume": 10, "timestamp": datetime.now(UTC), "block_number": None}]

        async def get_trending_tokens(self, limit=10):
            return [{"token": "T1", "score": 6000, "volume": 20, "timestamp": int(datetime.now(UTC).timestamp())}]

    monkeypatch.setattr(sentiment_mod, "get_blockchain_service", lambda: FakeBlockchain())

    # Provide fake redis and override tier requirement
    auth_deps.redis_client = type("R", (), {"incr": (lambda *a, **k: 1), "expire": (lambda *a, **k: True)})()
    app.dependency_overrides[auth_deps.check_rate_limit] = lambda: TokenData(sub="tester", tier=Tier.PRO)

    # Call handler functions directly to avoid middleware/dependency intricacies
    hist = await sentiment_mod.get_sentiment_history("FOO", TokenData(sub="tester", tier=Tier.PRO), hours=1)
    assert isinstance(hist, list) or hist is not None

    trending = await sentiment_mod.get_trending_tokens(TokenData(sub="tester", tier=Tier.PRO), limit=1)
    assert isinstance(trending, list)


def test_batch_too_many_tokens(monkeypatch):
    app = create_app()
    client = TestClient(app)

    class FakeBlockchain:
        async def initialize(self):
            return None

        async def get_latest_sentiment(self, token):
            return {"token": token, "score": 5000, "volume": 10, "timestamp": int(datetime.now(UTC).timestamp())}

    monkeypatch.setattr(sentiment_mod, "get_blockchain_service", lambda: FakeBlockchain())

    # Set user to FREE so token limit is 5 and we'll request >5 to trigger 400
    app.dependency_overrides[auth_deps.check_rate_limit] = lambda: TokenData(sub="tester", tier=Tier.FREE)
    auth_deps.redis_client = type("R", (), {"incr": (lambda *a, **k: 1), "expire": (lambda *a, **k: True)})()

    headers = {"X-API-Key": "sb_live_testkey_for_middleware"}
    # Build query string with repeated tokens to ensure FastAPI parses as list
    qs = "?" + "&".join([f"tokens=T{i}" for i in range(10)])
    resp = client.get(f"/api/v1/sentiment/batch{qs}", headers=headers)
    assert resp.status_code == 400
