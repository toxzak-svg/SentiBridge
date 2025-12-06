"""Health check and status endpoints."""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis

from src.auth.dependencies import get_redis
from src.config import get_settings
from src.models import HealthCheck, OracleStats
from src.services.blockchain import get_blockchain_service

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthCheck,
    summary="Health check",
    description="Check the health of the API and its dependencies.",
)
async def health_check(
    redis: Redis = Depends(get_redis),
) -> HealthCheck:
    """Check health of all services."""
    settings = get_settings()

    # Check Redis
    try:
        await redis.ping()
        redis_status = "healthy"
    except Exception:
        redis_status = "unhealthy"

    # Check blockchain connection
    try:
        blockchain = get_blockchain_service()
        await blockchain.health_check()
        blockchain_status = "healthy"
    except Exception:
        blockchain_status = "unhealthy"

    # Database check would go here
    database_status = "healthy"  # Placeholder

    overall_status = "healthy"
    if any(s == "unhealthy" for s in [redis_status, blockchain_status, database_status]):
        overall_status = "degraded"

    return HealthCheck(
        status=overall_status,
        version="0.1.0",
        environment=settings.environment.value,
        database=database_status,
        redis=redis_status,
        blockchain=blockchain_status,
    )


@router.get(
    "/stats",
    response_model=OracleStats,
    summary="Oracle statistics",
    description="Get overall statistics about the sentiment oracle.",
)
async def get_oracle_stats() -> OracleStats:
    """Get oracle statistics."""
    blockchain = get_blockchain_service()

    try:
        stats = await blockchain.get_oracle_stats()
        return OracleStats(**stats)
    except Exception:
        # Return default stats if unavailable
        from datetime import UTC, datetime

        return OracleStats(
            total_tokens=0,
            total_updates=0,
            last_update=datetime.now(UTC),
            uptime_percentage=0.0,
        )


@router.get(
    "/",
    summary="API information",
    description="Get basic API information.",
)
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": "SentiBridge API",
        "version": "0.1.0",
        "description": "Crypto sentiment oracle API",
        "documentation": "/docs",
        "health": "/health",
    }
