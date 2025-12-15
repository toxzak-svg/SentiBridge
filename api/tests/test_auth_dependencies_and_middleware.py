import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException

from fastapi.testclient import TestClient

from src.main import create_app
from src.auth import dependencies as auth_deps
from src.middleware.usage import usage_middleware
from src.auth.jwt import hash_api_key


class TinyReq:
    def __init__(self, path='/', headers=None):
        from starlette.datastructures import URL

        self.url = URL(path)
        self.headers = headers or {}


class DummyResp:
    def __init__(self):
        self.status_code = 200


async def dummy_call_next(request):
    return DummyResp()


def test_get_redis_unavailable():
    auth_deps.redis_client = None

    with pytest.raises(HTTPException) as ei:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(auth_deps.get_redis())
        finally:
            loop.close()

    assert ei.value.status_code == 503


def test_get_api_key_data_and_require_api_key(monkeypatch):
    # Prepare fake redis client
    class FakeRedis:
        def __init__(self):
            self.hashes = {}

        async def hgetall(self, key):
            return self.hashes.get(key, {})

        async def hset(self, key, *args, mapping=None):
            return True

    fake = FakeRedis()
    auth_deps.redis_client = fake

    # Monkeypatch hash_api_key to return a known hash
    monkeypatch.setattr(auth_deps, "hash_api_key", lambda k: "hhash")

    # No data -> get_api_key_data returns None
    loop = asyncio.new_event_loop()
    try:
        res = loop.run_until_complete(auth_deps.get_api_key_data(api_key="sb_live_dummy"))
    finally:
        loop.close()
    assert res is None

    # Add key data and test require_api_key
    fake.hashes["apikey:hhash"] = {b"id": b"key_1", b"tier": b"pro", b"is_active": b"true"}

    loop = asyncio.new_event_loop()
    try:
        res = loop.run_until_complete(auth_deps.get_api_key_data(api_key="sb_live_dummy"))
    finally:
        loop.close()

    assert res is not None

    # require_api_key should return token data when present
    loop = asyncio.new_event_loop()
    try:
        token = loop.run_until_complete(auth_deps.require_api_key(api_key_data=res))
    finally:
        loop.close()

    assert token.sub == "key_1"


def test_usage_middleware_missing_key_returns_401():
    req = TinyReq(path="/api/v1/some")

    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(usage_middleware(req, dummy_call_next))
    finally:
        loop.close()

    assert hasattr(resp, "status_code") and resp.status_code == 401


def test_usage_middleware_with_redis_records(monkeypatch):
    # Setup dependencies.get_redis to return a fake redis that records calls
    class FakeRedis:
        def __init__(self):
            self.incr_calls = []

        async def incr(self, key):
            self.incr_calls.append(key)
            return 1

        async def expire(self, key, seconds):
            return True

    fake = FakeRedis()

    async def fake_get_redis():
        return fake

    monkeypatch.setattr(auth_deps, "get_redis", fake_get_redis)

    req = TinyReq(path="/api/v1/some", headers={"X-API-Key": "sb_live_test"})

    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(usage_middleware(req, dummy_call_next))
    finally:
        loop.close()

    # call_next returns DummyResp
    assert hasattr(resp, "status_code") and resp.status_code == 200
