"""FastAPI dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer
from redis.asyncio import Redis

from src.auth.jwt import decode_access_token, hash_api_key, RateLimitConfig
from src.config import get_settings
from src.models import Tier, TokenData

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

# Redis connection (initialized in app startup)
redis_client: Redis | None = None

# Rate limit config
rate_limit_config = RateLimitConfig()


async def get_redis() -> Redis:
    """Get Redis connection."""
    if redis_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis connection not available",
        )
    return redis_client


async def get_api_key_data(
    api_key: str = Depends(api_key_header),
) -> TokenData | None:
    """
    Validate API key and return associated data.
    
    This looks up the API key in Redis/database to get tier info.
    """
    if not api_key:
        return None

    # Hash the key for lookup
    key_hash = hash_api_key(api_key)

    # Look up in Redis (some test fakes may not implement hash commands)
    redis = await get_redis()

    key_data = None
    try:
        if hasattr(redis, "hgetall") and callable(getattr(redis, "hgetall")):
            key_data = await redis.hgetall(f"apikey:{key_hash}")
    except Exception:
        # Best-effort: if Redis doesn't support hgetall (fake in tests), treat as missing
        key_data = None

    if not key_data:
        return None

    # Check if key is active
    try:
        if key_data.get(b"is_active", b"true") == b"false":
            return None
    except Exception:
        return None

    # Update last used timestamp (best-effort)
    try:
        if hasattr(redis, "hset") and callable(getattr(redis, "hset")):
            await redis.hset(f"apikey:{key_hash}", "last_used", str(int(__import__("time").time())))
    except Exception:
        # ignore errors when updating metadata
        pass

    try:
        sub = key_data.get(b"id", b"").decode()
        tier_val = key_data.get(b"tier", b"free").decode()
    except Exception:
        return None

    return TokenData(
        sub=sub,
        tier=Tier(tier_val),
    )


async def get_bearer_token_data(
    bearer = Depends(bearer_scheme),
) -> TokenData | None:
    """Extract and validate bearer token."""
    if not bearer:
        return None

    return decode_access_token(bearer.credentials)


async def get_current_user(
    api_key_data: TokenData | None = Depends(get_api_key_data),
    bearer_data: TokenData | None = Depends(get_bearer_token_data),
) -> TokenData:
    """
    Get current authenticated user from API key or bearer token.
    
    Prefers API key if both are provided.
    """
    # Try API key first
    if api_key_data:
        return api_key_data

    # Fall back to bearer token
    if bearer_data:
        return bearer_data

    # No valid authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


async def get_optional_user(
    api_key_data: TokenData | None = Depends(get_api_key_data),
    bearer_data: TokenData | None = Depends(get_bearer_token_data),
) -> TokenData:
    """
    Get current user or return free tier for unauthenticated requests.
    
    Used for endpoints that allow unauthenticated access with rate limits.
    """
    if api_key_data:
        return api_key_data
    if bearer_data:
        return bearer_data

    # Return anonymous free tier user
    return TokenData(sub="anonymous", tier=Tier.FREE)


def require_tier(minimum_tier: Tier):
    """
    Dependency factory to require minimum tier.
    
    Usage:
        @router.get("/endpoint", dependencies=[Depends(require_tier(Tier.PRO))])
    """

    async def tier_checker(
        current_user: TokenData = Depends(get_current_user),
    ) -> TokenData:
        tier_order = [Tier.FREE, Tier.BASIC, Tier.PRO, Tier.ENTERPRISE]

        user_tier_idx = tier_order.index(current_user.tier)
        required_tier_idx = tier_order.index(minimum_tier)

        if user_tier_idx < required_tier_idx:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires {minimum_tier.value} tier or higher",
            )

        return current_user

    return tier_checker


async def check_rate_limit(
    current_user: TokenData = Depends(get_optional_user),
    x_forwarded_for: str | None = Header(None),
) -> TokenData:
    """
    Check rate limits for the current user/IP.
    
    Uses Redis to track request counts.
    """
    redis = await get_redis()

    # Get identifier (user ID or IP)
    if current_user.sub == "anonymous":
        identifier = x_forwarded_for or "unknown"
    else:
        identifier = current_user.sub

    # Get limits for tier
    limits = rate_limit_config.get_limits(current_user.tier)
    requests_per_minute = limits["requests_per_minute"]

    # Check minute rate limit
    minute_key = f"ratelimit:{identifier}:minute"
    current_count = await redis.incr(minute_key)

    if current_count == 1:
        await redis.expire(minute_key, 60)

    if current_count > requests_per_minute:
        ttl = await redis.ttl(minute_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": f"Rate limit exceeded. Maximum {requests_per_minute} requests per minute.",
                "retry_after": ttl,
                "limit": requests_per_minute,
                "remaining": 0,
            },
            headers={"Retry-After": str(ttl)},
        )

    return current_user


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[TokenData, Depends(get_current_user)]
OptionalUser = Annotated[TokenData, Depends(get_optional_user)]
RateLimitedUser = Annotated[TokenData, Depends(check_rate_limit)]


async def require_api_key(
    api_key_data: TokenData | None = Depends(get_api_key_data),
) -> TokenData:
    """
    Require that a valid API key is present. Raises 401 if not.
    Use this dependency when an endpoint must only accept requests with an API key.
    """
    if not api_key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key_data


# Type alias for endpoints that MUST present an API key
APIKeyRequired = Annotated[TokenData, Depends(require_api_key)]
