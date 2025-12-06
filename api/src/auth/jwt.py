"""Authentication module for API key and JWT management."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import get_settings
from src.models import Tier, TokenData

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def generate_api_key() -> tuple[str, str]:
    """
    Generate a new API key.
    
    Returns:
        Tuple of (full_key, key_hash) - store hash, return full key once
    """
    # Format: sb_live_<32 random chars>
    key = f"sb_live_{secrets.token_urlsafe(32)}"
    key_hash = hash_api_key(key)
    return key, key_hash


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def get_key_prefix(key: str) -> str:
    """Get the prefix of an API key for display."""
    return key[:12] if len(key) >= 12 else key


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Token payload data
        expires_delta: Token expiration time
        
    Returns:
        Encoded JWT token
    """
    settings = get_settings()

    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> TokenData | None:
    """
    Decode and validate a JWT access token.
    
    Args:
        token: JWT token string
        
    Returns:
        TokenData if valid, None if invalid
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
        )
        user_id: str = payload.get("sub")
        tier: str = payload.get("tier", "free")

        if user_id is None:
            return None

        return TokenData(sub=user_id, tier=Tier(tier))
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


class RateLimitConfig:
    """Rate limit configuration per tier."""

    def __init__(self) -> None:
        """Initialize rate limits from settings."""
        settings = get_settings()

        self.limits = {
            Tier.FREE: {
                "requests_per_day": settings.free_rate_limit,
                "tokens_limit": settings.free_tokens_limit,
                "requests_per_minute": 10,
            },
            Tier.BASIC: {
                "requests_per_day": settings.basic_rate_limit,
                "tokens_limit": settings.basic_tokens_limit,
                "requests_per_minute": 60,
            },
            Tier.PRO: {
                "requests_per_day": settings.pro_rate_limit,
                "tokens_limit": settings.pro_tokens_limit,
                "requests_per_minute": 300,
            },
            Tier.ENTERPRISE: {
                "requests_per_day": settings.enterprise_rate_limit,
                "tokens_limit": settings.enterprise_tokens_limit,
                "requests_per_minute": 1000,
            },
        }

    def get_limits(self, tier: Tier) -> dict:
        """Get rate limits for a tier."""
        return self.limits.get(tier, self.limits[Tier.FREE])

    def get_rate_limit_string(self, tier: Tier) -> str:
        """Get rate limit string for slowapi."""
        limits = self.get_limits(tier)
        return f"{limits['requests_per_minute']}/minute"
