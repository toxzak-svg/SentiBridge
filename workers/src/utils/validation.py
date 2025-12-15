"""
Input validation using Pydantic models.

All external data must be validated before processing.
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Ethereum address pattern
ETH_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")


class SocialPost(BaseModel):
    """
    Validated social media post.

    All posts from collectors must be validated through this model
    before being processed by the sentiment analyzer.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    source: Annotated[str, Field(pattern=r"^(twitter|discord|telegram)$", alias="platform")]
    post_id: Annotated[str, Field(min_length=1, max_length=100, alias="id")]
    author_id: Annotated[str, Field(min_length=1, max_length=100)]
    text: Annotated[str, Field(min_length=1, max_length=10000, alias="content")]
    timestamp: datetime
    # backward-compatible optional username
    author_username: str | None = Field(default=None, alias="author_username")
    token_mentions: list[str] = Field(default_factory=list)

    # Optional metadata
    author_followers: int | None = Field(default=None, ge=0, alias="follower_count")
    author_verified: bool = False
    # Optional account age in days (collectors may provide this)
    author_account_age_days: int | None = Field(default=None, ge=0, alias="account_age_days")
    engagement_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)
    retweet_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """Sanitize text content."""
        # Remove null bytes
        v = v.replace("\x00", "")
        # Normalize unicode
        import unicodedata

        v = unicodedata.normalize("NFKC", v)
        # Strip excessive whitespace
        v = " ".join(v.split())
        return v

    @field_validator("timestamp")
    @classmethod
    def parse_timestamp(cls, v):
        """Accept epoch timestamps (int/float) as well as datetime."""
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v)
        return v

    @field_validator("token_mentions")
    @classmethod
    def validate_token_mentions(cls, v: list[str]) -> list[str]:
        """Validate token mention formats."""
        validated = []
        for mention in v:
            # Accept $SYMBOL format or 0x... address format
            if mention.startswith("$") or ETH_ADDRESS_PATTERN.match(mention):
                validated.append(mention.upper() if mention.startswith("$") else mention.lower())
        return validated


class SentimentScore(BaseModel):
    """
    Validated sentiment score output.

    Represents the analyzed sentiment for a single post.
    """

    model_config = ConfigDict(frozen=True)

    post_id: str
    score: Annotated[float, Field(ge=-1.0, le=1.0)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    model_version: str
    processing_time_ms: Annotated[float, Field(ge=0)]


class AggregatedSentiment(BaseModel):
    """
    Validated aggregated sentiment for a token.

    This is what gets submitted to the oracle contract.
    """

    model_config = ConfigDict(frozen=True)

    token_address: Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]{40}$")]
    score: Annotated[float, Field(ge=-1.0, le=1.0)]
    sample_size: Annotated[int, Field(ge=1)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    timestamp: datetime
    sources: dict[str, int]  # source -> count

    @property
    def score_int(self) -> int:
        """Convert score to 18-decimal fixed point for smart contract."""
        return int(self.score * 10**18)

    @property
    def confidence_basis_points(self) -> int:
        """Convert confidence to basis points (0-10000) for smart contract."""
        return int(self.confidence * 10000)


class ManipulationFlags(BaseModel):
    """
    Manipulation detection results.

    Flags suspicious activity patterns that may indicate
    coordinated manipulation attempts.
    """

    model_config = ConfigDict(frozen=True)

    is_suspicious: bool
    reasons: list[str] = Field(default_factory=list)
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]

    # Specific indicators
    volume_anomaly: bool = False
    content_similarity_score: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    temporal_clustering_score: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    new_account_ratio: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    cross_platform_divergence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    # Additional signals
    duplicate_ratio: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    burst_score: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0


class OracleUpdate(BaseModel):
    """
    Validated oracle update parameters.

    Final validation before blockchain submission.
    """

    model_config = ConfigDict(frozen=True)

    token_address: Annotated[str, Field(pattern=r"^0x[a-fA-F0-9]{40}$")]
    score: Annotated[int, Field(ge=-10**18, le=10**18)]
    sample_size: Annotated[int, Field(ge=1, le=2**32 - 1)]
    confidence: Annotated[int, Field(ge=0, le=10000)]

    @classmethod
    def from_aggregated(cls, agg: AggregatedSentiment) -> "OracleUpdate":
        """Create oracle update from aggregated sentiment."""
        return cls(
            token_address=agg.token_address,
            score=agg.score_int,
            sample_size=min(agg.sample_size, 2**32 - 1),
            confidence=agg.confidence_basis_points,
        )
