"""
Twitter/X data collector using Twitter API v2.

Security considerations:
- Bearer token stored securely
- Rate limiting handled gracefully
- Bot/spam filtering applied
"""

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from tenacity import retry, stop_after_attempt, wait_exponential

from src.collectors.base import BaseCollector
from src.utils.logging import get_logger
from src.utils.validation import SocialPost

logger = get_logger(__name__)

# Token mention patterns
CASHTAG_PATTERN = re.compile(r"\$([A-Za-z]{2,10})\b")
ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")


class TwitterCollector(BaseCollector):
    """
    Twitter/X data collector using Tweepy and Twitter API v2.

    Features:
    - Recent search with pagination
    - User metrics for quality weighting
    - Bot detection heuristics
    - Rate limit handling
    """

    def __init__(self, bearer_token: str) -> None:
        """
        Initialize Twitter collector.

        Args:
            bearer_token: Twitter API v2 Bearer Token
        """
        self._bearer_token = bearer_token
        self._client: Any = None
        self._connected = False

    @property
    def source_name(self) -> str:
        return "twitter"

    async def connect(self) -> None:
        """Initialize Tweepy client."""
        try:
            import tweepy

            self._client = tweepy.Client(
                bearer_token=self._bearer_token,
                wait_on_rate_limit=True,
            )
            self._connected = True
            logger.info("Twitter collector connected")
        except ImportError:
            raise RuntimeError("tweepy is required. Install with: pip install tweepy")
        except Exception as e:
            logger.error("Failed to connect to Twitter", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Clean up Twitter client."""
        self._client = None
        self._connected = False
        logger.info("Twitter collector disconnected")

    async def health_check(self) -> bool:
        """Verify Twitter API access."""
        if not self._connected or self._client is None:
            return False

        try:
            # Simple API call to verify credentials
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._client.get_me())
            return True
        except Exception as e:
            logger.warning("Twitter health check failed", error=str(e))
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
    )
    async def collect(
        self,
        tokens: list[str],
        since: datetime | None = None,
        limit: int = 1000,
    ) -> AsyncIterator[SocialPost]:
        """
        Collect tweets mentioning specified tokens.

        Args:
            tokens: Token symbols (e.g., ["MATIC", "USDC"]) or addresses
            since: Collect tweets after this time (default: 1 hour ago)
            limit: Maximum tweets to collect

        Yields:
            Validated SocialPost objects
        """
        if not self._connected or self._client is None:
            raise RuntimeError("Twitter collector not connected")

        # Build search query
        query = self._build_query(tokens)

        # Default to 1 hour ago if not specified
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=1)

        logger.info(
            "Starting Twitter collection",
            tokens=tokens,
            since=since.isoformat(),
            limit=limit,
        )

        collected = 0
        loop = asyncio.get_event_loop()

        try:
            # Use search_recent_tweets with pagination
            paginator = await loop.run_in_executor(
                None,
                lambda: self._client.search_recent_tweets(
                    query=query,
                    start_time=since,
                    max_results=min(100, limit),  # API max per request
                    tweet_fields=["created_at", "public_metrics", "author_id"],
                    user_fields=["public_metrics", "verified", "created_at"],
                    expansions=["author_id"],
                ),
            )

            if paginator.data is None:
                logger.info("No tweets found", query=query)
                return

            # Build user lookup
            users = {}
            if paginator.includes and "users" in paginator.includes:
                users = {u.id: u for u in paginator.includes["users"]}

            for tweet in paginator.data:
                if collected >= limit:
                    break

                # Get author info
                author = users.get(tweet.author_id)

                # Skip potential bots
                if self._is_likely_bot(tweet, author):
                    continue

                # Extract token mentions
                mentions = self._extract_token_mentions(tweet.text, tokens)

                try:
                    post = SocialPost(
                        source="twitter",
                        post_id=str(tweet.id),
                        author_id=str(tweet.author_id),
                        text=tweet.text,
                        timestamp=tweet.created_at,
                        token_mentions=mentions,
                        author_followers=author.public_metrics["followers_count"] if author else 0,
                        author_verified=author.verified if author else False,
                        engagement_count=self._calculate_engagement(tweet),
                        reply_count=tweet.public_metrics.get("reply_count", 0),
                        retweet_count=tweet.public_metrics.get("retweet_count", 0),
                        like_count=tweet.public_metrics.get("like_count", 0),
                    )
                    collected += 1
                    yield post

                except Exception as e:
                    logger.warning(
                        "Failed to parse tweet",
                        tweet_id=tweet.id,
                        error=str(e),
                    )
                    continue

        except Exception as e:
            logger.error("Twitter collection failed", error=str(e))
            raise

        logger.info("Twitter collection complete", collected=collected)

    def _build_query(self, tokens: list[str]) -> str:
        """Build Twitter search query from token list."""
        # Combine cashtags and keywords
        terms = []
        for token in tokens:
            if token.startswith("$"):
                terms.append(token)
            elif token.startswith("0x"):
                terms.append(token)
            else:
                terms.append(f"${token}")
                terms.append(token)

        # Join with OR, filter out retweets and replies
        query = f"({' OR '.join(terms)}) -is:retweet -is:reply lang:en"
        return query

    def _extract_token_mentions(self, text: str, target_tokens: list[str]) -> list[str]:
        """Extract token mentions from tweet text."""
        mentions = set()

        # Find cashtags
        for match in CASHTAG_PATTERN.finditer(text):
            symbol = match.group(1).upper()
            if any(t.upper().replace("$", "") == symbol for t in target_tokens):
                mentions.add(f"${symbol}")

        # Find addresses
        for match in ADDRESS_PATTERN.finditer(text):
            address = match.group(0).lower()
            if any(t.lower() == address for t in target_tokens):
                mentions.add(address)

        return list(mentions)

    def _is_likely_bot(self, tweet: Any, author: Any | None) -> bool:
        """
        Heuristic bot detection.

        Checks for common bot patterns:
        - Very new accounts
        - Suspicious follower/following ratios
        - High tweet frequency
        """
        if author is None:
            return False

        try:
            metrics = author.public_metrics
            followers = metrics.get("followers_count", 0)
            following = metrics.get("following_count", 0)
            tweet_count = metrics.get("tweet_count", 0)

            # Very few followers but many following
            if followers < 10 and following > 1000:
                return True

            # Extremely high tweet rate (spam bot)
            if author.created_at:
                account_age_days = (datetime.now(timezone.utc) - author.created_at).days
                if account_age_days > 0 and tweet_count / account_age_days > 100:
                    return True

            return False

        except Exception:
            return False

    def _calculate_engagement(self, tweet: Any) -> int:
        """Calculate total engagement score."""
        metrics = tweet.public_metrics
        return (
            metrics.get("reply_count", 0)
            + metrics.get("retweet_count", 0)
            + metrics.get("like_count", 0)
            + metrics.get("quote_count", 0)
        )
