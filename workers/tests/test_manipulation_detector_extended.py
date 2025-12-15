"""Extended tests for manipulation detector heuristics."""
import asyncio
from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_duplicate_content_detection() -> None:
    from src.processors.manipulation_detector import ManipulationDetector
    from src.utils.validation import SocialPost

    detector = ManipulationDetector(duplicate_threshold=0.4)

    base = "Buy $SCAMTOKEN now!"
    posts = [
        SocialPost(
            source="twitter",
            post_id=f"d{i}",
            author_id=f"u{i}",
            text=(base if i % 3 != 0 else base + " extra"),
            timestamp=datetime.utcnow() - timedelta(seconds=i * 10),
        )
        for i in range(30)
    ]

    flags = await detector.analyze(posts, token="TOK_DUP")
    assert flags.duplicate_ratio > 0.0
    assert (flags.is_suspicious and flags.duplicate_ratio > 0.3) or not flags.is_suspicious


@pytest.mark.asyncio
async def test_burst_detection() -> None:
    from src.processors.manipulation_detector import ManipulationDetector
    from src.utils.validation import SocialPost

    detector = ManipulationDetector(burst_window_seconds=60, burst_ratio_threshold=0.5)

    # Create 40 posts where 30 occur within 30 seconds
    now = datetime.utcnow()
    posts = []
    for i in range(30):
        posts.append(
            SocialPost(
                source="twitter",
                post_id=f"b{i}",
                author_id=f"a{i}",
                text=f"Burst {i}",
                timestamp=now - timedelta(seconds=i % 30),
            )
        )
    for i in range(10):
        posts.append(
            SocialPost(
                source="twitter",
                post_id=f"b_extra{i}",
                author_id=f"x{i}",
                text=f"Normal {i}",
                timestamp=now - timedelta(minutes=10 + i),
            )
        )

    flags = await detector.analyze(posts, token="TOK_BURST")
    assert flags.burst_score > 0.0
    assert (flags.is_suspicious and flags.burst_score > 0.4) or not flags.is_suspicious


def test_quality_weights_account_age() -> None:
    from src.processors.manipulation_detector import ManipulationDetector
    from src.utils.validation import SocialPost

    detector = ManipulationDetector()

    posts = [
        SocialPost(
            source="twitter",
            post_id="old1",
            author_id="old_a",
            text="Old account post",
            timestamp=datetime.utcnow(),
            author_followers=500,
            author_account_age_days=800,
        ),
        SocialPost(
            source="twitter",
            post_id="new1",
            author_id="new_a",
            text="New account post",
            timestamp=datetime.utcnow(),
            author_followers=50,
            author_account_age_days=5,
        ),
    ]

    weights = detector.calculate_quality_weights(posts)
    assert weights["old1"] > weights["new1"]
