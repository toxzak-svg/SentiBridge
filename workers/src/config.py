"""
Application configuration using Pydantic Settings.

Security best practices:
- Secrets loaded from environment variables or secrets manager
- Validation of all configuration values
- Type-safe configuration access
"""

from enum import Enum
from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """
    Application settings with validation.

    Load order:
    1. Environment variables
    2. .env file (if present)
    3. Default values
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============ Environment ============
    environment: Environment = Environment.DEVELOPMENT
    log_level: LogLevel = LogLevel.INFO
    debug: bool = False

    # ============ Database ============
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://localhost:5432/sentibridge",
        description="PostgreSQL connection URL",
    )
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Database pool settings
    db_pool_size: int = Field(default=5, ge=1, le=100)
    db_max_overflow: int = Field(default=10, ge=0, le=100)

    # ============ Social Media APIs ============
    # Twitter
    twitter_bearer_token: SecretStr | None = None
    twitter_api_key: SecretStr | None = None
    twitter_api_secret: SecretStr | None = None

    # Discord
    discord_bot_token: SecretStr | None = None
    discord_guild_ids: list[int] = Field(default_factory=list)

    # Telegram
    telegram_bot_token: SecretStr | None = None
    telegram_chat_ids: list[int] = Field(default_factory=list)

    # ============ Blockchain ============
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon mainnet RPC URL",
    )
    polygon_amoy_rpc_url: str = Field(
        default="https://rpc-amoy.polygon.technology",
        description="Polygon Amoy testnet RPC URL",
    )
    oracle_contract_address: str = Field(
        default="0x0000000000000000000000000000000000000000",
        description="Deployed oracle contract address",
    )

    # Private key (only for development - use KMS in production)
    oracle_private_key: SecretStr | None = None
    operator_private_key: SecretStr | None = None  # Alias for oracle_private_key
    use_aws_kms: bool = Field(
        default=False,
        description="Use AWS KMS for transaction signing in production",
    )

    # ============ AWS ============
    aws_region: str = "us-east-1"
    aws_secrets_arn: str | None = None
    aws_kms_key_id: str | None = None

    # ============ Telegram API (for user client) ============
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_phone: str | None = None

    # ============ Token Tracking ============
    tracked_tokens: list[str] = Field(
        default_factory=lambda: ["BTC", "ETH", "SOL", "MATIC"],
        description="List of tokens to track sentiment for",
    )

    # ============ Worker Settings ============
    update_interval_seconds: int = Field(
        default=300,  # 5 minutes
        ge=60,
        le=3600,
        description="Interval between oracle updates",
    )
    min_sample_size: int = Field(
        default=10,
        ge=1,
        description="Minimum posts required for sentiment calculation",
    )
    confidence_threshold: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to publish update",
    )

    # Circuit breaker
    max_score_change: float = Field(
        default=0.2,  # 20%
        ge=0.0,
        le=1.0,
        description="Maximum allowed score change per update",
    )

    # ============ Monitoring ============
    sentry_dsn: str | None = None
    prometheus_enabled: bool = True
    prometheus_port: int = 9090

    # ============ Validators ============
    @field_validator("discord_guild_ids", mode="before")
    @classmethod
    def parse_discord_guild_ids(cls, v: Any) -> list[int]:
        """Parse comma-separated guild IDs from environment."""
        if isinstance(v, str):
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",")]
        return v or []

    @field_validator("telegram_chat_ids", mode="before")
    @classmethod
    def parse_telegram_chat_ids(cls, v: Any) -> list[int]:
        """Parse comma-separated chat IDs from environment."""
        if isinstance(v, str):
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",")]
        return v or []

    @field_validator("tracked_tokens", mode="before")
    @classmethod
    def parse_tracked_tokens(cls, v: Any) -> list[str]:
        """Parse comma-separated token symbols from environment."""
        if isinstance(v, str):
            if not v:
                return ["BTC", "ETH"]
            return [x.strip().upper() for x in v.split(",")]
        return v or ["BTC", "ETH"]

    @field_validator("oracle_contract_address")
    @classmethod
    def validate_ethereum_address(cls, v: str) -> str:
        """Validate Ethereum address format."""
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Invalid Ethereum address format")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION

    @property
    def rpc_url(self) -> str:
        """Get appropriate RPC URL based on environment."""
        if self.environment == Environment.PRODUCTION:
            return self.polygon_rpc_url
        return self.polygon_amoy_rpc_url


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Using lru_cache ensures settings are loaded once and reused.
    """
    return Settings()
