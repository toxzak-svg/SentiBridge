"""Sentiment data endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from src.auth import RateLimitedUser, require_tier
from src.models import (
    BatchSentimentResponse,
    SentimentHistoryResponse,
    SentimentResponse,
    Tier,
)
from src.services.blockchain import get_blockchain_service

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


def score_to_sentiment(score: int) -> str:
    """Convert numeric score to sentiment label."""
    if score >= 7000:
        return "bullish"
    elif score >= 5500:
        return "slightly_bullish"
    elif score >= 4500:
        return "neutral"
    elif score >= 3000:
        return "slightly_bearish"
    else:
        return "bearish"


@router.get(
    "/current/{token}",
    response_model=SentimentResponse,
    summary="Get current sentiment for a token",
    description="Returns the latest sentiment score for the specified token.",
)
async def get_current_sentiment(
    token: str,
    user: RateLimitedUser,
) -> SentimentResponse:
    """Get current sentiment for a specific token."""
    blockchain = get_blockchain_service()

    try:
        data = await blockchain.get_latest_sentiment(token.upper())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Token {token} not found or no sentiment data available",
        ) from e

    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No sentiment data available for {token}",
        )

    return SentimentResponse(
        token=data["token"],
        score=data["score"],
        score_normalized=data["score"] / 10000,
        sentiment=score_to_sentiment(data["score"]),
        volume=data["volume"],
        last_updated=datetime.fromtimestamp(data["timestamp"], tz=UTC),
        confidence=min(1.0, data["volume"] / 100),  # Simple confidence based on volume
    )


@router.get(
    "/batch",
    response_model=BatchSentimentResponse,
    summary="Get sentiment for multiple tokens",
    description="Returns current sentiment for multiple tokens in a single request.",
)
async def get_batch_sentiment(
    user: RateLimitedUser,
    tokens: list[str] = Query(
        ...,
        description="List of token symbols",
        min_length=1,
        max_length=50,
    ),
) -> BatchSentimentResponse:
    """Get sentiment for multiple tokens."""
    # Check token limit based on tier
    from src.auth import RateLimitConfig

    config = RateLimitConfig()
    limits = config.get_limits(user.tier)
    max_tokens = limits["tokens_limit"]

    if max_tokens > 0 and len(tokens) > max_tokens:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your tier allows maximum {max_tokens} tokens per request",
        )

    blockchain = get_blockchain_service()
    results = []

    for token in tokens:
        try:
            data = await blockchain.get_latest_sentiment(token.upper())
            if data:
                results.append(
                    SentimentResponse(
                        token=data["token"],
                        score=data["score"],
                        score_normalized=data["score"] / 10000,
                        sentiment=score_to_sentiment(data["score"]),
                        volume=data["volume"],
                        last_updated=datetime.fromtimestamp(data["timestamp"], tz=UTC),
                        confidence=min(1.0, data["volume"] / 100),
                    )
                )
        except Exception:
            # Skip tokens that fail
            continue

    return BatchSentimentResponse(
        tokens=results,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/history/{token}",
    response_model=SentimentHistoryResponse,
    summary="Get historical sentiment data",
    description="Returns historical sentiment data for a token. Time range depends on tier.",
    dependencies=[require_tier(Tier.BASIC)],
)
async def get_sentiment_history(
    token: str,
    user: RateLimitedUser,
    hours: int = Query(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Hours of history to retrieve",
    ),
) -> SentimentHistoryResponse:
    """Get historical sentiment for a token."""
    # Tier-based history limits
    max_hours = {
        Tier.BASIC: 24,
        Tier.PRO: 72,
        Tier.ENTERPRISE: 168,
    }

    tier_max = max_hours.get(user.tier, 24)
    if hours > tier_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Your tier allows maximum {tier_max} hours of history",
        )

    blockchain = get_blockchain_service()

    try:
        history = await blockchain.get_sentiment_history(
            token.upper(),
            from_timestamp=int((datetime.now(UTC) - timedelta(hours=hours)).timestamp()),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No history available for {token}",
        ) from e

    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No history available for {token}",
        )

    scores = [h["score"] for h in history]

    return SentimentHistoryResponse(
        token=token.upper(),
        history=history,
        average_score=sum(scores) / len(scores),
        min_score=min(scores),
        max_score=max(scores),
        total_volume=sum(h["volume"] for h in history),
    )


@router.get(
    "/trending",
    response_model=list[SentimentResponse],
    summary="Get trending tokens by sentiment change",
    description="Returns tokens with the biggest sentiment changes in the last 24h.",
    dependencies=[require_tier(Tier.PRO)],
)
async def get_trending_tokens(
    user: RateLimitedUser,
    limit: int = Query(default=10, ge=1, le=50),
    direction: str = Query(
        default="both",
        description="Filter by direction: 'bullish', 'bearish', or 'both'",
    ),
) -> list[SentimentResponse]:
    """Get trending tokens by sentiment change."""
    blockchain = get_blockchain_service()

    try:
        trending = await blockchain.get_trending_tokens(limit=limit)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve trending data",
        ) from e

    results = []
    for data in trending:
        sentiment = score_to_sentiment(data["score"])

        # Filter by direction if specified
        if direction == "bullish" and "bullish" not in sentiment:
            continue
        if direction == "bearish" and "bearish" not in sentiment:
            continue

        results.append(
            SentimentResponse(
                token=data["token"],
                score=data["score"],
                score_normalized=data["score"] / 10000,
                sentiment=sentiment,
                volume=data["volume"],
                last_updated=datetime.fromtimestamp(data["timestamp"], tz=UTC),
                confidence=min(1.0, data["volume"] / 100),
            )
        )

    return results[:limit]
