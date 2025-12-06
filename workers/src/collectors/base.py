"""
Base collector interface.

All social media collectors must implement this interface
to ensure consistent data handling and validation.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import AsyncIterator

from src.utils.validation import SocialPost


class BaseCollector(ABC):
    """
    Abstract base class for social media collectors.

    Implementations must:
    - Handle rate limiting gracefully
    - Validate all collected data
    - Log collection metrics
    - Handle authentication securely
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source identifier (twitter, discord, telegram)."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the data source.

        Should handle authentication and validate credentials.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Clean up connections and resources.

        Should be called when shutting down.
        """
        pass

    @abstractmethod
    async def collect(
        self,
        tokens: list[str],
        since: datetime | None = None,
        limit: int = 1000,
    ) -> AsyncIterator[SocialPost]:
        """
        Collect posts mentioning specified tokens.

        Args:
            tokens: List of token symbols or addresses to search for
            since: Only collect posts after this timestamp
            limit: Maximum number of posts to collect

        Yields:
            Validated SocialPost objects
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the collector is healthy and can collect data.

        Returns:
            True if healthy, False otherwise
        """
        pass
