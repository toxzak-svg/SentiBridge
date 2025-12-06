"""API configuration using Pydantic Settings."""

from enum import Enum
from functools import lru_cache

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """API configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ============ Environment ============
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # ============ Security ============
    secret_key: SecretStr = Field(
        default="CHANGE_ME_IN_PRODUCTION_32_CHARS_MIN",
        description="Secret key for JWT signing",
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # API Keys for webhook signing
    webhook_secret: SecretStr | None = None

    # CORS
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # ============ Database ============
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://localhost:5432/sentibridge",
        description="PostgreSQL connection URL",
    )
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # ============ Blockchain ============
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon mainnet RPC URL",
    )
    oracle_contract_address: str = Field(
        default="0x" + "0" * 40,
        description="Oracle contract address",
    )

    # ============ Rate Limiting ============
    # Free tier
    free_rate_limit: int = 100  # requests per day
    free_tokens_limit: int = 5  # max tokens to query

    # Basic tier
    basic_rate_limit: int = 1000  # requests per day
    basic_tokens_limit: int = 20

    # Pro tier
    pro_rate_limit: int = 10000  # requests per day
    pro_tokens_limit: int = 100

    # Enterprise tier
    enterprise_rate_limit: int = 100000  # requests per day
    enterprise_tokens_limit: int = -1  # unlimited

    # ============ Monitoring ============
    sentry_dsn: str | None = None
    prometheus_enabled: bool = True

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment == Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
