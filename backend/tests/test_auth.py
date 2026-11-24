import unittest
from datetime import timedelta
from http.cookies import SimpleCookie

from app.models.user import UserSession
from app.services.auth_service import SESSION_COOKIE_NAME, AuthService, utcnow
from tests.support import PASSWORD, ApiTestEnvironment


class AuthApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user()

    def tearDown(self):
        self.env.close()

    def test_password_is_hashed(self):
        db = self.env.SessionLocal()
        from app.models.user import User

        user = db.query(User).one()
        self.assertNotIn(PASSWORD, user.password_hash)
        self.assertTrue(AuthService.verify_password(PASSWORD, user.password_hash))
        self.assertFalse(AuthService.verify_password("falsch-falsch-falsch", user.password_hash))
        db.close()

    def test_short_password_rejected(self):
        with self.assertRaises(ValueError):
            self.env.create_user("kurz", "zu-kurz")

    def test_login_sets_persistent_http_only_cookie(self):
        client = self.env.client(username=None)
        response = client.post("/v1/auth/login", json={"username": "ALEX", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "alex", "today": "2026-11-24", "timezone": "UTC"})
        cookie = SimpleCookie()
        cookie.load(response.headers["set-cookie"])
        morsel = cookie[SESSION_COOKIE_NAME]
        self.assertTrue(morsel["httponly"])
        self.assertNotEqual(morsel["max-age"], "")
        self.assertEqual(client.get("/v1/auth/me").status_code, 200)

    def test_wrong_password_and_logout(self):
        client = self.env.client(username=None)
        self.assertEqual(
            client.post("/v1/auth/login", json={"username": "alex", "password": "falsch"}).status_code, 401
        )
        self.assertEqual(client.get("/v1/auth/me").status_code, 401)
        client = self.env.client()
        self.assertEqual(client.post("/v1/auth/logout").status_code, 204)
        self.assertEqual(client.get("/v1/auth/me").status_code, 401)

    def test_rate_limit_after_five_failures(self):
        client = self.env.client(username=None)
        for _ in range(5):
            client.post("/v1/auth/login", json={"username": "alex", "password": "falsch"})
        response = client.post("/v1/auth/login", json={"username": "alex", "password": PASSWORD})
        self.assertEqual(response.status_code, 429)

    def test_expired_session_is_rejected(self):
        client = self.env.client()
        db = self.env.SessionLocal()
        db.query(UserSession).update({UserSession.expires_at: utcnow() - timedelta(minutes=1)})
        db.commit()
        db.close()
        self.assertEqual(client.get("/v1/auth/me").status_code, 401)

    def test_protected_routes_require_login(self):
        client = self.env.client(username=None)
        self.assertEqual(client.get("/v1/habits").status_code, 401)
        self.assertEqual(client.get("/v1/days").status_code, 401)
        self.assertEqual(client.put("/v1/habits/1/days/2026-11-24", json={"done": True}).status_code, 401)

    def test_health(self):
        self.assertEqual(self.env.client(username=None).get("/health").json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
