import asyncio
import pytest
from datetime import datetime, timezone

from src.services.blockchain import BlockchainService


class FakeCall:
    def __init__(self, result):
        self._result = result

    async def call(self):
        return self._result


class FakeFunctions:
    def __init__(self, mapping):
        self._mapping = mapping

    def getCurrentSentiment(self, token):
        return FakeCall(self._mapping.get("current", (0, 0, 0, b"")))

    def getSentimentHistory(self, token, count):
        return FakeCall(self._mapping.get("history", []))

    def getWhitelistedTokens(self):
        return FakeCall(self._mapping.get("whitelist", []))

    def isTokenWhitelisted(self, token):
        return FakeCall(self._mapping.get("is_whitelisted", False))


class FakeContract:
    def __init__(self, mapping):
        self.functions = FakeFunctions(mapping)


@pytest.mark.asyncio
async def test_get_latest_sentiment_none_and_success():
    svc = BlockchainService()
    svc._initialized = True
    # timestamp == 0 -> None
    svc._contract = FakeContract({"current": (0, 0, 0, b"")})
    res = await svc.get_latest_sentiment("FOO")
    assert res is None

    # valid result
    fake_hash = bytes.fromhex("01" * 32)
    svc._contract = FakeContract({"current": (123, 50, 1700000000, fake_hash)})
    res = await svc.get_latest_sentiment("FOO")
    assert res["score"] == 123
    assert res["volume"] == 50
    assert res["timestamp"] == 1700000000
    assert res["source_hash"].startswith("0x") or len(res["source_hash"]) >= 2


@pytest.mark.asyncio
async def test_get_sentiment_history_filters():
    svc = BlockchainService()
    svc._initialized = True

    now = int(datetime.now(timezone.utc).timestamp())
    entries = [
        (1, 10, 0, b""),  # should be skipped (timestamp 0)
        (2, 20, now - 1000, b"\x01" * 32),
        (3, 30, now - 2000, b"\x02" * 32),
    ]
    svc._contract = FakeContract({"history": entries})

    # from_timestamp filters out older
    history = await svc.get_sentiment_history("FOO", from_timestamp=now - 1500, count=10)
    assert all(h["timestamp"].timestamp() >= now - 1500 for h in history)


@pytest.mark.asyncio
async def test_whitelist_and_is_token_and_trending_and_stats(monkeypatch):
    svc = BlockchainService()
    svc._initialized = True

    # Stub get_whitelisted_tokens and get_latest_sentiment
    monkeypatch.setattr(svc, "get_whitelisted_tokens", lambda: asyncio.sleep(0, result=["A", "B", "C"]))

    async def fake_latest(t):
        return {"token": t, "score": 100, "volume": 10, "timestamp": 1, "source_hash": "0x01"}

    monkeypatch.setattr(svc, "get_latest_sentiment", fake_latest)

    trending = await svc.get_trending_tokens(limit=2)
    assert len(trending) <= 2

    # get_oracle_stats should aggregate volumes
    monkeypatch.setattr(svc, "get_latest_sentiment", lambda t: asyncio.sleep(0, result={"token": t, "score": 0, "volume": 5, "timestamp": int(datetime.now(timezone.utc).timestamp()), "source_hash": "0x01"}))
    stats = await svc.get_oracle_stats()
    assert "total_tokens" in stats
    assert "total_updates" in stats