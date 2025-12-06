"""
Discord data collector.

Monitors Discord servers for token-related discussions.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from src.collectors.base import BaseCollector
from src.utils.logging import get_logger
from src.utils.validation import SocialPost

logger = get_logger(__name__)

# Token mention patterns
CASHTAG_PATTERN = re.compile(r"\$([A-Za-z]{2,10})\b")
ADDRESS_PATTERN = re.compile(r"0x[a-fA-F0-9]{40}")


class DiscordCollector(BaseCollector):
    """
    Discord data collector.

    Uses discord.py to monitor specified guild channels.
    """

    def __init__(self, bot_token: str, guild_ids: list[int]) -> None:
        """
        Initialize Discord collector.

        Args:
            bot_token: Discord bot token
            guild_ids: List of guild IDs to monitor
        """
        self._bot_token = bot_token
        self._guild_ids = set(guild_ids)
        self._client: Any = None
        self._connected = False

    @property
    def source_name(self) -> str:
        return "discord"

    async def connect(self) -> None:
        """Initialize Discord client."""
        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            intents.messages = True

            self._client = discord.Client(intents=intents)
            self._connected = True
            logger.info("Discord collector initialized", guild_count=len(self._guild_ids))
        except ImportError:
            raise RuntimeError("discord.py is required. Install with: pip install discord.py")

    async def disconnect(self) -> None:
        """Clean up Discord client."""
        if self._client is not None:
            await self._client.close()
        self._client = None
        self._connected = False
        logger.info("Discord collector disconnected")

    async def health_check(self) -> bool:
        """Check Discord connection status."""
        return self._connected and self._client is not None

    async def collect(
        self,
        tokens: list[str],
        since: datetime | None = None,
        limit: int = 1000,
    ) -> AsyncIterator[SocialPost]:
        """
        Collect messages from monitored Discord guilds.

        Note: This is a simplified implementation. In production,
        you would use the bot's message history API.

        Args:
            tokens: Token symbols or addresses to search for
            since: Collect messages after this time
            limit: Maximum messages to collect

        Yields:
            Validated SocialPost objects
        """
        if not self._connected or self._client is None:
            raise RuntimeError("Discord collector not connected")

        # Default to 1 hour ago
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=1)

        logger.info(
            "Starting Discord collection",
            tokens=tokens,
            since=since.isoformat(),
            limit=limit,
            guild_count=len(self._guild_ids),
        )

        collected = 0

        # Note: In production, this would be implemented using the bot's
        # message history API with proper pagination and rate limiting.
        # This is a placeholder structure.

        try:
            for guild_id in self._guild_ids:
                if collected >= limit:
                    break

                # Placeholder for actual Discord API calls
                # In practice, you would iterate through channels and
                # fetch message history
                logger.debug("Collecting from guild", guild_id=guild_id)

        except Exception as e:
            logger.error("Discord collection failed", error=str(e))
            raise

        logger.info("Discord collection complete", collected=collected)

    def _extract_token_mentions(self, text: str, target_tokens: list[str]) -> list[str]:
        """Extract token mentions from message text."""
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


class DiscordWebhookReceiver:
    """
    Alternative: Receive Discord messages via webhook.

    More efficient than polling for high-traffic servers.
    The Discord bot sends messages to our API endpoint.
    """

    def __init__(self, webhook_secret: str) -> None:
        self.webhook_secret = webhook_secret

    def verify_signature(self, payload: bytes, signature: str, timestamp: str) -> bool:
        """Verify Discord webhook signature."""
        import hmac
        import hashlib

        message = timestamp.encode() + payload
        expected = hmac.new(
            self.webhook_secret.encode(),
            message,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def process_message(self, data: dict[str, Any]) -> SocialPost | None:
        """Process incoming webhook message."""
        try:
            return SocialPost(
                source="discord",
                post_id=data["message_id"],
                author_id=data["author_id"],
                text=data["content"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                token_mentions=data.get("token_mentions", []),
            )
        except Exception as e:
            logger.warning("Failed to process Discord webhook", error=str(e))
            return None
