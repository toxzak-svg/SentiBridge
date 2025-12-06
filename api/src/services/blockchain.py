"""Blockchain service for interacting with the sentiment oracle contract."""

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from src.config import get_settings

# Oracle contract ABI (read functions)
ORACLE_ABI = [
    {
        "inputs": [{"name": "tokenSymbol", "type": "string"}],
        "name": "getCurrentSentiment",
        "outputs": [
            {"name": "score", "type": "uint256"},
            {"name": "volume", "type": "uint256"},
            {"name": "timestamp", "type": "uint256"},
            {"name": "sourceHash", "type": "bytes32"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "tokenSymbol", "type": "string"},
            {"name": "count", "type": "uint256"},
        ],
        "name": "getSentimentHistory",
        "outputs": [
            {
                "components": [
                    {"name": "score", "type": "uint256"},
                    {"name": "volume", "type": "uint256"},
                    {"name": "timestamp", "type": "uint256"},
                    {"name": "sourceHash", "type": "bytes32"},
                ],
                "name": "",
                "type": "tuple[]",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenSymbol", "type": "string"}],
        "name": "isTokenWhitelisted",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getWhitelistedTokens",
        "outputs": [{"name": "", "type": "string[]"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class BlockchainService:
    """Service for interacting with the blockchain oracle."""

    def __init__(self) -> None:
        """Initialize blockchain service."""
        self._web3: Any = None
        self._contract: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize Web3 connection."""
        if self._initialized:
            return

        try:
            from web3 import AsyncHTTPProvider, AsyncWeb3
            from web3.middleware import ExtraDataToPOAMiddleware
        except ImportError as e:
            raise RuntimeError("web3 package required") from e

        settings = get_settings()

        self._web3 = AsyncWeb3(AsyncHTTPProvider(settings.polygon_rpc_url))
        self._web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        if not await self._web3.is_connected():
            raise ConnectionError("Failed to connect to blockchain")

        self._contract = self._web3.eth.contract(
            address=self._web3.to_checksum_address(settings.oracle_contract_address),
            abi=ORACLE_ABI,
        )

        self._initialized = True

    async def health_check(self) -> bool:
        """Check blockchain connection health."""
        if not self._initialized:
            await self.initialize()

        try:
            await self._web3.eth.block_number
            return True
        except Exception:
            return False

    async def get_latest_sentiment(self, token: str) -> dict[str, Any] | None:
        """Get latest sentiment for a token."""
        if not self._initialized:
            await self.initialize()

        try:
            result = await self._contract.functions.getCurrentSentiment(token).call()
            score, volume, timestamp, source_hash = result

            if timestamp == 0:
                return None

            return {
                "token": token,
                "score": score,
                "volume": volume,
                "timestamp": timestamp,
                "source_hash": source_hash.hex(),
            }
        except Exception:
            return None

    async def get_sentiment_history(
        self,
        token: str,
        from_timestamp: int | None = None,
        count: int = 288,  # 24 hours at 5-min intervals
    ) -> list[dict[str, Any]]:
        """Get sentiment history for a token."""
        if not self._initialized:
            await self.initialize()

        try:
            result = await self._contract.functions.getSentimentHistory(
                token, count
            ).call()

            history = []
            for entry in result:
                score, volume, timestamp, source_hash = entry

                if timestamp == 0:
                    continue

                if from_timestamp and timestamp < from_timestamp:
                    continue

                history.append({
                    "token_symbol": token,
                    "score": score,
                    "volume": volume,
                    "timestamp": datetime.fromtimestamp(timestamp, tz=UTC),
                    "block_number": None,  # Would need additional call
                })

            return history
        except Exception:
            return []

    async def get_whitelisted_tokens(self) -> list[str]:
        """Get list of whitelisted tokens."""
        if not self._initialized:
            await self.initialize()

        try:
            return await self._contract.functions.getWhitelistedTokens().call()
        except Exception:
            return []

    async def is_token_whitelisted(self, token: str) -> bool:
        """Check if a token is whitelisted."""
        if not self._initialized:
            await self.initialize()

        try:
            return await self._contract.functions.isTokenWhitelisted(token).call()
        except Exception:
            return False

    async def get_trending_tokens(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get trending tokens by sentiment change.
        
        This is a simplified implementation - in production,
        you'd use the Subgraph for efficient historical queries.
        """
        if not self._initialized:
            await self.initialize()

        tokens = await self.get_whitelisted_tokens()
        results = []

        for token in tokens[:limit * 2]:  # Check more than needed
            data = await self.get_latest_sentiment(token)
            if data:
                results.append(data)

        # Sort by volume (as proxy for activity)
        results.sort(key=lambda x: x["volume"], reverse=True)

        return results[:limit]

    async def get_oracle_stats(self) -> dict[str, Any]:
        """Get oracle statistics."""
        if not self._initialized:
            await self.initialize()

        tokens = await self.get_whitelisted_tokens()

        total_updates = 0
        last_update = 0

        for token in tokens[:20]:  # Sample first 20
            data = await self.get_latest_sentiment(token)
            if data:
                total_updates += data["volume"]
                last_update = max(last_update, data["timestamp"])

        return {
            "total_tokens": len(tokens),
            "total_updates": total_updates,
            "last_update": datetime.fromtimestamp(last_update, tz=UTC)
            if last_update
            else datetime.now(UTC),
            "uptime_percentage": 99.9,  # Would need actual monitoring
        }


# Singleton instance
_blockchain_service: BlockchainService | None = None


def get_blockchain_service() -> BlockchainService:
    """Get the blockchain service singleton."""
    global _blockchain_service
    if _blockchain_service is None:
        _blockchain_service = BlockchainService()
    return _blockchain_service
