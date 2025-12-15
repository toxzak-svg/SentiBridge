"""Showcase for the ManipulationDetector.

Creates sample scenarios and prints detection results.

Run: python -m workers.examples.showcase_manipulation
"""
import asyncio
from datetime import datetime, timedelta

from src.processors.manipulation_detector import ManipulationDetector
from src.utils.validation import SocialPost


def make_post(i: int, text: str, seconds_offset: int = 0, followers: int | None = 1000, verified: bool = False, source: str = "twitter") -> SocialPost:
    return SocialPost(
        source=source,
        post_id=f"p{i}",
        author_id=f"a{i}",
        text=text,
        timestamp=datetime.utcnow() - timedelta(seconds=seconds_offset),
        token_mentions=[],
        author_followers=followers,
        author_verified=verified,
        engagement_count=0,
    )


async def run_showcase() -> None:
    detector = ManipulationDetector()

    # Scenario 1: normal, diverse posts
    normal_posts = [
        make_post(i, t, seconds_offset=i * 3600, followers=1000 + i * 100)
        for i, t in enumerate([
            "Holding long-term, fundamentals are strong",
            "Watching the charts, seems healthy",
            "Love the new protocol upgrade",
            "Noticed some accumulation",
            "Still skeptical but watching",
        ])
    ]

    res_normal = await detector.analyze(normal_posts, token="TOKEN_A")
    print("--- Normal posts result ---")
    print(res_normal.json(indent=2))

    # Scenario 2: coordinated spam / volume spike
    spam_posts = [
        make_post(i, "BUY $SCAM NOW! 1000x guaranteed!", seconds_offset=i, followers=5, verified=False)
        for i in range(60)
    ]

    res_spam = await detector.analyze(spam_posts, token="TOKEN_A")
    print("--- Spam/volume spike result ---")
    print(res_spam.json(indent=2))

    # Scenario 3: cross-platform divergence
    mixed = []
    # Twitter shows high (synthetic) engagement normalized by followers
    for i in range(20):
        mixed.append(make_post(i, "Twitter hype!", seconds_offset=i * 10, followers=50, source="twitter"))
    # Telegram shows low
    for i in range(5):
        mixed.append(make_post(100 + i, "Calm discussion", seconds_offset=100 + i * 60, followers=5000, source="telegram"))

    res_div = await detector.analyze(mixed, token="TOKEN_B")
    print("--- Cross-platform divergence result ---")
    print(res_div.json(indent=2))


def main() -> None:
    asyncio.run(run_showcase())


if __name__ == "__main__":
    main()
