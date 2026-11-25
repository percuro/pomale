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
        }
        base.update(values)
        return mock.patch.dict(os.environ, base)

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
