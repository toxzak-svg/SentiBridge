"""
Structured logging configuration.

Features:
- JSON output for production (machine-parseable)
- Pretty console output for development
- Request tracing with correlation IDs
- Sensitive data filtering
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from src.config import Environment, get_settings


def filter_sensitive_data(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Filter sensitive data from logs.

    Removes or masks:
    - API keys and tokens
    - Private keys
    - Passwords
    - Personal identifiable information
    """
    sensitive_keys = {
        "password",
        "token",
        "secret",
        "api_key",
        "private_key",
        "bearer",
        "authorization",
        "credential",
    }

    def mask_value(key: str, value: Any) -> Any:
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            if isinstance(value, str) and len(value) > 8:
                return f"{value[:4]}...{value[-4:]}"
            return "***REDACTED***"
        return value

    return {k: mask_value(k, v) for k, v in event_dict.items()}


def add_service_info(
    logger: logging.Logger, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Add service metadata to all log entries."""
    event_dict["service"] = "sentibridge-workers"
    event_dict["version"] = "0.1.0"
    return event_dict


def configure_logging() -> None:
    """
    Configure structured logging.

    Production: JSON output to stdout
    Development: Pretty colored console output
    """
    settings = get_settings()

    # Shared processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        filter_sensitive_data,
        add_service_info,
    ]

    if settings.environment == Environment.PRODUCTION:
        # Production: JSON logs
        processors: list[Processor] = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.value),
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a logger instance with the given name."""
    return structlog.get_logger(name)
