"""Authentication package."""

from src.auth.dependencies import (
    CurrentUser,
    OptionalUser,
    RateLimitedUser,
    check_rate_limit,
    get_current_user,
    get_optional_user,
    require_tier,
)
from src.auth.jwt import (
    RateLimitConfig,
    create_access_token,
    decode_access_token,
    generate_api_key,
    get_key_prefix,
    hash_api_key,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "generate_api_key",
    "hash_api_key",
    "get_key_prefix",
    "RateLimitConfig",
    "get_current_user",
    "get_optional_user",
    "require_tier",
    "check_rate_limit",
    "CurrentUser",
    "OptionalUser",
    "RateLimitedUser",
]
