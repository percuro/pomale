import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.web import create_application
from tests.support import ApiTestEnvironment


class WebTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user()
        self.dir = tempfile.TemporaryDirectory()
        dist = Path(self.dir.name)
        (dist / "assets").mkdir()
        (dist / "index.html").write_text("<!doctype html><title>app</title>")
        (dist / "assets" / "index-abc.js").write_text("console.log(1)")
        (dist / "sw.js").write_text("self.x=1")
        (dist / "manifest.webmanifest").write_text("{}")
        (dist / "icon.svg").write_text("<svg/>")
        self.client = TestClient(create_application(dist))

    def tearDown(self):
        self.env.close()
        self.dir.cleanup()

    def test_api_is_mounted_under_api(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(self.client.get("/api/v1/unknown").status_code, 404)

    def test_spa_fallback_and_cache_headers(self):
        for path in ("/", "/heute", "/woche"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIn("<title>app</title>", response.text)
            self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertEqual(self.client.get("/sw.js").headers["cache-control"], "no-cache")
        asset = self.client.get("/assets/index-abc.js")
        self.assertIn("immutable", asset.headers["cache-control"])
        self.assertEqual(self.client.get("/assets/missing.js").status_code, 404)
        self.assertEqual(self.client.get("/missing.png").status_code, 404)
        manifest = self.client.get("/manifest.webmanifest")
        self.assertEqual(manifest.headers["content-type"], "application/manifest+json")

    def test_security_headers(self):
        for path in ("/", "/api/health"):
            headers = self.client.get(path).headers
            self.assertIn("frame-ancestors 'none'", headers["content-security-policy"])
            self.assertEqual(headers["x-content-type-options"], "nosniff")
            self.assertNotIn("strict-transport-security", headers)  # http PUBLIC_URL in tests

    def test_shortcut_through_mounted_api_is_csrf_exempt(self):
        api_client = self.env.client()
        habit = api_client.post("/v1/habits", json={"name": "Lesen"}).json()
        token = api_client.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={}).json()["token"]
        bare = TestClient(self.client.app)
        response = bare.put(
            f"/api/v1/habits/{habit['id']}/days/today",
            headers={"Authorization": f"Bearer {token}"},
            json={"done": True},
        )
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main()


class LifespanTest(unittest.TestCase):
    """Starting the app creates the VAPID key and starts the reminder loop; stopping ends it."""

    def setUp(self):
        from unittest import mock

        self.env = ApiTestEnvironment()
        self.addCleanup(self.env.close)
        patcher = mock.patch("app.web.SessionLocal", self.env.SessionLocal)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_reminders_start_and_stop(self):
        from unittest import mock

        from app.models import InstanceSecret
        from app.services.scheduler import ReminderScheduler

        with mock.patch.object(ReminderScheduler, "stop", autospec=True, side_effect=ReminderScheduler.stop) as stop:
            with self.assertLogs("app.services.scheduler", "INFO"), TestClient(create_application(None)) as client:
                self.assertEqual(client.get("/api/health").status_code, 200)
            stop.assert_called_once()
        db = self.env.SessionLocal()
        try:
            self.assertIsNotNone(db.get(InstanceSecret, "vapid_private_key"))
        finally:
            db.close()

    def test_turned_off(self):
        from unittest import mock

        from app.models import InstanceSecret

        with mock.patch.dict("os.environ", {"PUSH_ENABLED": "false"}), TestClient(create_application(None)):
            pass
        db = self.env.SessionLocal()
        try:
            self.assertIsNone(db.get(InstanceSecret, "vapid_private_key"))
        finally:
            db.close()
