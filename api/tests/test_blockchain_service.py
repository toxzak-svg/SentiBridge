import asyncio
from datetime import datetime, UTC

import pytest

from src.services import blockchain as bc_mod


class FakeFunc:
    def __init__(self, value):
        self._value = value

    async def call(self):
        return self._value


class FakeContract:
    def __init__(self, mapping):
        self._mapping = mapping

    class funcs:
        pass

    @property
    def functions(self):
        # Return an object with callables that create FakeFunc
        class F:
            def __init__(self, mapping):
                self._mapping = mapping

            def getCurrentSentiment(self, token):
                return FakeFunc(self._mapping.get(token, (0, 0, 0, bytes(32))))

            def getSentimentHistory(self, token, count):
                return FakeFunc(self._mapping.get("history:" + token, []))

            def getWhitelistedTokens(self):
                return FakeFunc(self._mapping.get("whitelist", []))

            def isTokenWhitelisted(self, token):
                return FakeFunc(self._mapping.get("is_whitelisted:" + token, False))

        return F(self._mapping)


@pytest.mark.asyncio
async def test_blockchain_service_functions(monkeypatch):
    svc = bc_mod.BlockchainService()
    svc._initialized = True

    # Prepare mapping for fake contract responses
    now_ts = int(datetime.now(UTC).timestamp())
    mapping = {
        "TOKENA": (7000, 200, now_ts, bytes.fromhex("00" * 32)),
        "history:TOKENA": [
            (6000, 50, now_ts - 3600, bytes.fromhex("00" * 32)),
            (0, 0, 0, bytes.fromhex("00" * 32)),  # should be skipped
        ],
        "whitelist": ["TOKENA", "TOKENB"],
        "is_whitelisted:TOKENA": True,
    }

    svc._contract = FakeContract(mapping)

    monkeypatch.setattr(bc_mod, "get_blockchain_service", lambda: svc)

    # Test get_latest_sentiment
    res = await svc.get_latest_sentiment("TOKENA")
    assert res and res["token"] == "TOKENA"

    # Timestamp zero should return None
    mapping_zero = {"TOKENX": (100, 1, 0, bytes.fromhex("00" * 32))}
    svc._contract = FakeContract(mapping_zero)
    res = await svc.get_latest_sentiment("TOKENX")
    assert res is None

    # Test history
    svc._contract = FakeContract(mapping)
    hist = await svc.get_sentiment_history("TOKENA", count=10)
    assert isinstance(hist, list) and len(hist) >= 1

    # Test whitelist and is_token_whitelisted
    wl = await svc.get_whitelisted_tokens()
    assert "TOKENA" in wl
    assert await svc.is_token_whitelisted("TOKENA") is True

    # Test trending tokens (uses whitelist and latest sentiment)
    trending = await svc.get_trending_tokens(limit=2)
    assert isinstance(trending, list)

    # Test oracle stats
    stats = await svc.get_oracle_stats()
    assert "total_tokens" in stats and "total_updates" in stats
