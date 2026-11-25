import unittest
from datetime import timedelta

from app.models.habit import Checkin, Habit
from app.models.shortcut_token import ShortcutToken
from app.models.user import User, UserSession
from app.services.auth_service import utcnow
from app.services.devices import describe_user_agent
from tests.support import PASSWORD, ApiTestEnvironment

IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
)
FIREFOX_LINUX = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
NEW_PASSWORD = "ein-ganz-neues-passwort"


class AccountTestCase(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user()
        self.client = self.login(IPHONE)

    def tearDown(self):
        self.env.close()

    def login(self, user_agent: str, username: str = "alex", password: str = PASSWORD):
        client = self.env.client(username=None)
        client.headers["User-Agent"] = user_agent
        response = client.post("/v1/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return client

    def count(self, model) -> int:
        db = self.env.SessionLocal()
        try:
            return db.query(model).count()
        finally:
            db.close()


class PasswordChangeTest(AccountTestCase):
    def change(self, current=PASSWORD, new=NEW_PASSWORD, client=None):
        return (client or self.client).post(
            "/v1/account/password", json={"current_password": current, "new_password": new}
        )

    def test_change_logs_out_other_devices_only(self):
        laptop = self.login(FIREFOX_LINUX)
        self.assertEqual(self.change().status_code, 204)
        self.assertEqual(self.client.get("/v1/auth/me").status_code, 200)
        self.assertEqual(laptop.get("/v1/auth/me").status_code, 401)
        self.login(FIREFOX_LINUX, password=NEW_PASSWORD)
        old = self.env.client(username=None).post("/v1/auth/login", json={"username": "alex", "password": PASSWORD})
        self.assertEqual(old.status_code, 401)

    def test_wrong_current_password(self):
        response = self.change(current="falsch-falsch-falsch")
        self.assertEqual((response.status_code, response.json()["code"]), (403, "account.wrong_password"))
        self.assertEqual(self.client.get("/v1/auth/me").status_code, 200)

    def test_new_password_too_short(self):
        response = self.change(new="kurz")
        self.assertEqual((response.status_code, response.json()["code"]), (422, "account.password_too_short"))
        self.assertEqual(response.json()["min_length"], 12)

    def test_wrong_passwords_are_rate_limited(self):
        for _ in range(5):
            self.change(current="falsch-falsch-falsch")
        self.assertEqual(self.change().status_code, 429)


class SessionsTest(AccountTestCase):
    def test_list_marks_this_device_and_names_devices(self):
        self.login(FIREFOX_LINUX)
        sessions = self.client.get("/v1/account/sessions").json()
        self.assertEqual(len(sessions), 2)
        by_device = {s["device"]: s for s in sessions}
        self.assertTrue(by_device["iPhone · Safari"]["current"])
        self.assertFalse(by_device["Linux · Firefox"]["current"])
        self.assertIsNotNone(by_device["Linux · Firefox"]["last_seen_at"])
        self.assertNotIn("user_agent", sessions[0])

    def test_revoke_another_device(self):
        laptop = self.login(FIREFOX_LINUX)
        other = next(s for s in self.client.get("/v1/account/sessions").json() if not s["current"])
        self.assertEqual(self.client.delete(f"/v1/account/sessions/{other['id']}").status_code, 204)
        self.assertEqual(laptop.get("/v1/auth/me").status_code, 401)
        self.assertEqual(self.client.get("/v1/auth/me").status_code, 200)

    def test_revoke_this_device_logs_out(self):
        current = next(s for s in self.client.get("/v1/account/sessions").json() if s["current"])
        response = self.client.delete(f"/v1/account/sessions/{current['id']}")
        self.assertEqual(response.status_code, 204)
        self.assertIn("habit_session=", response.headers.get("set-cookie", ""))
        self.assertEqual(self.client.get("/v1/auth/me").status_code, 401)

    def test_revoke_others(self):
        laptop = self.login(FIREFOX_LINUX)
        tablet = self.login(IPHONE)
        self.assertEqual(self.client.post("/v1/account/sessions/revoke-others").status_code, 204)
        self.assertEqual(laptop.get("/v1/auth/me").status_code, 401)
        self.assertEqual(tablet.get("/v1/auth/me").status_code, 401)
        self.assertEqual(len(self.client.get("/v1/account/sessions").json()), 1)

    def test_cannot_see_or_revoke_sessions_of_other_accounts(self):
        self.env.create_user("sam")
        sam = self.login(FIREFOX_LINUX, username="sam")
        sam_session = sam.get("/v1/account/sessions").json()[0]
        self.assertEqual(len(self.client.get("/v1/account/sessions").json()), 1)
        response = self.client.delete(f"/v1/account/sessions/{sam_session['id']}")
        self.assertEqual((response.status_code, response.json()["code"]), (404, "session.not_found"))
        self.assertEqual(sam.get("/v1/auth/me").status_code, 200)

    def test_last_seen_is_written_at_most_every_few_minutes(self):
        db = self.env.SessionLocal()
        session = db.query(UserSession).one()
        first_seen = session.last_seen_at
        self.client.get("/v1/auth/me")
        db.refresh(session)
        self.assertEqual(session.last_seen_at, first_seen)
        old = utcnow() - timedelta(minutes=10)
        session.last_seen_at = old
        db.commit()
        self.client.get("/v1/auth/me")
        db.refresh(session)
        self.assertGreater(session.last_seen_at, old)
        self.assertEqual(db.query(User).one().last_seen_at, session.last_seen_at)
        db.close()

    def test_no_ip_address_is_stored(self):
        db = self.env.SessionLocal()
        values = [str(v) for v in db.query(UserSession).one().__dict__.values()]
        db.close()
        self.assertFalse(any("testclient" in v or "127.0.0.1" in v for v in values))


class DeleteAccountTest(AccountTestCase):
    def setUp(self):
        super().setUp()
        habit = self.client.post("/v1/habits", json={"name": "Lesen"}).json()
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True})
        self.client.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPhone"})
        self.env.create_user("sam")
        self.sam = self.login(FIREFOX_LINUX, username="sam")
        self.sam.post("/v1/habits", json={"name": "Laufen"})

    def delete(self, password=PASSWORD, client=None):
        return (client or self.client).request("DELETE", "/v1/account", json={"password": password})

    def test_delete_removes_the_account_and_all_its_data(self):
        response = self.delete()
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/v1/auth/me").status_code, 401)
        self.assertEqual(self.count(User), 1)
        self.assertEqual(self.count(Habit), 1)
        self.assertEqual((self.count(Checkin), self.count(ShortcutToken)), (0, 0))
        self.assertEqual([h["name"] for h in self.sam.get("/v1/habits").json()], ["Laufen"])
        login = self.env.client(username=None).post("/v1/auth/login", json={"username": "alex", "password": PASSWORD})
        self.assertEqual(login.status_code, 401)

    def test_wrong_password_keeps_the_account(self):
        response = self.delete(password="falsch-falsch-falsch")
        self.assertEqual((response.status_code, response.json()["code"]), (403, "account.wrong_password"))
        self.assertEqual(self.count(User), 2)

    def test_the_last_admin_cannot_delete_itself(self):
        db = self.env.SessionLocal()
        db.query(User).filter(User.username == "alex").update({User.role: "admin"})
        db.commit()
        response = self.delete()
        self.assertEqual((response.status_code, response.json()["code"]), (409, "account.last_admin"))
        # A deactivated admin does not count
        db.query(User).filter(User.username == "sam").update({User.role: "admin", User.is_active: False})
        db.commit()
        self.assertEqual(self.delete().status_code, 409)
        db.query(User).filter(User.username == "sam").update({User.is_active: True})
        db.commit()
        db.close()
        self.assertEqual(self.delete().status_code, 204)


class DescribeUserAgentTest(unittest.TestCase):
    def test_common_browsers(self):
        cases = {
            IPHONE: "iPhone · Safari",
            FIREFOX_LINUX: "Linux · Firefox",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Mobile/15E148": "iPhone · Safari",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 "
            "Safari/537.36 Edg/140.0": "Windows · Edge",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36": "Mac · Chrome",
            "Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile "
            "Safari/537.36": "Android · Chrome",
        }
        for user_agent, expected in cases.items():
            self.assertEqual(describe_user_agent(user_agent), expected, user_agent)

    def test_unknown(self):
        self.assertIsNone(describe_user_agent(None))
        self.assertIsNone(describe_user_agent("curl/8.10"))


if __name__ == "__main__":
    unittest.main()
