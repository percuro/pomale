"""An OpenID provider in the test process, plugged into OidcClient as its HTTP transport."""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
from typing import Any

from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey

from app.services.oidc_client import OidcError

ISSUER = "https://idp.test"
CLIENT_ID = "pomale"
CLIENT_SECRET = "client-secret-for-tests"


class FakeProvider:
    def __init__(self, issuer: str = ISSUER, clock=time.time):
        self.issuer = issuer
        self.clock = clock
        self.key = RSAKey.generate_key(2048, parameters={"kid": "k1"}, private=True)
        self.published_keys = [self.key]
        self.codes: dict[str, dict[str, Any]] = {}
        self.access_tokens: dict[str, str] = {}
        self.users: dict[str, dict[str, Any]] = {}
        # Test switches
        self.down = False
        self.discovery_overrides: dict[str, Any] = {}
        self.claim_overrides: dict[str, Any] = {}
        self.userinfo_overrides: dict[str, Any] = {}
        self.signing_alg = "RS256"
        self.requests: list[tuple[str, str]] = []

    def add_user(self, subject: str, **claims) -> None:
        self.users[subject] = {"sub": subject, **claims}

    def rotate_key(self) -> None:
        self.key = RSAKey.generate_key(2048, parameters={"kid": f"k{len(self.published_keys) + 1}"}, private=True)
        self.published_keys.append(self.key)

    # --- What the browser does at the provider ------------------------------

    def sign_in(self, authorize_url: str, subject: str, auth_time: float | None = None) -> dict[str, str]:
        """Follow the authorization URL as a person signing in; returns the callback query (code, state)."""
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(authorize_url).query))
        assert query["response_type"] == "code" and query["code_challenge_method"] == "S256", query
        code = secrets.token_urlsafe(16)
        self.codes[code] = {
            "subject": subject,
            "nonce": query["nonce"],
            "challenge": query["code_challenge"],
            "redirect_uri": query["redirect_uri"],
            "client_id": query["client_id"],
            "auth_time": int(auth_time if auth_time is not None else self.clock()),
            "query": query,
        }
        return {"code": code, "state": query["state"]}

    # --- Transport ----------------------------------------------------------

    def __call__(self, method: str, url: str, data: dict | None, headers: dict) -> tuple[int, bytes]:
        self.requests.append((method, url))
        if self.down:
            raise OidcError("oidc.provider_unavailable", "connection refused")
        path = urllib.parse.urlsplit(url).path
        if path == "/.well-known/openid-configuration":
            return self._json(200, self.discovery())
        if path == "/jwks":
            return self._json(200, {"keys": [key.as_dict(private=False) for key in self.published_keys]})
        if path == "/token" and method == "POST":
            return self._token(data or {}, headers)
        if path == "/userinfo":
            return self._userinfo(headers)
        return self._json(404, {"error": "not_found"})

    def discovery(self) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "jwks_uri": f"{self.issuer}/jwks",
            "userinfo_endpoint": f"{self.issuer}/userinfo",
            "id_token_signing_alg_values_supported": ["RS256"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post", "none"],
            **self.discovery_overrides,
        }

    def _token(self, data: dict, headers: dict) -> tuple[int, bytes]:
        grant = self.codes.pop(data.get("code", ""), None)
        if grant is None or data.get("grant_type") != "authorization_code":
            return self._json(400, {"error": "invalid_grant"})
        if data.get("redirect_uri") != grant["redirect_uri"]:
            return self._json(400, {"error": "invalid_grant"})
        verifier = data.get("code_verifier", "")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if challenge != grant["challenge"]:
            return self._json(400, {"error": "invalid_grant", "error_description": "PKCE"})
        authorization = headers.get("Authorization", "")
        if authorization.startswith("Basic "):
            client_id, _, secret = base64.b64decode(authorization[6:]).decode().partition(":")
            client_id, secret = urllib.parse.unquote(client_id), urllib.parse.unquote(secret)
        else:
            client_id, secret = data.get("client_id", ""), data.get("client_secret")
        if client_id != grant["client_id"] or (secret is not None and secret != CLIENT_SECRET):
            return self._json(401, {"error": "invalid_client"})
        subject = grant["subject"]
        now = int(self.clock())
        claims = {
            "iss": self.issuer,
            "sub": subject,
            "aud": client_id,
            "exp": now + 300,
            "iat": now,
            "nonce": grant["nonce"],
            "auth_time": grant["auth_time"],
            **self.claim_overrides,
        }
        claims = {name: value for name, value in claims.items() if value is not None}
        access_token = secrets.token_urlsafe(16)
        self.access_tokens[access_token] = subject
        return self._json(
            200, {"id_token": self.id_token(claims), "access_token": access_token, "token_type": "Bearer"}
        )

    def id_token(self, claims: dict) -> str:
        if self.signing_alg == "HS256":
            return jwt.encode({"alg": "HS256"}, claims, OctKey.import_key(CLIENT_SECRET.encode() * 2), ["HS256"])
        return jwt.encode({"alg": self.signing_alg, "kid": self.key.kid}, claims, self.key, [self.signing_alg])

    def _userinfo(self, headers: dict) -> tuple[int, bytes]:
        token = headers.get("Authorization", "").removeprefix("Bearer ")
        subject = self.access_tokens.get(token)
        if subject is None:
            return self._json(401, {"error": "invalid_token"})
        return self._json(200, {**self.users.get(subject, {"sub": subject}), **self.userinfo_overrides})

    @staticmethod
    def _json(status: int, payload: dict) -> tuple[int, bytes]:
        return status, json.dumps(payload).encode()
