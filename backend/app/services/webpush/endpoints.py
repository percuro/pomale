"""Checks for what a browser sends when it subscribes."""

from urllib.parse import urlsplit

from app.config import get_push_allowed_hosts
from app.services.webpush.encoding import b64url_decode

ENDPOINT_MAX_LENGTH = 1000


def _host_allowed(host: str, port: int | None, allowed: tuple[str, ...]) -> bool:
    for entry in allowed:
        name, _, entry_port = entry.partition(":")
        wanted_port = int(entry_port) if entry_port.isdigit() else 443
        if (port or 443) != wanted_port:
            continue
        if name.startswith("*."):
            if host.endswith(name[1:]) and host != name[2:]:
                return True
        elif host == name:
            return True
    return False


def endpoint_allowed(url: str) -> bool:
    """https only, on a known push service (see config.DEFAULT_PUSH_HOSTS), no credentials."""
    if len(url) > ENDPOINT_MAX_LENGTH:
        return False
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return False
    return _host_allowed(host, port, get_push_allowed_hosts())


def decode_keys(p256dh: str, auth: str) -> tuple[bytes, bytes]:
    """The subscription keys as bytes; ValueError if they are not a P-256 point and a 16-byte secret."""
    public = b64url_decode(p256dh)
    secret = b64url_decode(auth)
    if len(public) != 65 or public[0] != 4 or len(secret) != 16:
        raise ValueError("invalid subscription keys")
    return public, secret
