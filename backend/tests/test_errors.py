"""Every error has the shape {"detail": "<English message>", "code": "<stable code>"}."""

import unittest

from tests.support import ApiTestEnvironment


class ErrorFormatTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user()
        self.client = self.env.client()

    def tearDown(self):
        self.env.close()

    def assertError(self, response, status: int, code: str):
        self.assertEqual(response.status_code, status, response.text)
        body = response.json()
        self.assertEqual(body["code"], code)
        self.assertIsInstance(body["detail"], str)
        self.assertTrue(body["detail"].isascii(), body["detail"])
        return body

    def test_app_errors(self):
        self.assertError(self.client.get("/v1/habits/999/shortcut-tokens"), 404, "habit.not_found")
        anonymous = self.env.client(username=None)
        self.assertError(anonymous.get("/v1/auth/me"), 401, "auth.not_authenticated")
        self.assertError(
            anonymous.post("/v1/auth/login", json={"username": "alex", "password": "wrong"}),
            401,
            "auth.invalid_credentials",
        )

    def test_validation_error_lists_fields(self):
        body = self.assertError(self.client.post("/v1/habits", json={"name": "   "}), 422, "validation")
        self.assertEqual(body["errors"][0]["field"], "name")
        body = self.assertError(self.client.post("/v1/habits", json={}), 422, "validation")
        self.assertEqual(body["errors"][0]["type"], "missing")

    def test_framework_errors_get_a_generic_code(self):
        self.assertError(self.client.get("/v1/does-not-exist"), 404, "http.404")
        self.assertError(self.client.delete("/v1/auth/me"), 405, "http.405")

    def test_csrf_rejection(self):
        response = self.client.post("/v1/habits", json={"name": "x"}, headers={"X-Habit-CSRF": ""})
        self.assertError(response, 403, "csrf.invalid_origin")

    def test_range_errors_carry_parameters(self):
        body = self.assertError(
            self.client.get("/v1/days", params={"from": "2026-01-01", "to": "2026-12-31"}), 422, "range.too_long"
        )
        self.assertEqual(body["max_days"], 62)


if __name__ == "__main__":
    unittest.main()
