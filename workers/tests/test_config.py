"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Tests for Settings class."""

    def test_default_environment(self) -> None:
        """Test default environment is development."""
        from src.config import Settings

        settings = Settings(_env_file=None)
        assert settings.environment.value == "development"

    def test_default_tracked_tokens(self) -> None:
        """Test default tracked tokens."""
        from src.config import Settings

        settings = Settings(_env_file=None)
        assert "BTC" in settings.tracked_tokens
        assert "ETH" in settings.tracked_tokens

    def test_parse_tracked_tokens_from_string(self) -> None:
        """Test parsing tracked tokens from comma-separated string."""
        from src.config import Settings

        with patch.dict(os.environ, {"TRACKED_TOKENS": "SOL,MATIC,LINK"}):
            settings = Settings(_env_file=None)
            assert "SOL" in settings.tracked_tokens
            assert "MATIC" in settings.tracked_tokens
            assert "LINK" in settings.tracked_tokens

    def test_token_symbols_uppercased(self) -> None:
        """Test that token symbols are uppercased."""
        from src.config import Settings

        with patch.dict(os.environ, {"TRACKED_TOKENS": "btc,eth,sol"}):
            settings = Settings(_env_file=None)
            assert "BTC" in settings.tracked_tokens
            assert "ETH" in settings.tracked_tokens

    def test_parse_discord_guild_ids(self) -> None:
        """Test parsing Discord guild IDs."""
        from src.config import Settings

        with patch.dict(os.environ, {"DISCORD_GUILD_IDS": "123,456,789"}):
            settings = Settings(_env_file=None)
            assert settings.discord_guild_ids == [123, 456, 789]

    def test_parse_telegram_chat_ids(self) -> None:
        """Test parsing Telegram chat IDs."""
        from src.config import Settings

        with patch.dict(os.environ, {"TELEGRAM_CHAT_IDS": "-100123,-100456"}):
            settings = Settings(_env_file=None)
            assert settings.telegram_chat_ids == [-100123, -100456]

    def test_ethereum_address_validation_valid(self) -> None:
        """Test valid Ethereum address passes validation."""
        from src.config import Settings

        valid_address = "0x" + "a" * 40
        with patch.dict(os.environ, {"ORACLE_CONTRACT_ADDRESS": valid_address}):
            settings = Settings(_env_file=None)
            assert settings.oracle_contract_address == valid_address

    def test_ethereum_address_validation_invalid(self) -> None:
        """Test invalid Ethereum address fails validation."""
        from src.config import Settings

        invalid_addresses = [
            "not_an_address",
            "0x123",  # Too short
            "0x" + "g" * 40,  # Invalid characters
        ]

        for addr in invalid_addresses:
            with patch.dict(os.environ, {"ORACLE_CONTRACT_ADDRESS": addr}):
                with pytest.raises(ValueError):
                    Settings(_env_file=None)

    def test_is_production_property(self) -> None:
        """Test is_production property."""
        from src.config import Settings

        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            settings = Settings(_env_file=None)
            assert settings.is_production

        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            settings = Settings(_env_file=None)
            assert not settings.is_production

    def test_rpc_url_based_on_environment(self) -> None:
        """Test RPC URL selection based on environment."""
        from src.config import Settings

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "POLYGON_RPC_URL": "https://mainnet.example.com",
                "POLYGON_AMOY_RPC_URL": "https://testnet.example.com",
            },
        ):
            settings = Settings(_env_file=None)
            assert settings.rpc_url == "https://mainnet.example.com"

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "POLYGON_RPC_URL": "https://mainnet.example.com",
                "POLYGON_AMOY_RPC_URL": "https://testnet.example.com",
            },
        ):
            settings = Settings(_env_file=None)
            assert settings.rpc_url == "https://testnet.example.com"

    def test_update_interval_bounds(self) -> None:
        """Test update interval validation bounds."""
        from src.config import Settings

        # Valid value
        with patch.dict(os.environ, {"UPDATE_INTERVAL_SECONDS": "300"}):
            settings = Settings(_env_file=None)
            assert settings.update_interval_seconds == 300

        # Too low
        with patch.dict(os.environ, {"UPDATE_INTERVAL_SECONDS": "30"}):
            with pytest.raises(ValueError):
                Settings(_env_file=None)

        # Too high
        with patch.dict(os.environ, {"UPDATE_INTERVAL_SECONDS": "5000"}):
            with pytest.raises(ValueError):
                Settings(_env_file=None)

    def test_confidence_threshold_bounds(self) -> None:
        """Test confidence threshold validation."""
        from src.config import Settings

        # Valid value
        with patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "0.7"}):
            settings = Settings(_env_file=None)
            assert settings.confidence_threshold == 0.7

        # Invalid: greater than 1
        with patch.dict(os.environ, {"CONFIDENCE_THRESHOLD": "1.5"}):
            with pytest.raises(ValueError):
                Settings(_env_file=None)

    def test_secret_str_types(self) -> None:
        """Test that sensitive fields use SecretStr."""
        from src.config import Settings

        with patch.dict(
            os.environ,
            {
                "TWITTER_BEARER_TOKEN": "secret_token_123",
                "DISCORD_BOT_TOKEN": "discord_secret",
            },
        ):
            settings = Settings(_env_file=None)

            # Should not expose secret in string representation
            assert "secret_token_123" not in str(settings.twitter_bearer_token)
            assert "discord_secret" not in str(settings.discord_bot_token)

            # Can get actual value with get_secret_value()
            assert settings.twitter_bearer_token.get_secret_value() == "secret_token_123"


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_cached(self) -> None:
        """Test that get_settings returns cached instance."""
        from src.config import get_settings

        # Clear cache first
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
