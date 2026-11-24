"""Runtime configuration, read from environment variables.

Only PUBLIC_URL is required in production; everything else has a safe default.
See docs/configuration.md for the full reference.
"""

import logging
import os
from functools import lru_cache
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

APP_NAME = "pomale"

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Raised when the configuration cannot work; the message is shown to the operator."""


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def get_database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:////data/habits.db")


def get_public_url() -> str:
    """External base URL, e.g. https://habits.example.org (no path)."""
    value = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
    if not value:
        raise ConfigError("PUBLIC_URL is not set, e.g. PUBLIC_URL=https://habits.example.org")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ConfigError(f"PUBLIC_URL must start with http:// or https:// (got {value!r})")
    if parts.path not in {"", "/"}:
        raise ConfigError("PUBLIC_URL must not contain a path; serving under a sub-path is not supported")
    return f"{parts.scheme}://{parts.netloc}"


def get_allowed_origins() -> list[str]:
    """Origins allowed for state-changing requests: PUBLIC_URL plus optional CORS_ORIGINS."""
    origins = [get_public_url()]
    extra = os.getenv("CORS_ORIGINS", "")
    origins += [origin.strip().rstrip("/") for origin in extra.split(",") if origin.strip()]
    return origins


def csrf_enabled() -> bool:
    return env_bool("CSRF_PROTECTION", True)


def cookie_secure() -> bool:
    """Secure cookies unless explicitly disabled; defaults to on for https PUBLIC_URL."""
    if os.getenv("COOKIE_SECURE", "").strip():
        return env_bool("COOKIE_SECURE")
    return get_public_url().startswith("https://")


_legacy_warned = False


def get_default_timezone_name() -> str:
    global _legacy_warned
    value = os.getenv("DEFAULT_TIMEZONE", "").strip()
    if not value:
        legacy = os.getenv("TRACKER_TZ", "").strip()
        if legacy:
            if not _legacy_warned:
                logger.warning("TRACKER_TZ is deprecated, use DEFAULT_TIMEZONE instead")
                _legacy_warned = True
            value = legacy
    return value or "UTC"


@lru_cache
def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"Unknown time zone {name!r} in DEFAULT_TIMEZONE") from exc


def get_default_timezone() -> ZoneInfo:
    return _zone(get_default_timezone_name())


def validate() -> None:
    """Fail fast at startup with a readable message instead of on the first request."""
    get_public_url()
    get_default_timezone()
