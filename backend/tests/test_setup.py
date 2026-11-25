import unittest

from app.api.routers.setup import setup_rate_limiter
from app.services import setup_service
from app.services.auth_service import SESSION_COOKIE_NAME
from tests.support import PASSWORD, ApiTestEnvironment


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.client = self.env.client(username=None)
        setup_rate_limiter.reset()
        self.token = setup_service.issue_token()

    def tearDown(self):
        setup_service.clear_token()
        self.env.close()

    def post(self, token=None, username="alex", password=PASSWORD):
        return self.client.post(
            "/v1/setup", json={"token": token or self.token, "username": username, "password": password}
        )

    def test_status_needed_without_accounts(self):
        self.assertEqual(self.client.get("/v1/setup").json(), {"needed": True})

    def test_wrong_token_rejected(self):
        self.assertEqual(self.post(token="falsch").status_code, 403)
        self.assertEqual(self.client.get("/v1/setup").json(), {"needed": True})

    def test_setup_creates_account_and_logs_in(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn(SESSION_COOKIE_NAME, response.headers["set-cookie"])
        me = self.client.get("/v1/auth/me").json()
        self.assertEqual((me["username"], me["role"]), ("alex", "admin"))
        self.assertEqual(self.client.get("/v1/setup").json(), {"needed": False})
        second = self.post(username="mallory")
        self.assertEqual(second.status_code, 409)

    def test_token_invalid_after_setup_even_if_reissued_check(self):
        self.post()
        self.assertFalse(setup_service.token_matches(self.token))

    def test_account_from_cli_ends_setup(self):
        self.env.create_user()
        self.assertEqual(self.client.get("/v1/setup").json(), {"needed": False})
        self.assertEqual(self.post().status_code, 409)

    def test_setup_stores_timezone_and_language(self):
        response = self.client.post(
            "/v1/setup",
            json={
                "token": self.token,
                "username": "alex",
                "password": PASSWORD,
                "timezone": "America/New_York",
                "locale": "en",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()["timezone"], response.json()["locale"]), ("America/New_York", "en"))

    def test_invalid_username_rejected(self):
        response = self.post(username="a b")
        self.assertEqual((response.status_code, response.json()["code"]), (422, "account.invalid_username"))

    def test_weak_password_rejected(self):
        self.assertEqual(self.post(password="kurz").status_code, 422)
        self.assertEqual(self.client.get("/v1/setup").json(), {"needed": True})

    def test_rate_limit(self):
        for _ in range(5):
            self.post(token="falsch")
        self.assertEqual(self.post().status_code, 429)

    def test_no_token_issued_means_no_setup(self):
        setup_service.clear_token()
        self.assertEqual(self.post().status_code, 403)


if __name__ == "__main__":
    unittest.main()
