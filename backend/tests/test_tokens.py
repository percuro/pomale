"""API tokens: deny by default, scopes, habit limits, expiry, revocation, CSRF and rate limit."""

import re
import unittest
from datetime import date, datetime, timedelta

from app.main import app
from app.models.api_token import ApiToken
from app.models.user import User
from app.services.auth_service import utcnow
from app.services.token_service import TOKEN_ROUTES, TokenService, hash_token, token_rate_limiter
from tests.support import ApiTestEnvironment


def all_routes() -> set[tuple[str, str]]:
    # The OpenAPI schema lists every API route with its full path, however routers are nested
    paths = app.openapi()["paths"]
    return {(method.upper(), path) for path, operations in paths.items() for method in operations}


class TokenTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user("alex")
        self.client = self.env.client("alex")
        token_rate_limiter.reset()
        # The limiter lives in the process: leave no failed attempts behind for other tests
        self.addCleanup(token_rate_limiter.reset)
        self.read = self.client.post("/v1/habits", json={"name": "Lesen", "start_on": "2026-11-23"}).json()
        self.run = self.client.post("/v1/habits", json={"name": "Laufen", "start_on": "2026-11-23"}).json()
        # A script: no cookie, no CSRF header, no Origin
        self.script = self.env.client(username=None)
        self.script.headers.clear()

    def tearDown(self):
        self.env.close()

    def make(self, scopes=("read", "checkin"), habit_ids=(), expires_in_days=None, username="alex") -> str:
        db = self.env.SessionLocal()
        try:
            user = db.query(User).filter_by(username=username).one()
            _, raw = TokenService(db).create(user, "test", list(scopes), list(habit_ids), expires_in_days)
            return raw
        finally:
            db.close()

    def call(self, token: str, method: str, path: str, **kwargs):
        headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
        return self.script.request(method, path, headers=headers, **kwargs)

    def test_only_listed_routes_are_reachable_with_a_token(self):
        token = self.make()
        values = {"habit_id": self.read["id"], "day": "2026-11-24"}
        # Without any login, but with the CSRF header: 401 means the route needs an account
        browser = self.env.client(username=None)
        for method, template in sorted(all_routes()):
            path = re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), 1)), template)
            body = {} if method in ("POST", "PUT", "PATCH") else None
            anonymous = browser.request(method, path, json=body)
            response = self.call(token, method, path, json=body)
            if (method, template) in TOKEN_ROUTES:
                self.assertNotIn(response.status_code, (401, 403), (method, template, response.text))
            elif anonymous.status_code == 401:
                # Everything else that needs an account stays closed, whatever it is
                self.assertEqual(response.status_code, 403, (method, template, response.text))
                self.assertEqual(response.json()["code"], "token.not_allowed", (method, template))

    def test_never_reachable_with_a_token(self):
        token = self.make()
        for method, path in (
            ("GET", "/v1/auth/me"),
            ("PATCH", "/v1/account"),
            ("DELETE", "/v1/account"),
            ("GET", "/v1/account/sessions"),
            ("GET", "/v1/push/subscriptions"),
            ("POST", "/v1/habits"),
            ("GET", "/v1/admin/users"),
        ):
            self.assertEqual(self.call(token, method, path, json={}).json()["code"], "token.not_allowed", path)

    def test_read_and_check_off(self):
        token = self.make()
        days = self.call(token, "GET", "/v1/days").json()
        self.assertEqual([h["name"] for h in days["habits"]], ["Lesen", "Laufen"])
        done = self.call(token, "PUT", f"/v1/habits/{self.read['id']}/days/2026-11-24", json={"done": True})
        self.assertEqual((done.status_code, done.json()["state"]), (200, "done"))
        note = self.call(token, "PUT", f"/v1/habits/{self.read['id']}/days/2026-11-24/note", json={"note": "p. 12"})
        self.assertEqual(note.status_code, 200)
        self.assertEqual(self.call(token, "GET", "/v1/history").status_code, 200)
        self.assertEqual(self.call(token, "GET", "/v1/export.csv").status_code, 200)

    def test_scopes(self):
        reader = self.make(scopes=["read"])
        refused = self.call(reader, "PUT", f"/v1/habits/{self.read['id']}/days/2026-11-24", json={"done": True})
        self.assertEqual((refused.status_code, refused.json()["code"]), (403, "token.missing_scope"))
        self.assertEqual(refused.json()["scope"], "checkin")
        writer = self.make(scopes=["checkin"])
        self.assertEqual(self.call(writer, "GET", "/v1/days").json()["code"], "token.missing_scope")
        self.assertEqual(
            self.call(writer, "PUT", f"/v1/habits/{self.read['id']}/days/today", json={"done": True}).status_code, 200
        )

    def test_limited_to_some_habits(self):
        token = self.make(habit_ids=[self.read["id"]])
        self.assertEqual([h["name"] for h in self.call(token, "GET", "/v1/days").json()["habits"]], ["Lesen"])
        self.assertEqual([h["name"] for h in self.call(token, "GET", "/v1/habits").json()], ["Lesen"])
        other = self.call(token, "PUT", f"/v1/habits/{self.run['id']}/days/2026-11-24", json={"done": True})
        self.assertEqual((other.status_code, other.json()["code"]), (403, "token.habit_not_allowed"))
        for path in ("/v1/history", "/v1/export.csv", "/v1/groups", "/v1/pauses"):
            response = self.call(token, "GET", path)
            self.assertEqual((response.status_code, response.json()["code"]), (403, "token.all_habits_needed"), path)

    def test_another_accounts_habit_is_not_found(self):
        self.env.create_user("sam")
        sam = self.make(username="sam")
        response = self.call(sam, "PUT", f"/v1/habits/{self.read['id']}/days/2026-11-24", json={"done": True})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.call(sam, "GET", "/v1/days").json()["habits"], [])

    def test_invalid_revoked_expired_and_deactivated(self):
        self.assertEqual(self.call("pm_nonsense", "GET", "/v1/days").json()["code"], "token.invalid")
        expiring = self.make(expires_in_days=30)
        self.assertEqual(self.call(expiring, "GET", "/v1/days").status_code, 200)
        self.env.now += timedelta(days=31)
        db = self.env.SessionLocal()
        try:
            token = db.query(ApiToken).filter_by(token_hash=hash_token(expiring)).one()
            token.expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.call(expiring, "GET", "/v1/days").status_code, 401)

        revoked = self.make()
        db = self.env.SessionLocal()
        try:
            user = db.query(User).filter_by(username="alex").one()
            token = db.query(ApiToken).filter_by(token_hash=hash_token(revoked)).one()
            TokenService(db).revoke(user, token.id)
        finally:
            db.close()
        response = self.call(revoked, "GET", "/v1/days")
        self.assertEqual((response.status_code, response.headers["WWW-Authenticate"]), (401, "Bearer"))

        active = self.make()
        db = self.env.SessionLocal()
        try:
            db.query(User).filter_by(username="alex").update({"is_active": False})
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.call(active, "GET", "/v1/days").status_code, 401)

    def test_keys_from_before_0_10_keep_working(self):
        # Migration 0008 keeps the hash of the old ht_ shortcut keys
        db = self.env.SessionLocal()
        try:
            user = db.query(User).filter_by(username="alex").one()
            db.add(ApiToken(user_id=user.id, label="iPhone", token_hash=hash_token("ht_old-key"), scopes="checkin"))
            db.commit()
        finally:
            db.close()
        response = self.call("ht_old-key", "PUT", f"/v1/habits/{self.read['id']}/days/today", json={"done": True})
        self.assertEqual(response.status_code, 200)

    def test_a_session_cookie_wins_over_a_key(self):
        # The browser sends its cookie; a stray header does not turn it into a key request
        response = self.client.get("/v1/auth/me", headers={"Authorization": "Bearer pm_nonsense"})
        self.assertEqual(response.status_code, 200)

    def test_csrf_does_not_apply_to_keys_but_to_sessions(self):
        token = self.make()
        path = f"/v1/habits/{self.read['id']}/days/2026-11-24"
        self.assertEqual(self.call(token, "PUT", path, json={"done": True}).status_code, 200)
        # A cookie without the CSRF header is refused, even with a key next to it
        stranger = self.env.client(username=None)
        stranger.cookies.update(self.client.cookies)
        stranger.headers.pop("X-Habit-CSRF")
        forged = stranger.put(path, json={"done": False}, headers={"Authorization": f"Bearer {token}"})
        self.assertEqual((forged.status_code, forged.json()["code"]), (403, "csrf.invalid_origin"))

    def test_wrong_keys_are_limited_per_address(self):
        good = self.make()
        for _ in range(20):
            self.call("pm_wrong", "GET", "/v1/days")
        self.assertEqual(self.call(good, "GET", "/v1/days").status_code, 429)
        # Other addresses are not affected (before 0.10 the limit was shared by everyone)
        token_rate_limiter.check("192.0.2.7", "192.0.2.7")

    def test_last_used_is_written_at_most_every_few_minutes(self):
        token = self.make()

        def last_used():
            db = self.env.SessionLocal()
            try:
                return db.query(ApiToken).filter_by(token_hash=hash_token(token)).one().last_used_at
            finally:
                db.close()

        self.assertIsNone(last_used())
        self.call(token, "GET", "/v1/days")
        first = last_used()
        self.assertIsNotNone(first)
        self.call(token, "GET", "/v1/days")
        self.assertEqual(last_used(), first)


class TokenManagementTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user("alex")
        self.client = self.env.client("alex")
        self.habit = self.client.post("/v1/habits", json={"name": "Lesen"}).json()

    def tearDown(self):
        self.env.close()

    def test_create_list_and_revoke(self):
        body = {"label": "Home Assistant", "scopes": ["checkin", "read"], "habit_ids": [self.habit["id"]]}
        created = self.client.post("/v1/account/tokens", json=body)
        self.assertEqual(created.status_code, 201, created.text)
        data = created.json()
        self.assertTrue(data["token"].startswith("pm_"))
        self.assertEqual(
            (data["scopes"], data["habit_ids"], data["expires_at"]), (["read", "checkin"], [self.habit["id"]], None)
        )
        listed = self.client.get("/v1/account/tokens").json()
        self.assertEqual([t["label"] for t in listed], ["Home Assistant"])
        self.assertNotIn("token", listed[0])
        self.assertEqual(self.client.delete(f"/v1/account/tokens/{data['id']}").status_code, 204)
        self.assertIsNotNone(self.client.get("/v1/account/tokens").json()[0]["revoked_at"])
        # Revoking twice is fine
        self.assertEqual(self.client.delete(f"/v1/account/tokens/{data['id']}").status_code, 204)

    def test_expiry(self):
        data = self.client.post("/v1/account/tokens", json={"scopes": ["read"], "expires_in_days": 90}).json()
        created, expires = (datetime.fromisoformat(data[k]) for k in ("created_at", "expires_at"))
        self.assertEqual(expires - created, timedelta(days=90))
        self.assertEqual(data["habit_ids"], [])

    def test_invalid_input(self):
        for body in ({"scopes": []}, {"scopes": ["admin"]}, {"scopes": ["read"], "expires_in_days": 7}, {}):
            response = self.client.post("/v1/account/tokens", json=body)
            self.assertEqual((response.status_code, response.json()["code"]), (422, "validation"), body)
        self.env.create_user("sam")
        foreign = self.env.client("sam").post("/v1/habits", json={"name": "Sam's"}).json()
        response = self.client.post("/v1/account/tokens", json={"scopes": ["read"], "habit_ids": [foreign["id"]]})
        self.assertEqual(response.status_code, 404)

    def test_at_most_fifty_active_keys(self):
        for _ in range(50):
            self.assertEqual(self.client.post("/v1/account/tokens", json={"scopes": ["read"]}).status_code, 201)
        full = self.client.post("/v1/account/tokens", json={"scopes": ["read"]})
        self.assertEqual((full.status_code, full.json()["code"]), (409, "token.limit_reached"))
        first = self.client.get("/v1/account/tokens").json()[-1]["id"]
        self.client.delete(f"/v1/account/tokens/{first}")
        self.assertEqual(self.client.post("/v1/account/tokens", json={"scopes": ["read"]}).status_code, 201)

    def test_shortcut_keys_show_up_in_the_list(self):
        self.client.post(f"/v1/habits/{self.habit['id']}/shortcut-tokens", json={"label": "iPhone"})
        listed = self.client.get("/v1/account/tokens").json()
        self.assertEqual((listed[0]["label"], listed[0]["scopes"]), ("iPhone", ["checkin"]))
        # A general key is not listed as a shortcut key of the habit
        self.client.post("/v1/account/tokens", json={"scopes": ["read"], "habit_ids": [self.habit["id"]]})
        shortcut_keys = self.client.get(f"/v1/habits/{self.habit['id']}/shortcut-tokens").json()
        self.assertEqual([t["label"] for t in shortcut_keys], ["iPhone"])


if __name__ == "__main__":
    unittest.main()
