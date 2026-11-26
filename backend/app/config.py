"""Runtime configuration, read from environment variables.

Only PUBLIC_URL is required in production; everything else has a safe default.
See docs/configuration.md for the full reference.
"""

import logging
import os
from dataclasses import dataclass
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


REGISTRATION_MODES = ("invite", "open")


def get_registration_mode() -> str:
    """invite (default): accounts only through an admin's invitation; open: anyone may register."""
    value = os.getenv("REGISTRATION", "").strip().lower() or "invite"
    if value not in REGISTRATION_MODES:
        raise ConfigError(f"REGISTRATION must be 'invite' or 'open' (got {value!r})")
    return value


def get_invite_expiry_days() -> int:
    return env_positive_int("INVITE_EXPIRY_DAYS", 7)


def get_audit_retention_days() -> int:
    return env_positive_int("AUDIT_RETENTION_DAYS", 180)


@dataclass(frozen=True)
class OidcSettings:
    issuer: str
    client_id: str
    # None = public client: PKCE only, no client authentication at the token endpoint
    client_secret: str | None
    scopes: str
    # Name on the sign-in button, e.g. "Authelia"; None = a translated "single sign-on"
    label: str | None
    auto_create: bool


def get_oidc_settings() -> OidcSettings | None:
    """None when OIDC is not configured (OIDC_ISSUER empty)."""
    issuer = os.getenv("OIDC_ISSUER", "").strip()
    if not issuer:
        return None
    parts = urlsplit(issuer)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ConfigError(f"OIDC_ISSUER must start with https:// (got {issuer!r})")
    client_id = os.getenv("OIDC_CLIENT_ID", "").strip()
    if not client_id:
        raise ConfigError("OIDC_CLIENT_ID is required when OIDC_ISSUER is set")
    scopes = " ".join(os.getenv("OIDC_SCOPES", "").split()) or "openid profile email"
    if "openid" not in scopes.split():
        raise ConfigError(f"OIDC_SCOPES must contain openid (got {scopes!r})")
    return OidcSettings(
        # Compared exactly with the provider's "issuer"; only a trailing slash is forgiven
        issuer=issuer,
        client_id=client_id,
        client_secret=os.getenv("OIDC_CLIENT_SECRET", "").strip() or None,
        scopes=scopes,
        label=os.getenv("OIDC_LABEL", "").strip()[:40] or None,
        auto_create=env_bool("OIDC_AUTO_CREATE", False),
    )


def password_login_enabled() -> bool:
    """PASSWORD_LOGIN=off: accounts sign in, register and are set up through OIDC only."""
    return env_bool("PASSWORD_LOGIN", True)


def get_oidc_redirect_uri() -> str:
    return f"{get_public_url()}/api/v1/auth/oidc/callback"


def api_docs_enabled() -> bool:
    """API_DOCS=false hides /api/openapi.json (the API itself is unaffected)."""
    return env_bool("API_DOCS", True)


def push_enabled() -> bool:
    """PUSH_ENABLED=false turns reminders off: no scheduler, no push endpoints, no UI."""
    return env_bool("PUSH_ENABLED", True)


def get_push_contact() -> str:
    """VAPID "sub": how push services can reach the operator. Apple requires mailto: or https://."""
    value = os.getenv("PUSH_CONTACT", "").strip()
    if not value:
        return get_public_url()
    if not (value.startswith("mailto:") or value.startswith("https://")):
        raise ConfigError(f"PUSH_CONTACT must start with mailto: or https:// (got {value!r})")
    return value


# Hosts of the push services that browsers use. Push subscriptions with any other endpoint are
# rejected, so the server never sends requests to addresses a user made up.
DEFAULT_PUSH_HOSTS = (
    "fcm.googleapis.com",  # Chrome, Edge on Android, Opera, Samsung Internet
    "*.push.services.mozilla.com",  # Firefox
    "*.notify.windows.com",  # Edge on Windows
    "*.push.apple.com",  # Safari, iPhone and iPad home-screen apps
)


def get_push_allowed_hosts() -> tuple[str, ...]:
    """The defaults plus PUSH_ALLOWED_HOSTS (comma-separated; "*.example.org" matches subdomains)."""
    extra = os.getenv("PUSH_ALLOWED_HOSTS", "")
    return DEFAULT_PUSH_HOSTS + tuple(host.strip().lower() for host in extra.split(",") if host.strip())


def _is_local(host: str) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost")


def validate() -> None:
    """Fail fast at startup with a readable message instead of on the first request."""
    get_public_url()
    get_default_timezone()
    get_registration_mode()
    if push_enabled():
        get_push_contact()
    oidc = get_oidc_settings()
    if not password_login_enabled() and oidc is None:
        raise ConfigError("PASSWORD_LOGIN=off needs OIDC: set OIDC_ISSUER and OIDC_CLIENT_ID")
    if oidc is not None:
        # The provider is not contacted here: pomale starts even while it is down
        host = urlsplit(oidc.issuer).hostname or ""
        if oidc.issuer.startswith("http://") and not _is_local(host):
            logger.warning("OIDC_ISSUER uses http://; tokens and codes travel unencrypted")
