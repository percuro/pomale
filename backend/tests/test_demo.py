"""DEMO_MODE: sample data, the hourly reset, its safety check and the locked actions."""

import os
import unittest
from datetime import UTC, date, datetime
from unittest import mock

from sqlalchemy import func, select

from app import config
from app.models.audit_event import AuditEvent
from app.models.habit import Checkin, Habit
from app.models.user import User
from app.schemas.export import AccountExport
from app.services import demo_service
from tests.support import ApiTestEnvironment

TODAY = date(2026, 11, 24)


class DemoDataTest(unittest.TestCase):
    def test_sample_data_pass_the_import_checks_and_stay_the_same_for_a_day(self):
        data = demo_service.build_demo(TODAY)
        AccountExport.model_validate(data.model_dump(mode="json"))
        self.assertEqual(data, demo_service.build_demo(TODAY))
        self.assertEqual({h.schedules[-1].goal_type for h in data.habits}, {"days", "weekly_count", "quantity"})
        self.assertTrue(any(len(h.schedules) > 1 for h in data.habits))
        self.assertTrue(data.pauses)
        self.assertTrue(any(c.note for h in data.habits for c in h.checkins))
        latest = max(c.date for h in data.habits for c in h.checkins)
        self.assertEqual(latest, TODAY)

    def test_next_hour(self):
        self.assertEqual(demo_service.seconds_until_next_hour(datetime(2026, 11, 24, 10, 59, 30, tzinfo=UTC)), 31)
        self.assertEqual(demo_service.seconds_until_next_hour(datetime(2026, 11, 24, 11, 0, 0, tzinfo=UTC)), 3601)


class DemoModeTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=TODAY)
        self._demo = mock.patch.dict(os.environ, {"DEMO_MODE": "true"})
        self._demo.start()
        self.reset()
        self.client = self.env.client(demo_service.DEMO_USERNAME, demo_service.DEMO_PASSWORD)

    def tearDown(self):
        self._demo.stop()
        self.env.close()

    def reset(self):
        db = self.env.SessionLocal()
        try:
            demo_service.reset(db, self.env.now)
        finally:
            db.close()

    def count(self, model) -> int:
        db = self.env.SessionLocal()
        try:
            return db.scalar(select(func.count()).select_from(model))
        finally:
            db.close()

    def test_meta_tells_the_login_page(self):
        meta = self.env.client(username=None).get("/v1/meta").json()
        self.assertEqual(meta["demo"], {"username": "demo", "password": demo_service.DEMO_PASSWORD})
        self.assertFalse(meta["setup_needed"])
        self.assertEqual(meta["registration"], "invite")

    def test_today_and_week_show_the_sample_data(self):
        today = self.client.get("/v1/today").json()
        self.assertEqual(today["date"], "2026-11-24")
        self.assertGreater(today["due"], today["done"])
        self.assertGreater(today["done"], 0)
        self.assertEqual(len(self.client.get("/v1/days").json()["habits"]), 6)

    def test_reset_undoes_changes_and_keeps_visitors_signed_in(self):
        habits = self.client.get("/v1/habits").json()
        self.client.post(f"/v1/habits/{habits[0]['id']}/archive")
        self.client.post("/v1/habits", json={"name": "Spam"})
        self.client.patch("/v1/account", json={"locale": "de", "day_end_hour": 3})
        checkins = self.count(Checkin)

        self.reset()

        names = [h["name"] for h in self.client.get("/v1/habits").json()]
        self.assertNotIn("Spam", names)
        self.assertEqual(len(names), 6)
        self.assertEqual(self.count(Checkin), checkins)
        me = self.client.get("/v1/auth/me").json()
        self.assertIsNone(me["locale"])
        self.assertEqual(me["day_end_hour"], 0)
        self.assertEqual(self.count(AuditEvent), 1)  # only the import of the reset

    def test_locked_actions(self):
        habit = self.client.get("/v1/habits").json()[0]
        locked = [
            self.client.post(
                "/v1/account/password",
                json={"current_password": demo_service.DEMO_PASSWORD, "new_password": "something-else-1"},
            ),
            self.client.request("DELETE", "/v1/account", json={"password": demo_service.DEMO_PASSWORD}),
            self.client.post("/v1/account/sessions/revoke-others"),
            self.client.post("/v1/account/tokens", json={"label": "x", "scopes": ["read"]}),
            self.client.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "x"}),
            self.client.post("/v1/import", json={"format": "pomale-export", "version": 1}),
        ]
        for response in locked:
            self.assertEqual((response.status_code, response.json()["code"]), (403, "demo.not_allowed"), response.url)
        self.assertEqual(self.client.get("/v1/push/subscriptions").json()["code"], "push.disabled")
        self.assertEqual(self.client.get("/v1/admin/users").status_code, 403)
        # What a visitor should try out still works
        self.assertEqual(
            self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True}).status_code, 200
        )
        self.assertEqual(self.client.get("/v1/export.json").status_code, 200)

    def test_refuses_a_database_with_real_accounts(self):
        self.env.create_user("alex")
        db = self.env.SessionLocal()
        try:
            with self.assertRaisesRegex(config.ConfigError, "alex"):
                demo_service.reset(db, self.env.now)
            self.assertEqual(db.scalar(select(func.count()).select_from(Habit)), 6)
            self.assertEqual(db.scalar(select(func.count()).select_from(User)), 2)
        finally:
            db.close()

    def test_scheduler_run_logs_instead_of_raising(self):
        self.env.create_user("alex")
        scheduler = demo_service.DemoResetScheduler(self.env.SessionLocal, clock=lambda: self.env.now)
        with self.assertLogs("app.services.demo_service", "ERROR"):
            scheduler.run_once()


class DemoConfigTest(unittest.TestCase):
    def env(self, **values):
        base = {
            "PUBLIC_URL": "https://demo.example.org",
            "DEMO_MODE": "true",
            "PUSH_ENABLED": "",
            "BACKUP_ENABLED": "",
            "REGISTRATION": "",
            "PASSWORD_LOGIN": "",
            "OIDC_ISSUER": "",
            "OIDC_CLIENT_ID": "",
            "TRACKER_TZ": "",
        }
        base.update(values)
        return mock.patch.dict(os.environ, base)

    def test_demo_turns_push_and_backups_off(self):
        with self.env():
            config.validate()
            self.assertFalse(config.push_enabled())
            self.assertFalse(config.backup_enabled())
        with self.env(DEMO_MODE=""):
            self.assertTrue(config.push_enabled())

    def test_conflicting_settings_stop_the_start(self):
        for name, value in [
            ("PUSH_ENABLED", "true"),
            ("BACKUP_ENABLED", "on"),
            ("REGISTRATION", "open"),
            ("OIDC_ISSUER", "https://id.example.org"),
        ]:
            with self.subTest(name), self.env(**{name: value}), self.assertRaisesRegex(config.ConfigError, name):
                config.validate()
        with self.env(PUSH_ENABLED="false", BACKUP_ENABLED="false", REGISTRATION="invite"):
            config.validate()


if __name__ == "__main__":
    unittest.main()
