"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings() -> MagicMock:
    """Mock settings for testing."""
    settings = MagicMock()
    settings.environment = "development"
    settings.twitter_bearer_token = None
    settings.discord_bot_token = None
    settings.telegram_api_id = None
    settings.telegram_api_hash = None
    settings.polygon_rpc_url = "http://localhost:8545"
    settings.oracle_contract_address = "0x" + "0" * 40
    settings.use_aws_kms = False
    settings.tracked_tokens = ["BTC", "ETH"]
    return settings


@pytest.fixture
def sample_post() -> dict:
    """Sample social post data."""
    return {
        "id": "test123",
        "platform": "twitter",
        "content": "Bitcoin is looking bullish! $BTC to the moon! 🚀",
        "author_id": "author123",
        "author_username": "cryptotrader",
        "timestamp": 1704067200.0,
        "metrics": {
            "likes": 100,
            "retweets": 50,
            "replies": 10,
        },
    }


@pytest.fixture
def sample_posts() -> list[dict]:
    """Multiple sample posts for batch testing."""
    return [
        {
            "id": f"post{i}",
            "platform": "twitter",
            "content": content,
            "author_id": f"author{i}",
            "author_username": f"user{i}",
            "timestamp": 1704067200.0 + i * 60,
            "metrics": {"likes": i * 10, "retweets": i * 5, "replies": i},
        }
        for i, content in enumerate([
            "Bitcoin is going up! Very bullish on $BTC",
            "ETH looking strong today",
            "Bearish sentiment on the market, be careful",
            "Just bought more SOL, feeling good about it",
            "This market is terrible, selling everything",
        ])
    ]


@pytest.fixture
def manipulation_posts() -> list[dict]:
    """Posts that exhibit manipulation patterns."""
    base_time = 1704067200.0
    return [
        {
            "id": f"spam{i}",
            "platform": "twitter",
            "content": "BUY $SCAM NOW! 1000x guaranteed! Don't miss out!",
            "author_id": f"bot{i}",
            "author_username": f"newaccount{i}",
            "timestamp": base_time + i,  # All within seconds
            "metrics": {"likes": 0, "retweets": 0, "replies": 0},
            "account_created": base_time - 86400,  # 1 day old
            "follower_count": 10,
        }
        for i in range(50)
    ]
