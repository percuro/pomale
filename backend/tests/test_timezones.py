"""Each account has its own "today": two accounts on opposite sides of the date line."""

import os
import unittest
from datetime import UTC, datetime
from unittest import mock

from app.services.shortcut_service import shortcut_rate_limiter
from tests.support import PASSWORD, ApiTestEnvironment

# 11:00 UTC: already Wednesday 01:00 in Kiritimati (UTC+14), still Tuesday 01:00 in Honolulu (UTC-10)
NOW = datetime(2026, 11, 24, 11, 0, tzinfo=UTC)


class PerAccountTimezoneTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.now = NOW
        self.env.create_user("kiri", timezone="Pacific/Kiritimati")
        self.env.create_user("hono", timezone="Pacific/Honolulu")
        self.kiri = self.env.client("kiri")
        self.hono = self.env.client("hono")
        shortcut_rate_limiter.reset()

    def tearDown(self):
        self.env.close()

    def test_same_moment_different_today(self):
        kiri = self.kiri.get("/v1/auth/me").json()
        hono = self.hono.get("/v1/auth/me").json()
        self.assertEqual((kiri["today"], kiri["timezone"]), ("2026-11-25", "Pacific/Kiritimati"))
        self.assertEqual((hono["today"], hono["timezone"]), ("2026-11-24", "Pacific/Honolulu"))
        self.assertEqual(self.kiri.get("/v1/days").json()["today"], "2026-11-25")
        self.assertEqual(self.hono.get("/v1/days").json()["timezone"], "Pacific/Honolulu")

    def test_future_day_depends_on_the_account(self):
        kiri_habit = self.kiri.post("/v1/habits", json={"name": "Read", "start_on": "2026-11-23"}).json()
        hono_habit = self.hono.post("/v1/habits", json={"name": "Run", "start_on": "2026-11-23"}).json()
        self.assertEqual(
            self.kiri.put(f"/v1/habits/{kiri_habit['id']}/days/2026-11-25", json={"done": True}).status_code, 200
        )
        future = self.hono.put(f"/v1/habits/{hono_habit['id']}/days/2026-11-25", json={"done": True})
        self.assertEqual((future.status_code, future.json()["code"]), (422, "checkin.future_day"))

    def test_quota_counts_up_to_the_accounts_today(self):
        for client in (self.kiri, self.hono):
            client.post("/v1/habits", json={"name": "Daily", "start_on": "2026-11-23"})
        # Monday and Tuesday are due in Kiritimati (Wednesday is today and still open),
        # only Monday in Honolulu (Tuesday is today)
        self.assertEqual(self.kiri.get("/v1/days").json()["habits"][0]["quota"], {"done": 0, "due": 2})
        self.assertEqual(self.hono.get("/v1/days").json()["habits"][0]["quota"], {"done": 0, "due": 1})

    def test_shortcut_uses_the_owners_today(self):
        habit = self.kiri.post("/v1/habits", json={"name": "Read", "start_on": "2026-11-23"}).json()
        token = self.kiri.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPhone"}).json()["token"]
        phone = self.env.client(username=None)
        phone.headers.clear()
        response = phone.put(
            f"/v1/habits/{habit['id']}/days/today", headers={"Authorization": f"Bearer {token}"}, json={"done": True}
        )
        self.assertEqual(response.json()["date"], "2026-11-25")

    def test_changing_the_timezone_keeps_checkins_on_their_calendar_day(self):
        habit = self.kiri.post("/v1/habits", json={"name": "Read", "start_on": "2026-11-23"}).json()
        self.kiri.put(f"/v1/habits/{habit['id']}/days/2026-11-25", json={"done": True})
        me = self.kiri.patch("/v1/account", json={"timezone": "Pacific/Honolulu"}).json()
        self.assertEqual((me["today"], me["timezone_setting"]), ("2026-11-24", "Pacific/Honolulu"))
        days = self.kiri.get("/v1/days").json()["habits"][0]["days"]
        # Wednesday stays done; for this account it is now a future day
        self.assertEqual((days[2]["date"], days[2]["done"], days[2]["state"]), ("2026-11-25", False, "future"))
        self.kiri.patch("/v1/account", json={"timezone": "Pacific/Kiritimati"})
        days = self.kiri.get("/v1/days").json()["habits"][0]["days"]
        self.assertEqual(days[2]["state"], "done")

    def test_null_timezone_means_server_default(self):
        with mock.patch.dict(os.environ, {"DEFAULT_TIMEZONE": "Pacific/Kiritimati"}):
            me = self.hono.patch("/v1/account", json={"timezone": None}).json()
        self.assertEqual(
            (me["timezone"], me["timezone_setting"], me["default_timezone"], me["today"]),
            ("Pacific/Kiritimati", None, "Pacific/Kiritimati", "2026-11-25"),
        )

    def test_unknown_stored_timezone_falls_back_to_default(self):
        self.env.create_user("lost", timezone="Mars/Olympus_Mons")
        me = self.env.client("lost").get("/v1/auth/me").json()
        self.assertEqual((me["timezone"], me["timezone_setting"]), ("UTC", "Mars/Olympus_Mons"))


class AccountSettingsTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user()
        self.client = self.env.client()

    def tearDown(self):
        self.env.close()

    def test_patch_changes_only_the_fields_sent(self):
        me = self.client.patch("/v1/account", json={"display_name": "  Alex  ", "locale": "de"}).json()
        self.assertEqual((me["display_name"], me["locale"], me["timezone_setting"]), ("Alex", "de", None))
        me = self.client.patch("/v1/account", json={"timezone": "Europe/Berlin"}).json()
        self.assertEqual((me["display_name"], me["locale"], me["timezone"]), ("Alex", "de", "Europe/Berlin"))
        me = self.client.patch("/v1/account", json={"display_name": "", "locale": None}).json()
        self.assertEqual((me["display_name"], me["locale"]), (None, None))

    def test_invalid_values_are_rejected(self):
        for body in ({"timezone": "Europe/Atlantis"}, {"timezone": "../../etc/passwd"}, {"locale": "fr"}):
            response = self.client.patch("/v1/account", json=body)
            self.assertEqual((response.status_code, response.json()["code"]), (422, "validation"), body)
        self.assertEqual(self.client.patch("/v1/account", json={"display_name": "x" * 81}).status_code, 422)

    def test_day_end(self):
        me = self.client.get("/v1/auth/me").json()
        self.assertEqual(me["day_end_hour"], 0)
        me = self.client.patch("/v1/account", json={"day_end_hour": 3}).json()
        self.assertEqual(me["day_end_hour"], 3)
        # Other changes keep it
        me = self.client.patch("/v1/account", json={"locale": "en"}).json()
        self.assertEqual(me["day_end_hour"], 3)
        for value in (-1, 7, 24, None, "1:00", 1.5):
            response = self.client.patch("/v1/account", json={"day_end_hour": value})
            self.assertEqual((response.status_code, response.json()["code"]), (422, "validation"), value)
        self.assertEqual(self.client.patch("/v1/account", json={"day_end_hour": 6}).json()["day_end_hour"], 6)
        self.assertEqual(self.client.patch("/v1/account", json={"day_end_hour": 0}).json()["day_end_hour"], 0)

    def test_requires_login(self):
        self.assertEqual(self.env.client(username=None).patch("/v1/account", json={}).status_code, 401)

    def test_login_returns_the_accounts_settings(self):
        self.client.patch("/v1/account", json={"timezone": "Asia/Tokyo", "locale": "en"})
        me = self.env.client("alex", PASSWORD).get("/v1/auth/me").json()
        self.assertEqual((me["timezone"], me["locale"], me["role"]), ("Asia/Tokyo", "en", "user"))


class DayEndTest(unittest.TestCase):
    """A day end after midnight: the night still belongs to the day before, for every client."""

    def setUp(self):
        self.env = ApiTestEnvironment()
        # Wednesday 00:30 in Honolulu (UTC-10)
        self.env.now = datetime(2026, 11, 25, 10, 30, tzinfo=UTC)
        self.env.create_user("owl", timezone="Pacific/Honolulu", day_end_hour=1)
        self.env.create_user("lark", timezone="Pacific/Honolulu")
        self.owl = self.env.client("owl")
        self.lark = self.env.client("lark")
        shortcut_rate_limiter.reset()

    def tearDown(self):
        self.env.close()

    def test_me_and_days_follow_the_day_end(self):
        owl = self.owl.get("/v1/auth/me").json()
        self.assertEqual((owl["today"], owl["day_end_hour"]), ("2026-11-24", 1))
        self.assertEqual(self.owl.get("/v1/days").json()["today"], "2026-11-24")
        self.assertEqual(self.lark.get("/v1/auth/me").json()["today"], "2026-11-25")
        # One hour later the owl's Wednesday starts too
        self.env.now = datetime(2026, 11, 25, 11, 0, tzinfo=UTC)
        self.assertEqual(self.owl.get("/v1/auth/me").json()["today"], "2026-11-25")

    def test_the_calendar_day_is_still_the_future(self):
        habit = self.owl.post("/v1/habits", json={"name": "Read", "start_on": "2026-11-23"}).json()
        self.assertEqual(
            self.owl.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True}).status_code, 200
        )
        future = self.owl.put(f"/v1/habits/{habit['id']}/days/2026-11-25", json={"done": True})
        self.assertEqual((future.status_code, future.json()["code"]), (422, "checkin.future_day"))

    def test_shortcut_checks_off_the_day_before(self):
        habit = self.owl.post("/v1/habits", json={"name": "Read", "start_on": "2026-11-23"}).json()
        token = self.owl.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPhone"}).json()["token"]
        phone = self.env.client(username=None)
        phone.headers.clear()
        response = phone.put(
            f"/v1/habits/{habit['id']}/days/today", headers={"Authorization": f"Bearer {token}"}, json={"done": True}
        )
        self.assertEqual(response.json()["date"], "2026-11-24")


if __name__ == "__main__":
    unittest.main()
