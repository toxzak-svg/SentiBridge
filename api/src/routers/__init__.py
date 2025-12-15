"""Routers package."""

from src.routers.health import router as health_router
from src.routers.keys import router as keys_router
from src.routers.sentiment import router as sentiment_router
from src.routers.attestations import router as attestations_router

__all__ = ["health_router", "keys_router", "sentiment_router", "attestations_router"]
