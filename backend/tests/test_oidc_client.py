import base64
import json
import unittest

from app.config import OidcSettings
from app.services.oidc_client import OidcClient, OidcError, pkce_pair
from tests.oidc_fake import CLIENT_ID, CLIENT_SECRET, ISSUER, FakeProvider

REDIRECT_URI = "https://habits.test/api/v1/auth/oidc/callback"


class Clock:
    def __init__(self, now: float = 1_800_000_000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def settings(**changes) -> OidcSettings:
    values = {
        "issuer": ISSUER,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": "openid profile email",
        "label": None,
        "auto_create": False,
    }
    values.update(changes)
    return OidcSettings(**values)


class OidcClientTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.provider = FakeProvider(clock=self.clock)
        self.provider.add_user("user-1", email="anna@example.org", preferred_username="anna", name="Anna")
        self.client = OidcClient(settings(), transport=self.provider, clock=self.clock)

    def sign_in(self, subject="user-1", reauth=False, client=None, **auth):
        client = client or self.client
        verifier, challenge = pkce_pair()
        url = client.authorization_url(
            state="state-1", nonce="nonce-1", code_challenge=challenge, redirect_uri=REDIRECT_URI, reauth=reauth
        )
        callback = self.provider.sign_in(url, subject, **auth)
        return client.authenticate(
            code=callback["code"], code_verifier=verifier, nonce="nonce-1", redirect_uri=REDIRECT_URI
        ), url

    def assertFails(self, code="oidc.invalid_response", **kwargs):
        with self.assertRaises(OidcError) as context:
            self.sign_in(**kwargs)
        self.assertEqual(context.exception.code, code, context.exception.message)

    def test_valid_flow_with_userinfo_claims(self):
        identity, url = self.sign_in()
        self.assertEqual(
            (identity.issuer, identity.subject, identity.email, identity.preferred_username, identity.name),
            (ISSUER, "user-1", "anna@example.org", "anna", "Anna"),
        )
        self.assertIn("scope=openid+profile+email", url)
        self.assertNotIn("prompt=", url)

    def test_reauth_asks_the_provider_to_check_again(self):
        _identity, url = self.sign_in(reauth=True)
        self.assertIn("prompt=login", url)
        self.assertNotIn("max_age", url)

    def test_old_auth_time_fails_reauth(self):
        verifier, challenge = pkce_pair()
        url = self.client.authorization_url(
            state="s", nonce="n", code_challenge=challenge, redirect_uri=REDIRECT_URI, reauth=True
        )
        callback = self.provider.sign_in(url, "user-1", auth_time=self.clock.now - 3600)
        with self.assertRaises(OidcError) as context:
            self.client.authenticate(
                code=callback["code"],
                code_verifier=verifier,
                nonce="n",
                redirect_uri=REDIRECT_URI,
                authenticated_after=self.clock.now,
            )
        self.assertEqual(context.exception.code, "oidc.reauth_failed")

    def test_public_client_sends_no_secret(self):
        client = OidcClient(settings(client_secret=None), transport=self.provider, clock=self.clock)
        identity, _url = self.sign_in(client=client)
        self.assertEqual(identity.subject, "user-1")

    def test_client_secret_post_when_basic_is_not_offered(self):
        self.provider.discovery_overrides = {"token_endpoint_auth_methods_supported": ["client_secret_post"]}
        identity, _url = self.sign_in()
        self.assertEqual(identity.subject, "user-1")

    def test_wrong_issuer_in_discovery(self):
        self.provider.discovery_overrides = {"issuer": "https://evil.test"}
        with self.assertRaises(OidcError) as context:
            self.client.metadata()
        self.assertEqual(context.exception.code, "oidc.invalid_response")

    def test_trailing_slash_on_issuer_is_forgiven(self):
        client = OidcClient(settings(issuer=ISSUER + "/"), transport=self.provider, clock=self.clock)
        self.assertEqual(client.metadata().issuer, ISSUER)

    def test_wrong_claims_are_rejected(self):
        for overrides in (
            {"iss": "https://evil.test"},
            {"aud": "someone-else"},
            {"aud": [CLIENT_ID, "someone-else"]},
            {"nonce": "replayed"},
            {"exp": int(self.clock.now) - 120},
            {"iat": None},
            {"sub": None},
        ):
            with self.subTest(overrides=overrides):
                self.provider.claim_overrides = overrides
                self.assertFails()

    def test_several_audiences_with_matching_azp(self):
        self.provider.claim_overrides = {"aud": [CLIENT_ID, "other"], "azp": CLIENT_ID}
        identity, _url = self.sign_in()
        self.assertEqual(identity.subject, "user-1")

    def test_hmac_and_none_are_refused(self):
        self.provider.signing_alg = "HS256"
        self.assertFails()
        self.provider.signing_alg = "RS256"
        self.provider.discovery_overrides = {"id_token_signing_alg_values_supported": ["none", "HS256"]}
        fresh = OidcClient(settings(), transport=self.provider, clock=self.clock)
        with self.assertRaises(OidcError):
            fresh.metadata()

    def test_unsigned_token_is_refused(self):
        header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
        claims = {"iss": ISSUER, "sub": "user-1", "aud": CLIENT_ID, "exp": 2e9, "iat": 1.8e9, "nonce": "n"}
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        with self.assertRaises(OidcError):
            self.client.validate_id_token(f"{header}.{payload}.", "n")

    def test_key_rotation_fetches_keys_again(self):
        self.sign_in()
        jwks_requests = sum(1 for _m, url in self.provider.requests if url.endswith("/jwks"))
        self.provider.rotate_key()
        self.clock.now += 120
        identity, _url = self.sign_in()
        self.assertEqual(identity.subject, "user-1")
        self.assertEqual(sum(1 for _m, url in self.provider.requests if url.endswith("/jwks")), jwks_requests + 1)

    def test_unknown_key_is_refetched_at_most_once_a_minute(self):
        self.sign_in()
        self.provider.rotate_key()
        self.provider.published_keys = self.provider.published_keys[:1]
        self.assertFails()
        before = len(self.provider.requests)
        self.assertFails()
        # Second failure within the minute: no new JWKS download
        self.assertFalse(any(url.endswith("/jwks") for _m, url in self.provider.requests[before:]))

    def test_userinfo_for_another_subject(self):
        self.provider.userinfo_overrides = {"sub": "user-2"}
        self.assertFails()

    def test_provider_unreachable(self):
        self.provider.down = True
        with self.assertRaises(OidcError) as context:
            self.client.metadata()
        self.assertEqual(context.exception.code, "oidc.provider_unavailable")

    def test_discovery_is_cached_for_an_hour(self):
        self.client.metadata()
        self.client.metadata()
        discovery = [url for _m, url in self.provider.requests if "openid-configuration" in url]
        self.assertEqual(len(discovery), 1)
        self.clock.now += 3601
        self.client.metadata()
        discovery = [url for _m, url in self.provider.requests if "openid-configuration" in url]
        self.assertEqual(len(discovery), 2)

    def test_wrong_code_verifier(self):
        _verifier, challenge = pkce_pair()
        url = self.client.authorization_url(
            state="s", nonce="n", code_challenge=challenge, redirect_uri=REDIRECT_URI, reauth=False
        )
        callback = self.provider.sign_in(url, "user-1")
        with self.assertRaises(OidcError) as context:
            self.client.authenticate(code=callback["code"], code_verifier="wrong", nonce="n", redirect_uri=REDIRECT_URI)
        self.assertEqual(context.exception.code, "oidc.invalid_response")


if __name__ == "__main__":
    unittest.main()
