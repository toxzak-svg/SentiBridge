"""
Telegram data collector.

Monitors Telegram groups and channels for token discussions.
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


class TelegramCollector(BaseCollector):
    """
    Telegram data collector using python-telegram-bot.

    Monitors specified groups/channels for token mentions.
    """

    def __init__(self, bot_token: str, chat_ids: list[int]) -> None:
        """
        Initialize Telegram collector.

        Args:
            bot_token: Telegram bot token
            chat_ids: List of chat IDs to monitor (groups/channels)
        """
        self._bot_token = bot_token
        self._chat_ids = set(chat_ids)
        self._bot: Any = None
        self._connected = False

    @property
    def source_name(self) -> str:
        return "telegram"

    async def connect(self) -> None:
        """Initialize Telegram bot."""
        try:
            from telegram import Bot

            self._bot = Bot(token=self._bot_token)

            # Verify connection
            me = await self._bot.get_me()
            logger.info(
                "Telegram collector connected",
                bot_username=me.username,
                chat_count=len(self._chat_ids),
            )
            self._connected = True

        except ImportError:
            raise RuntimeError(
                "python-telegram-bot is required. "
                "Install with: pip install python-telegram-bot"
            )
        except Exception as e:
            logger.error("Failed to connect to Telegram", error=str(e))
            raise

    async def disconnect(self) -> None:
        """Clean up Telegram bot."""
        self._bot = None
        self._connected = False
        logger.info("Telegram collector disconnected")

    async def health_check(self) -> bool:
        """Verify Telegram bot access."""
        if not self._connected or self._bot is None:
            return False

        try:
            await self._bot.get_me()
            return True
        except Exception as e:
            logger.warning("Telegram health check failed", error=str(e))
            return False

    async def collect(
        self,
        tokens: list[str],
        since: datetime | None = None,
        limit: int = 1000,
    ) -> AsyncIterator[SocialPost]:
        """
        Collect messages from monitored Telegram chats.

        Note: Telegram Bot API has limitations on accessing chat history.
        For production, consider using a userbot or MTProto client.

        Args:
            tokens: Token symbols or addresses to search for
            since: Collect messages after this time
            limit: Maximum messages to collect

        Yields:
            Validated SocialPost objects
        """
        if not self._connected or self._bot is None:
            raise RuntimeError("Telegram collector not connected")

        # Default to 1 hour ago
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=1)

        logger.info(
            "Starting Telegram collection",
            tokens=tokens,
            since=since.isoformat(),
            limit=limit,
            chat_count=len(self._chat_ids),
        )

        collected = 0

        # Note: Standard Telegram Bot API cannot access message history.
        # This requires either:
        # 1. Using a userbot with MTProto (Telethon/Pyrogram)
        # 2. Having the bot receive messages in real-time via updates
        # 3. Using Telegram's webhook to push messages to our API

        # For this implementation, we'll use the update handler approach
        # where we store messages as they come in and query our cache

        try:
            for chat_id in self._chat_ids:
                if collected >= limit:
                    break

                logger.debug("Collecting from chat", chat_id=chat_id)
                # Implementation would fetch from our message cache

        except Exception as e:
            logger.error("Telegram collection failed", error=str(e))
            raise

        logger.info("Telegram collection complete", collected=collected)

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


class TelegramUpdateHandler:
    """
    Handle incoming Telegram updates in real-time.

    Messages are cached and queried by the collector.
    """

    def __init__(self, bot_token: str, redis_client: Any) -> None:
        self.bot_token = bot_token
        self.redis = redis_client
        self._message_ttl = 3600  # 1 hour

    async def handle_message(self, message: dict[str, Any]) -> None:
        """Process and cache incoming message."""
        try:
            # Store in Redis with TTL
            key = f"telegram:message:{message['message_id']}"
            await self.redis.setex(
                key,
                self._message_ttl,
                message,
            )
        except Exception as e:
            logger.error("Failed to cache Telegram message", error=str(e))

    async def get_recent_messages(
        self,
        chat_id: int,
        since: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Retrieve cached messages for a chat."""
        # Implementation would scan Redis for matching messages
        return []
