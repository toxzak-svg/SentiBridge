"""
Secure secrets management.

Supports multiple secret providers:
- Environment variables (development only)
- AWS Secrets Manager (production)
- HashiCorp Vault (alternative production)

Security principles:
- Secrets never logged
- Secrets cleared from memory when possible
- Minimal secret exposure time
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.config import Environment, get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SecretsProvider(str, Enum):
    """Supported secrets providers."""

    ENVIRONMENT = "environment"
    AWS_SECRETS_MANAGER = "aws"
    HASHICORP_VAULT = "vault"


@dataclass(frozen=True)
class SecureCredentials:
    """
    Container for all required credentials.

    Using frozen dataclass to prevent accidental modification.
    """

    twitter_bearer_token: str | None
    discord_bot_token: str | None
    telegram_bot_token: str | None
    oracle_private_key: str | None
    database_url: str
    redis_url: str


class BaseSecretsProvider(ABC):
    """Abstract base class for secrets providers."""

    @abstractmethod
    async def get_credentials(self) -> SecureCredentials:
        """Retrieve all credentials from the secrets store."""
        pass

    @abstractmethod
    async def get_secret(self, key: str) -> str | None:
        """Retrieve a single secret by key."""
        pass


class EnvironmentSecretsProvider(BaseSecretsProvider):
    """
    Load secrets from environment variables.

    WARNING: Only for development! Not suitable for production.
    """

    async def get_credentials(self) -> SecureCredentials:
        """Load credentials from environment."""
        settings = get_settings()

        if settings.is_production:
            logger.warning(
                "Using environment secrets in production is not recommended",
                extra={"environment": settings.environment.value},
            )

        return SecureCredentials(
            twitter_bearer_token=(
                settings.twitter_bearer_token.get_secret_value()
                if settings.twitter_bearer_token
                else None
            ),
            discord_bot_token=(
                settings.discord_bot_token.get_secret_value()
                if settings.discord_bot_token
                else None
            ),
            telegram_bot_token=(
                settings.telegram_bot_token.get_secret_value()
                if settings.telegram_bot_token
                else None
            ),
            oracle_private_key=(
                settings.oracle_private_key.get_secret_value()
                if settings.oracle_private_key
                else None
            ),
            database_url=str(settings.database_url),
            redis_url=str(settings.redis_url),
        )

    async def get_secret(self, key: str) -> str | None:
        """Get a single secret from environment."""
        import os

        return os.environ.get(key)


class AWSSecretsProvider(BaseSecretsProvider):
    """
    Load secrets from AWS Secrets Manager.

    Recommended for production deployments on AWS.
    """

    def __init__(self, region: str, secret_arn: str) -> None:
        self.region = region
        self.secret_arn = secret_arn
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialization of boto3 client."""
        if self._client is None:
            try:
                import boto3

                self._client = boto3.client("secretsmanager", region_name=self.region)
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for AWS Secrets Manager. "
                    "Install with: pip install boto3"
                )
        return self._client

    async def get_credentials(self) -> SecureCredentials:
        """Load credentials from AWS Secrets Manager."""
        import asyncio

        # boto3 is synchronous, run in executor
        loop = asyncio.get_event_loop()
        secrets = await loop.run_in_executor(None, self._fetch_secrets)

        return SecureCredentials(
            twitter_bearer_token=secrets.get("TWITTER_BEARER_TOKEN"),
            discord_bot_token=secrets.get("DISCORD_BOT_TOKEN"),
            telegram_bot_token=secrets.get("TELEGRAM_BOT_TOKEN"),
            oracle_private_key=secrets.get("ORACLE_PRIVATE_KEY"),
            database_url=secrets.get("DATABASE_URL", ""),
            redis_url=secrets.get("REDIS_URL", ""),
        )

    def _fetch_secrets(self) -> dict[str, str]:
        """Synchronous fetch of secrets."""
        client = self._get_client()

        try:
            response = client.get_secret_value(SecretId=self.secret_arn)
            secret_string = response.get("SecretString", "{}")
            return json.loads(secret_string)
        except Exception as e:
            logger.error(
                "Failed to fetch secrets from AWS",
                extra={"secret_arn": self.secret_arn, "error": str(e)},
            )
            raise

    async def get_secret(self, key: str) -> str | None:
        """Get a single secret from AWS Secrets Manager."""
        import asyncio

        loop = asyncio.get_event_loop()
        secrets = await loop.run_in_executor(None, self._fetch_secrets)
        return secrets.get(key)


class VaultSecretsProvider(BaseSecretsProvider):
    """
    Load secrets from HashiCorp Vault.

    Alternative production secrets provider.
    """

    def __init__(self, vault_url: str, vault_token: str, secret_path: str) -> None:
        self.vault_url = vault_url
        self.vault_token = vault_token
        self.secret_path = secret_path
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy initialization of hvac client."""
        if self._client is None:
            try:
                import hvac

                self._client = hvac.Client(url=self.vault_url, token=self.vault_token)
                if not self._client.is_authenticated():
                    raise RuntimeError("Vault authentication failed")
            except ImportError:
                raise RuntimeError(
                    "hvac is required for HashiCorp Vault. " "Install with: pip install hvac"
                )
        return self._client

    async def get_credentials(self) -> SecureCredentials:
        """Load credentials from HashiCorp Vault."""
        import asyncio

        loop = asyncio.get_event_loop()
        secrets = await loop.run_in_executor(None, self._fetch_secrets)

        return SecureCredentials(
            twitter_bearer_token=secrets.get("TWITTER_BEARER_TOKEN"),
            discord_bot_token=secrets.get("DISCORD_BOT_TOKEN"),
            telegram_bot_token=secrets.get("TELEGRAM_BOT_TOKEN"),
            oracle_private_key=secrets.get("ORACLE_PRIVATE_KEY"),
            database_url=secrets.get("DATABASE_URL", ""),
            redis_url=secrets.get("REDIS_URL", ""),
        )

    def _fetch_secrets(self) -> dict[str, str]:
        """Synchronous fetch of secrets."""
        client = self._get_client()

        try:
            response = client.secrets.kv.v2.read_secret_version(path=self.secret_path)
            return response["data"]["data"]
        except Exception as e:
            logger.error(
                "Failed to fetch secrets from Vault",
                extra={"secret_path": self.secret_path, "error": str(e)},
            )
            raise

    async def get_secret(self, key: str) -> str | None:
        """Get a single secret from Vault."""
        import asyncio

        loop = asyncio.get_event_loop()
        secrets = await loop.run_in_executor(None, self._fetch_secrets)
        return secrets.get(key)


class SecretsManager:
    """
    Factory for creating appropriate secrets provider.

    Automatically selects provider based on environment and configuration.
    """

    _instance: BaseSecretsProvider | None = None

    @classmethod
    def get_provider(cls) -> BaseSecretsProvider:
        """Get the appropriate secrets provider."""
        if cls._instance is not None:
            return cls._instance

        settings = get_settings()

        if settings.environment == Environment.PRODUCTION and settings.aws_secrets_arn:
            logger.info("Using AWS Secrets Manager")
            cls._instance = AWSSecretsProvider(
                region=settings.aws_region,
                secret_arn=settings.aws_secrets_arn,
            )
        else:
            if settings.is_production:
                logger.warning("Production environment using environment secrets")
            else:
                logger.info("Using environment variables for secrets")
            cls._instance = EnvironmentSecretsProvider()

        return cls._instance

    @classmethod
    async def get_credentials(cls) -> SecureCredentials:
        """Convenience method to get credentials."""
        provider = cls.get_provider()
        return await provider.get_credentials()
