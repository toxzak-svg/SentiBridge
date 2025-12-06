"""Pydantic models for API requests and responses."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Tier(str, Enum):
    """API access tiers."""

    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    ENTERPRISE = "enterprise"


# ============ Authentication Models ============


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """JWT token payload data."""

    sub: str  # User ID or API key ID
    tier: Tier = Tier.FREE
    exp: datetime | None = None


class APIKey(BaseModel):
    """API key model."""

    id: str
    key_prefix: str  # First 8 chars for identification
    name: str
    tier: Tier
    created_at: datetime
    last_used: datetime | None = None
    is_active: bool = True


class APIKeyCreate(BaseModel):
    """API key creation request."""

    name: str = Field(..., min_length=1, max_length=100)
    tier: Tier = Tier.FREE


class APIKeyResponse(BaseModel):
    """API key creation response (includes full key once)."""

    id: str
    key: str  # Full key - only shown once!
    name: str
    tier: Tier
    created_at: datetime


# ============ Sentiment Models ============


class SentimentData(BaseModel):
    """Single sentiment data point."""

    token_symbol: str
    score: int = Field(..., ge=0, le=10000, description="Score from 0-10000")
    volume: int = Field(..., ge=0, description="Sample volume")
    timestamp: datetime
    block_number: int | None = None


class SentimentResponse(BaseModel):
    """Current sentiment response."""

    token: str
    score: int = Field(..., ge=0, le=10000)
    score_normalized: float = Field(
        ..., ge=0.0, le=1.0, description="Score normalized to 0-1"
    )
    sentiment: str = Field(
        ..., description="Human readable: bullish/neutral/bearish"
    )
    volume: int
    last_updated: datetime
    confidence: float = Field(..., ge=0.0, le=1.0)


class SentimentHistoryResponse(BaseModel):
    """Historical sentiment response."""

    token: str
    history: list[SentimentData]
    average_score: float
    min_score: int
    max_score: int
    total_volume: int


class BatchSentimentResponse(BaseModel):
    """Batch sentiment query response."""

    tokens: list[SentimentResponse]
    timestamp: datetime


# ============ Statistics Models ============


class TokenStats(BaseModel):
    """Token statistics."""

    token: str
    current_score: int
    score_24h_change: float
    volume_24h: int
    update_count_24h: int
    average_score_7d: float
    volatility_7d: float


class OracleStats(BaseModel):
    """Oracle overall statistics."""

    total_tokens: int
    total_updates: int
    last_update: datetime
    uptime_percentage: float


# ============ Webhook Models ============


class WebhookConfig(BaseModel):
    """Webhook configuration."""

    id: str
    url: str
    events: list[str]
    is_active: bool = True
    created_at: datetime
    secret_hash: str | None = None  # For signature verification


class WebhookCreate(BaseModel):
    """Webhook creation request."""

    url: str = Field(..., min_length=10, max_length=500)
    events: list[str] = Field(
        default_factory=lambda: ["sentiment.updated"],
        description="Events to subscribe to",
    )


class WebhookEvent(BaseModel):
    """Webhook event payload."""

    event_type: str
    timestamp: datetime
    data: dict


# ============ Error Models ============


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict | None = None


class RateLimitError(BaseModel):
    """Rate limit exceeded response."""

    error: str = "rate_limit_exceeded"
    message: str
    retry_after: int  # Seconds until reset
    limit: int
    remaining: int


# ============ Health Models ============


class HealthCheck(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str
    database: str
    redis: str
    blockchain: str
