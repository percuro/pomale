"""VAPID (RFC 8292): a short-lived ES256 JWT per push service, signed with the instance key."""

import time
from collections.abc import Callable
from urllib.parse import urlsplit

from joserfc import jwt
from joserfc.jwk import ECKey

from app.services.webpush.keys import VapidKeys

TOKEN_LIFETIME = 12 * 3600
# Reuse a token for an hour; push services accept up to 24 h
CACHE_SECONDS = 3600


def audience(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return f"{parts.scheme}://{parts.netloc}"


class Vapid:
    def __init__(self, keys: VapidKeys, contact: str, clock: Callable[[], float] = time.time):
        self.keys = keys
        self.contact = contact
        self.clock = clock
        self._jwk = ECKey.import_key(keys.private_pem)
        self._cache: dict[str, tuple[str, float]] = {}

    def authorization(self, endpoint: str) -> str:
        aud = audience(endpoint)
        now = self.clock()
        cached = self._cache.get(aud)
        if cached and cached[1] > now:
            token = cached[0]
        else:
            claims = {"aud": aud, "exp": int(now) + TOKEN_LIFETIME, "sub": self.contact}
            token = jwt.encode({"alg": "ES256", "typ": "JWT"}, claims, self._jwk)
            self._cache[aud] = (token, now + CACHE_SECONDS)
        return f"vapid t={token}, k={self.keys.public_key}"
