"""Usage middleware: require X-API-Key on API routes and record per-call usage in Redis.

This middleware enforces presence of `X-API-Key` for `/api/v1` routes (except `/api/v1/keys`),
increments a Redis usage counter, and sets a TTL for short-term aggregation. Billing
and persistent recording are handled asynchronously by the billing service (stubbed).
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse

from src.auth.jwt import hash_api_key
from src.auth import dependencies


async def usage_middleware(request: Request, call_next: Callable):
    path = request.url.path

    # Only enforce for API paths under /api/v1 (skip docs, metrics, health)
    # Allow unauthenticated access to attestations and keys endpoints
    if path.startswith("/api/v1") and not (
        path.startswith("/api/v1/keys") or path.startswith("/api/v1/attestations")
    ):
        api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"error": "missing_api_key", "message": "X-API-Key header is required"},
            )

        # Hash and increment usage in Redis (best-effort)
        try:
            redis = await dependencies.get_redis()
        except Exception:
            # If Redis unavailable, allow request but do not record usage
            return await call_next(request)

        try:
            key_hash = hash_api_key(api_key)
            # Per-minute counter
            minute_key = f"usage:{key_hash}:{datetime.utcnow().strftime('%Y%m%d%H%M')}"
            await redis.incr(minute_key)
            await redis.expire(minute_key, 60 * 60 * 24)  # keep for 1 day

            # Per-day counter
            day_key = f"usage:{key_hash}:{datetime.utcnow().strftime('%Y%m%d')}"
            await redis.incr(day_key)
            await redis.expire(day_key, 60 * 60 * 24 * 30)  # keep 30 days
        except Exception:
            # Fail silently on recording errors
            pass

    response = await call_next(request)
    return response
