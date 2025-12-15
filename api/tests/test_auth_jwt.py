from datetime import timedelta, UTC, datetime

from src.auth.jwt import (
    generate_api_key,
    hash_api_key,
    get_key_prefix,
    create_access_token,
    decode_access_token,
    verify_password,
    get_password_hash,
    RateLimitConfig,
)
from src.models import Tier


def test_generate_and_hash_key():
    key, key_hash = generate_api_key()
    assert key.startswith("sb_live_")
    assert hash_api_key(key) == key_hash


def test_key_prefix():
    assert get_key_prefix("short") == "short"
    assert isinstance(get_key_prefix("sb_live_abcdef123456"), str)


def test_jwt_encode_decode(tmp_path):
    token = create_access_token({"sub": "user1", "tier": "pro"}, expires_delta=timedelta(minutes=5))
    data = decode_access_token(token)
    assert data is not None
    assert data.sub == "user1"


def test_password_hash_and_verify():
    pw = "s3cret"
    try:
        import bcrypt  # type: ignore
    except Exception:
        import pytest

        pytest.skip("bcrypt backend not available; skipping hash test")

    h = get_password_hash(pw)
    assert verify_password(pw, h)


def test_rate_limit_config_defaults():
    cfg = RateLimitConfig()
    limits = cfg.get_limits(Tier.FREE)
    assert "requests_per_minute" in limits
    assert isinstance(cfg.get_rate_limit_string(Tier.PRO), str)
