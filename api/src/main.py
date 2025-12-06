"""Main FastAPI application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis

from src import auth
from src.config import get_settings
from src.routers import health_router, keys_router, sentiment_router
from src.services.blockchain import get_blockchain_service

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()

    # Initialize Redis
    logger.info("Initializing Redis connection...")
    redis_url = str(settings.redis_url)
    auth.dependencies.redis_client = Redis.from_url(
        redis_url,
        decode_responses=False,
    )

    # Initialize blockchain service
    logger.info("Initializing blockchain service...")
    blockchain = get_blockchain_service()
    try:
        await blockchain.initialize()
        logger.info("Blockchain service initialized")
    except Exception as e:
        logger.warning(f"Blockchain initialization failed: {e}")

    # Initialize Sentry if configured
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment.value,
            traces_sample_rate=0.1,
        )
        logger.info("Sentry initialized")

    logger.info("Application startup complete")

    yield

    # Cleanup
    logger.info("Shutting down...")
    if auth.dependencies.redis_client:
        await auth.dependencies.redis_client.close()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="SentiBridge API",
        description="""
## Crypto Sentiment Oracle API

SentiBridge provides real-time cryptocurrency sentiment data aggregated 
from social media platforms and stored on the Polygon blockchain.

### Features

- **Real-time Sentiment**: Get current sentiment scores for cryptocurrencies
- **Historical Data**: Access historical sentiment trends (tier-dependent)
- **Batch Queries**: Query multiple tokens in a single request
- **Webhooks**: Subscribe to sentiment change notifications

### Authentication

All endpoints require an API key passed in the `X-API-Key` header.
Free tier allows limited access without authentication.

### Rate Limits

| Tier | Requests/min | Requests/day | History |
|------|--------------|--------------|---------|
| Free | 10 | 100 | None |
| Basic | 60 | 1,000 | 24h |
| Pro | 300 | 10,000 | 72h |
| Enterprise | 1,000 | 100,000 | 7d+ |

        """,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Prometheus metrics
    if settings.prometheus_enabled:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # Include routers
    app.include_router(health_router)
    app.include_router(sentiment_router, prefix="/api/v1")
    app.include_router(keys_router, prefix="/api/v1")

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
        )

        if settings.debug:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "internal_server_error",
                    "message": str(exc),
                    "type": type(exc).__name__,
                },
            )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
            },
        )

    return app


# Create app instance
app = create_app()
