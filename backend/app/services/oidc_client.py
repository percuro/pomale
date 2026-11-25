"""OpenID Connect relying party: Authorization Code flow with PKCE against exactly one provider.

What is checked, and why:
- The discovery document's "issuer" must equal OIDC_ISSUER (mix-up protection).
- The ID token must be signed with an asymmetric algorithm the provider announces; "none" and
  HMAC (HS*) are refused, so a leaked client secret cannot forge tokens.
- iss, aud (and azp with several audiences), exp, iat with 60 s leeway, nonce, and a subject.
- Userinfo (Authelia sends e-mail and username only there) must name the same subject.

Discovery and keys are cached in memory; the keys are fetched again when a token names an
unknown key id (key rotation), at most once a minute. HTTP goes through urllib, so a private CA
works with SSL_CERT_FILE like any other OpenSSL program.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet

from app.config import OidcSettings

ASYMMETRIC_ALGORITHMS = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)
DISCOVERY_TTL_SECONDS = 60 * 60
JWKS_REFRESH_MIN_SECONDS = 60
LEEWAY_SECONDS = 60
HTTP_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1024 * 1024


class OidcError(Exception):
    """A sign-in at the provider failed; `code` is shown to the person (translated by the web app)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def unavailable(message: str) -> OidcError:
    return OidcError("oidc.provider_unavailable", message)


def invalid(message: str) -> OidcError:
    return OidcError("oidc.invalid_response", message)


# (method, url, form data or None, headers) -> (status, body)
Transport = Callable[[str, str, dict[str, str] | None, dict[str, str]], tuple[int, bytes]]


def urllib_transport(method: str, url: str, data: dict[str, str] | None, headers: dict[str, str]) -> tuple[int, bytes]:
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={"Accept": "application/json", **headers})
    if body is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310 (https/http only)
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise unavailable(f"{url}: {exc}") from exc


def pkce_pair() -> tuple[str, str]:
    """(code_verifier, S256 code_challenge)."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


@dataclass(frozen=True)
class ProviderMetadata:
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    jwks_uri: str
    userinfo_endpoint: str | None
    algorithms: tuple[str, ...]
    token_auth_methods: tuple[str, ...]


@dataclass(frozen=True)
class Identity:
    """Who the provider says signed in. Only issuer + subject identify an account."""

    issuer: str
    subject: str
    email: str | None = None
    email_verified: bool | None = None
    preferred_username: str | None = None
    name: str | None = None


@dataclass
class _Cache:
    metadata: ProviderMetadata | None = None
    metadata_at: float = 0.0
    keys: KeySet | None = None
    keys_at: float = 0.0
    lock: Lock = field(default_factory=Lock)


def _text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:limit] or None


class OidcClient:
    def __init__(
        self,
        settings: OidcSettings,
        transport: Transport = urllib_transport,
        clock: Callable[[], float] = time.time,
    ):
        self.settings = settings
        self.transport = transport
        self.clock = clock
        self._cache = _Cache()

    # --- HTTP ---------------------------------------------------------------

    def _json(self, method: str, url: str, data: dict[str, str] | None = None, headers: dict | None = None) -> dict:
        status, body = self.transport(method, url, data, headers or {})
        if len(body) > MAX_RESPONSE_BYTES:
            raise invalid(f"{url}: response too large")
        try:
            payload = json.loads(body)
        except ValueError as exc:
            if status >= 500:
                raise unavailable(f"{url}: HTTP {status}") from exc
            raise invalid(f"{url}: HTTP {status}, not JSON") from exc
        if not isinstance(payload, dict):
            raise invalid(f"{url}: expected a JSON object")
        if status >= 500:
            raise unavailable(f"{url}: HTTP {status}")
        if status >= 400:
            error = payload.get("error", "")
            raise invalid(f"{url}: HTTP {status} {error}".strip())
        return payload

    # --- Discovery and keys -------------------------------------------------

    def metadata(self) -> ProviderMetadata:
        cache = self._cache
        with cache.lock:
            if cache.metadata is not None and self.clock() - cache.metadata_at < DISCOVERY_TTL_SECONDS:
                return cache.metadata
        issuer = self.settings.issuer.rstrip("/")
        document = self._json("GET", f"{issuer}/.well-known/openid-configuration")
        announced = str(document.get("issuer", ""))
        if announced.rstrip("/") != issuer:
            raise invalid(f"Discovery issuer {announced!r} does not match OIDC_ISSUER {self.settings.issuer!r}")
        try:
            algorithms = tuple(
                alg
                for alg in document.get("id_token_signing_alg_values_supported", ["RS256"])
                if alg in ASYMMETRIC_ALGORITHMS
            )
            metadata = ProviderMetadata(
                issuer=announced,
                authorization_endpoint=str(document["authorization_endpoint"]),
                token_endpoint=str(document["token_endpoint"]),
                jwks_uri=str(document["jwks_uri"]),
                userinfo_endpoint=str(document["userinfo_endpoint"]) if document.get("userinfo_endpoint") else None,
                algorithms=algorithms,
                token_auth_methods=tuple(
                    document.get("token_endpoint_auth_methods_supported", ["client_secret_basic"])
                ),
            )
        except (KeyError, TypeError) as exc:
            raise invalid(f"Discovery document incomplete: {exc}") from exc
        if not metadata.algorithms:
            raise invalid("The provider announces no asymmetric signing algorithm for ID tokens")
        with cache.lock:
            cache.metadata, cache.metadata_at = metadata, self.clock()
        return metadata

    def _keys(self, refresh: bool = False) -> KeySet:
        cache = self._cache
        with cache.lock:
            fresh_enough = self.clock() - cache.keys_at < JWKS_REFRESH_MIN_SECONDS
            if cache.keys is not None and (not refresh or fresh_enough):
                return cache.keys
        document = self._json("GET", self.metadata().jwks_uri)
        try:
            keys = KeySet.import_key_set(document)
        except (JoseError, ValueError, KeyError, TypeError) as exc:
            raise invalid(f"Unusable JWKS: {exc}") from exc
        with cache.lock:
            cache.keys, cache.keys_at = keys, self.clock()
        return keys

    # --- Flow ---------------------------------------------------------------

    def authorization_url(self, *, state: str, nonce: str, code_challenge: str, redirect_uri: str, reauth: bool) -> str:
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.settings.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if reauth:
            # Ask the provider to really check again, not to reuse its own session. prompt=login is
            # the widely supported way; auth_time is checked in validate_id_token.
            params["prompt"] = "login"
        endpoint = self.metadata().authorization_endpoint
        separator = "&" if "?" in endpoint else "?"
        return endpoint + separator + urllib.parse.urlencode(params)

    def _exchange(self, code: str, code_verifier: str, redirect_uri: str) -> dict:
        metadata = self.metadata()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        headers: dict[str, str] = {}
        secret = self.settings.client_secret
        if secret is None:
            data["client_id"] = self.settings.client_id
        elif (
            "client_secret_basic" in metadata.token_auth_methods
            or "client_secret_post" not in metadata.token_auth_methods
        ):
            pair = f"{urllib.parse.quote(self.settings.client_id, safe='')}:{urllib.parse.quote(secret, safe='')}"
            headers["Authorization"] = "Basic " + base64.b64encode(pair.encode()).decode()
        else:
            data.update(client_id=self.settings.client_id, client_secret=secret)
        tokens = self._json("POST", metadata.token_endpoint, data, headers)
        if not isinstance(tokens.get("id_token"), str):
            raise invalid("Token response without id_token")
        return tokens

    def validate_id_token(self, id_token: str, nonce: str, authenticated_after: float | None = None) -> dict:
        metadata = self.metadata()
        try:
            token = self._decode(id_token, metadata)
        except _UnknownKey:
            token = self._decode(id_token, metadata, refresh=True)
        claims = token.claims
        registry = jwt.JWTClaimsRegistry(
            now=int(self.clock()),
            leeway=LEEWAY_SECONDS,
            iss={"essential": True, "value": metadata.issuer},
            aud={"essential": True, "value": self.settings.client_id},
            sub={"essential": True},
            exp={"essential": True},
            iat={"essential": True},
            nonce={"essential": True, "value": nonce},
        )
        try:
            registry.validate(claims)
        except JoseError as exc:
            raise invalid(f"ID token rejected: {exc}") from exc
        audience = claims.get("aud")
        if isinstance(audience, list) and len(audience) > 1 and claims.get("azp") != self.settings.client_id:
            raise invalid("ID token for several audiences without matching azp")
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise invalid("ID token without subject")
        auth_time = claims.get("auth_time")
        if authenticated_after is not None and isinstance(auth_time, (int, float)):
            if auth_time < authenticated_after - LEEWAY_SECONDS:
                raise OidcError("oidc.reauth_failed", "The provider did not ask for the login again")
        return claims

    def _decode(self, id_token: str, metadata: ProviderMetadata, refresh: bool = False):
        keys = self._keys(refresh=refresh)
        try:
            return jwt.decode(id_token, keys, algorithms=list(metadata.algorithms))
        except JoseError as exc:
            if not refresh and _names_unknown_key(id_token, keys):
                raise _UnknownKey from exc
            raise invalid(f"ID token signature rejected: {exc}") from exc
        except ValueError as exc:
            if not refresh and _names_unknown_key(id_token, keys):
                raise _UnknownKey from exc
            raise invalid(f"ID token unreadable: {exc}") from exc

    def userinfo(self, access_token: str) -> dict:
        endpoint = self.metadata().userinfo_endpoint
        if endpoint is None:
            return {}
        return self._json("GET", endpoint, headers={"Authorization": f"Bearer {access_token}"})

    def authenticate(
        self,
        *,
        code: str,
        code_verifier: str,
        nonce: str,
        redirect_uri: str,
        authenticated_after: float | None = None,
    ) -> Identity:
        """Exchange the code and return the verified identity."""
        tokens = self._exchange(code, code_verifier, redirect_uri)
        claims = self.validate_id_token(tokens["id_token"], nonce, authenticated_after)
        access_token = tokens.get("access_token")
        if isinstance(access_token, str) and access_token:
            info = self.userinfo(access_token)
            if info:
                if info.get("sub") != claims["sub"]:
                    raise invalid("Userinfo names a different subject than the ID token")
                claims = {**info, **claims}
        return Identity(
            issuer=self.metadata().issuer,
            subject=claims["sub"][:255],
            email=_text(claims.get("email"), 255),
            email_verified=claims.get("email_verified") if isinstance(claims.get("email_verified"), bool) else None,
            preferred_username=_text(claims.get("preferred_username"), 80),
            name=_text(claims.get("name"), 80),
        )


class _UnknownKey(Exception):
    pass


def _names_unknown_key(id_token: str, keys: KeySet) -> bool:
    try:
        header = json.loads(base64.urlsafe_b64decode(id_token.split(".")[0] + "=="))
    except (ValueError, IndexError):
        return False
    kid = header.get("kid") if isinstance(header, dict) else None
    return isinstance(kid, str) and all(key.kid != kid for key in keys.keys)


_clients: dict[OidcSettings, OidcClient] = {}
_clients_lock = Lock()


def get_client(settings: OidcSettings) -> OidcClient:
    """One client (and cache) per configuration."""
    with _clients_lock:
        client = _clients.get(settings)
        if client is None:
            client = _clients[settings] = OidcClient(settings)
        return client


def reset_clients() -> None:
    with _clients_lock:
        _clients.clear()
