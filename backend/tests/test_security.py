import os
import unittest

from fastapi import Request
from fastapi.responses import Response

from app.errors import AppError
from app.middleware.csrf import enforce_csrf
from app.services.login_rate_limiter import LoginRateLimiter


class LoginRateLimiterTest(unittest.TestCase):
    def test_blocks_account_after_five_failures(self):
        limiter = LoginRateLimiter()
        for _ in range(5):
            limiter.check("alex", "192.0.2.1")
            limiter.record_failure("alex", "192.0.2.1")

        with self.assertRaises(AppError) as context:
            limiter.check("alex", "192.0.2.1")
        self.assertEqual(context.exception.status_code, 429)

        limiter.record_success("alex")
        limiter.check("alex", "192.0.2.1")

    def test_blocks_ip_after_twenty_failures(self):
        limiter = LoginRateLimiter()
        for i in range(20):
            limiter.record_failure(f"user{i}", "192.0.2.9")
        with self.assertRaises(AppError):
            limiter.check("neu", "192.0.2.9")


class CsrfMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.previous = {k: os.environ.get(k) for k in ("CSRF_PROTECTION", "CORS_ORIGINS", "PUBLIC_URL")}
        os.environ["CSRF_PROTECTION"] = "true"
        os.environ["PUBLIC_URL"] = "https://habits.example.org"
        os.environ["CORS_ORIGINS"] = ""

    async def asyncTearDown(self):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    async def _call(self, method: str, headers: dict[str, str]) -> int:
        request = Request(
            {
                "type": "http",
                "method": method,
                "path": "/v1/habits/1/days/2026-11-24",
                "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            }
        )

        async def call_next(_request):
            return Response(status_code=200)

        return (await enforce_csrf(request, call_next)).status_code

    async def test_get_is_allowed_without_header(self):
        self.assertEqual(await self._call("GET", {}), 200)

    async def test_shortcut_path_is_exempt_with_api_prefix(self):
        headers = {"Authorization": "Bearer ht_x"}
        request = Request(
            {
                "type": "http",
                "method": "PUT",
                "path": "/api/v1/habits/1/days/today",
                "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            }
        )

        async def call_next(_request):
            return Response(status_code=200)

        self.assertEqual((await enforce_csrf(request, call_next)).status_code, 200)

    async def test_put_requires_header_and_trusted_origin(self):
        self.assertEqual(await self._call("PUT", {}), 403)
        self.assertEqual(await self._call("PUT", {"X-Habit-CSRF": "1"}), 403)
        self.assertEqual(await self._call("PUT", {"X-Habit-CSRF": "1", "Origin": "https://evil.example"}), 403)
        self.assertEqual(await self._call("PUT", {"X-Habit-CSRF": "1", "Origin": "https://habits.example.org"}), 200)
        self.assertEqual(
            await self._call("PUT", {"X-Habit-CSRF": "1", "Referer": "https://habits.example.org/heute"}),
            200,
        )


if __name__ == "__main__":
    unittest.main()
