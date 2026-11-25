import os
import unittest
from unittest import mock

from app import config


class ConfigTest(unittest.TestCase):
    def env(self, **values):
        base = {
            "PUBLIC_URL": "",
            "CORS_ORIGINS": "",
            "COOKIE_SECURE": "",
            "CSRF_PROTECTION": "",
            "DEFAULT_TIMEZONE": "",
            "TRACKER_TZ": "",
            "OIDC_ISSUER": "",
            "OIDC_CLIENT_ID": "",
            "OIDC_CLIENT_SECRET": "",
            "OIDC_SCOPES": "",
            "OIDC_LABEL": "",
            "OIDC_AUTO_CREATE": "",
            "PASSWORD_LOGIN": "",
        }
        base.update(values)
        return mock.patch.dict(os.environ, base)

    def test_oidc_is_off_by_default(self):
        with self.env(PUBLIC_URL="https://habits.example.org"):
            self.assertIsNone(config.get_oidc_settings())
            self.assertTrue(config.password_login_enabled())
            config.validate()

    def test_oidc_settings(self):
        with self.env(
            PUBLIC_URL="https://habits.example.org",
            OIDC_ISSUER="https://auth.example.org",
            OIDC_CLIENT_ID="pomale",
            OIDC_SCOPES="openid  email",
            OIDC_LABEL="Authelia",
            OIDC_AUTO_CREATE="on",
        ):
            settings = config.get_oidc_settings()
            self.assertEqual(
                (settings.issuer, settings.client_id, settings.client_secret, settings.scopes, settings.label),
                ("https://auth.example.org", "pomale", None, "openid email", "Authelia"),
            )
            self.assertTrue(settings.auto_create)
            self.assertEqual(config.get_oidc_redirect_uri(), "https://habits.example.org/api/v1/auth/oidc/callback")
            config.validate()

    def test_oidc_misconfiguration(self):
        cases = (
            {"OIDC_ISSUER": "https://auth.example.org"},
            {"OIDC_ISSUER": "auth.example.org", "OIDC_CLIENT_ID": "pomale"},
            {"OIDC_ISSUER": "https://auth.example.org", "OIDC_CLIENT_ID": "pomale", "OIDC_SCOPES": "email"},
            {"PASSWORD_LOGIN": "off"},
        )
        for values in cases:
            with self.env(PUBLIC_URL="https://habits.example.org", **values), self.assertRaises(config.ConfigError):
                config.validate()

    def test_password_login_off_with_oidc(self):
        with self.env(
            PUBLIC_URL="https://habits.example.org",
            OIDC_ISSUER="https://auth.example.org",
            OIDC_CLIENT_ID="pomale",
            PASSWORD_LOGIN="off",
        ):
            config.validate()
            self.assertFalse(config.password_login_enabled())

    def test_plain_http_issuer_only_warns(self):
        with (
            self.env(
                PUBLIC_URL="https://habits.example.org", OIDC_ISSUER="http://auth.example.org", OIDC_CLIENT_ID="pomale"
            ),
            self.assertLogs("app.config", "WARNING"),
        ):
            config.validate()
        with self.env(PUBLIC_URL="http://localhost:8000", OIDC_ISSUER="http://localhost:5556/dex", OIDC_CLIENT_ID="p"):
            with self.assertNoLogs("app.config", "WARNING"):
                config.validate()

    def test_public_url_required(self):
        with self.env(), self.assertRaises(config.ConfigError):
            config.validate()

    def test_public_url_validation(self):
        for bad in ("habits.example.org", "ftp://x.org", "https://x.org/sub"):
            with self.env(PUBLIC_URL=bad), self.assertRaises(config.ConfigError):
                config.get_public_url()
        with self.env(PUBLIC_URL="https://habits.example.org/"):
            self.assertEqual(config.get_public_url(), "https://habits.example.org")

    def test_secure_defaults(self):
        with self.env(PUBLIC_URL="https://habits.example.org"):
            self.assertTrue(config.csrf_enabled())
            self.assertTrue(config.cookie_secure())
            self.assertEqual(config.get_allowed_origins(), ["https://habits.example.org"])
        with self.env(PUBLIC_URL="http://localhost:8000"):
            self.assertFalse(config.cookie_secure())
        with self.env(
            PUBLIC_URL="http://localhost:8000", COOKIE_SECURE="true", CORS_ORIGINS="http://a.test, http://b.test/"
        ):
            self.assertTrue(config.cookie_secure())
            self.assertEqual(config.get_allowed_origins(), ["http://localhost:8000", "http://a.test", "http://b.test"])

    def test_timezone_default_alias_and_validation(self):
        with self.env():
            self.assertEqual(config.get_default_timezone_name(), "UTC")
        with self.env(TRACKER_TZ="Europe/Berlin"):
            self.assertEqual(config.get_default_timezone_name(), "Europe/Berlin")
        with self.env(DEFAULT_TIMEZONE="America/New_York", TRACKER_TZ="Europe/Berlin"):
            self.assertEqual(config.get_default_timezone_name(), "America/New_York")
        with self.env(PUBLIC_URL="https://x.org", DEFAULT_TIMEZONE="Mars/Base"), self.assertRaises(config.ConfigError):
            config.validate()


class AcceptLanguageTest(unittest.TestCase):
    def test_picks_the_best_supported_language(self):
        from app.services.i18n import accept_language

        self.assertEqual(accept_language("de-AT,de;q=0.9,en;q=0.8"), "de")
        self.assertEqual(accept_language("fr-FR,fr;q=0.9,en;q=0.7,de;q=0.8"), "de")
        self.assertEqual(accept_language("en-US"), "en")
        self.assertIsNone(accept_language("fr,it"))
        self.assertIsNone(accept_language("de;q=0"))
        self.assertIsNone(accept_language(None))


if __name__ == "__main__":
    unittest.main()
