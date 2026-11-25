"""Devices for reminders (/v1/push) and reminder times on habits."""

import json
import unittest
from unittest import mock

import httpx

from app.api.routers.push import get_push_sender
from app.main import app
from app.models import AuditEvent, PushSubscription
from app.services.webpush.keys import ensure_vapid_keys
from app.services.webpush.sender import PushSender
from app.services.webpush.vapid import Vapid
from tests.support import ApiTestEnvironment, push_subscription


class PushTestCase(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.addCleanup(self.env.close)
        self.env.create_user("alex", locale="de")
        self.client = self.env.client("alex")
        self.requests: list[httpx.Request] = []
        self.status = 201

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(self.status)

        def sender():
            db = self.env.SessionLocal()
            try:
                vapid = Vapid(ensure_vapid_keys(db), "https://habits.example.org")
            finally:
                db.close()
            yield PushSender(vapid, httpx.Client(transport=httpx.MockTransport(handler)))

        app.dependency_overrides[get_push_sender] = sender

    def rows(self) -> list[PushSubscription]:
        db = self.env.SessionLocal()
        try:
            return db.query(PushSubscription).order_by(PushSubscription.id).all()
        finally:
            db.close()

    def events(self) -> list[str]:
        db = self.env.SessionLocal()
        try:
            return [e.event for e in db.query(AuditEvent).order_by(AuditEvent.id) if e.event.startswith("push.")]
        finally:
            db.close()


class ConfigTest(PushTestCase):
    def test_public_key_is_stable(self):
        first = self.client.get("/v1/push/config").json()
        self.assertTrue(first["enabled"])
        self.assertEqual(len(first["public_key"]), 87)
        self.assertEqual(self.client.get("/v1/push/config").json(), first)

    def test_needs_login(self):
        self.assertEqual(self.env.client(None).get("/v1/push/config").status_code, 401)

    def test_disabled(self):
        with mock.patch.dict("os.environ", {"PUSH_ENABLED": "false"}):
            self.assertEqual(self.client.get("/v1/push/config").json(), {"enabled": False, "public_key": None})
            for method, path in (
                ("GET", "/v1/push/subscriptions"),
                ("POST", "/v1/push/subscriptions"),
                ("DELETE", "/v1/push/subscriptions/1"),
                ("POST", "/v1/push/subscriptions/1/test"),
            ):
                response = self.client.request(method, path, json=push_subscription())
                self.assertEqual((response.status_code, response.json()["code"]), (404, "push.disabled"), path)


class SubscribeTest(PushTestCase):
    def test_subscribe_list_refresh_remove(self):
        body = push_subscription("one")
        created = self.client.post("/v1/push/subscriptions", json=body, headers={"User-Agent": "Mozilla/5.0 (iPhone)"})
        self.assertEqual(created.status_code, 201, created.text)
        device = created.json()
        self.assertTrue(device["current"])
        self.assertEqual(device["device"], "iPhone · Safari")
        # Loading the account page again re-sends the same subscription: no second row
        again = self.client.post("/v1/push/subscriptions", json=push_subscription("one"))
        self.assertEqual((again.status_code, again.json()["id"]), (200, device["id"]))
        listed = self.client.get("/v1/push/subscriptions").json()
        self.assertEqual([d["id"] for d in listed], [device["id"]])
        self.assertNotIn("endpoint", listed[0])
        # Seen from another session it is not "this device"
        other = self.env.client("alex")
        self.assertFalse(other.get("/v1/push/subscriptions").json()[0]["current"])
        self.assertEqual(self.client.delete(f"/v1/push/subscriptions/{device['id']}").status_code, 204)
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.events(), ["push.device_added", "push.device_removed"])

    def test_refresh_updates_keys(self):
        self.client.post("/v1/push/subscriptions", json=push_subscription("one"))
        body = push_subscription("one")
        self.client.post("/v1/push/subscriptions", json=body)
        self.assertEqual(self.rows()[0].p256dh, body["keys"]["p256dh"])

    def test_old_endpoint_is_replaced(self):
        self.client.post("/v1/push/subscriptions", json=push_subscription("old"))
        body = push_subscription("new", old_endpoint="https://fcm.googleapis.com/fcm/send/old")
        self.assertEqual(self.client.post("/v1/push/subscriptions", json=body).status_code, 201)
        self.assertEqual([r.endpoint for r in self.rows()], ["https://fcm.googleapis.com/fcm/send/new"])

    def test_endpoint_moves_to_the_account_now_logged_in(self):
        self.client.post("/v1/push/subscriptions", json=push_subscription("shared"))
        self.env.create_user("sam")
        sam = self.env.client("sam")
        self.assertEqual(sam.post("/v1/push/subscriptions", json=push_subscription("shared")).status_code, 201)
        self.assertEqual(self.client.get("/v1/push/subscriptions").json(), [])
        self.assertEqual(len(sam.get("/v1/push/subscriptions").json()), 1)

    def test_validation(self):
        bad = [
            ({"endpoint": "https://evil.example/x"}, "push.endpoint_not_allowed"),
            ({"endpoint": "http://fcm.googleapis.com/fcm/send/x"}, "push.endpoint_not_allowed"),
            ({"endpoint": "https://127.0.0.1/x"}, "push.endpoint_not_allowed"),
            ({"keys": {"p256dh": "AAAA", "auth": "AAAA"}}, "push.invalid_keys"),
        ]
        for change, code in bad:
            body = {**push_subscription(), **change}
            response = self.client.post("/v1/push/subscriptions", json=body)
            self.assertEqual((response.status_code, response.json()["code"]), (422, code), change)
        self.assertEqual(self.client.post("/v1/push/subscriptions", json={"endpoint": "x"}).status_code, 422)
        self.assertEqual(self.rows(), [])

    def test_extra_allowed_host(self):
        body = {**push_subscription(), "endpoint": "https://push.example.org/x"}
        self.assertEqual(self.client.post("/v1/push/subscriptions", json=body).status_code, 422)
        with mock.patch.dict("os.environ", {"PUSH_ALLOWED_HOSTS": "push.example.org"}):
            self.assertEqual(self.client.post("/v1/push/subscriptions", json=body).status_code, 201)

    def test_device_limit(self):
        for index in range(20):
            self.assertEqual(
                self.client.post("/v1/push/subscriptions", json=push_subscription(str(index))).status_code, 201
            )
        response = self.client.post("/v1/push/subscriptions", json=push_subscription("21"))
        self.assertEqual((response.status_code, response.json()["code"]), (422, "push.too_many_devices"))
        # Refreshing an existing one still works at the limit
        self.assertEqual(self.client.post("/v1/push/subscriptions", json=push_subscription("3")).status_code, 200)


class LogoutTest(PushTestCase):
    def test_logout_removes_this_devices_subscription_only(self):
        other = self.env.client("alex")
        self.client.post("/v1/push/subscriptions", json=push_subscription("this"))
        other.post("/v1/push/subscriptions", json=push_subscription("other"))
        self.assertEqual(self.client.post("/v1/auth/logout").status_code, 204)
        self.assertEqual([r.endpoint.rsplit("/", 1)[1] for r in self.rows()], ["other"])

    def test_ending_sessions_removes_their_subscriptions(self):
        second, third = self.env.client("alex"), self.env.client("alex")
        for name, client in (("one", self.client), ("two", second), ("three", third)):
            client.post("/v1/push/subscriptions", json=push_subscription(name))
        sessions = self.client.get("/v1/account/sessions").json()
        second_id = next(s["id"] for s in sessions if not s["current"])
        self.client.delete(f"/v1/account/sessions/{second_id}")
        self.assertEqual(len(self.rows()), 2)
        self.client.post("/v1/account/sessions/revoke-others")
        self.assertEqual([r.endpoint.rsplit("/", 1)[1] for r in self.rows()], ["one"])

    def test_expired_session_keeps_its_device(self):
        self.client.post("/v1/push/subscriptions", json=push_subscription("one"))
        self.env.now = self.env.now.replace(year=2027)
        db = self.env.SessionLocal()
        try:
            from app.models.user import UserSession

            db.query(UserSession).update({"expires_at": self.env.now.replace(tzinfo=None, year=2026, month=1)})
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.client.get("/v1/push/subscriptions").status_code, 401)
        rows = self.rows()
        self.assertEqual((len(rows), rows[0].session_id), (1, None))


class TestNotificationTest(PushTestCase):
    def device(self, name: str = "one") -> int:
        return self.client.post("/v1/push/subscriptions", json=push_subscription(name)).json()["id"]

    def test_sends_in_the_accounts_language(self):
        device = self.device()
        response = self.client.post(f"/v1/push/subscriptions/{device}/test")
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(str(self.requests[0].url), "https://fcm.googleapis.com/fcm/send/one")
        self.assertEqual(self.requests[0].headers["TTL"], "600")
        self.assertIsNotNone(self.rows()[0].last_success_at)
        listed = self.client.get("/v1/push/subscriptions").json()[0]
        self.assertIsNotNone(listed["last_success_at"])

    def test_payload(self):
        # Decrypt with a known receiver key to check the text
        from cryptography.hazmat.primitives.asymmetric import ec

        from app.services.webpush.crypto import public_bytes
        from app.services.webpush.encoding import b64url_encode
        from tests.test_webpush_crypto import decrypt

        receiver = ec.generate_private_key(ec.SECP256R1())
        body = push_subscription("one")
        body["keys"]["p256dh"] = b64url_encode(public_bytes(receiver))
        device = self.client.post("/v1/push/subscriptions", json=body).json()["id"]
        self.client.post(f"/v1/push/subscriptions/{device}/test")
        payload = json.loads(decrypt(self.requests[0].content, receiver, b"0123456789abcdef"))
        self.assertEqual(payload["title"], "Testbenachrichtigung")
        self.assertEqual((payload["url"], payload["habit"]), ("/account", None))

    def test_gone_removes_the_device(self):
        device = self.device()
        self.status = 410
        response = self.client.post(f"/v1/push/subscriptions/{device}/test")
        self.assertEqual((response.status_code, response.json()["code"]), (410, "push.gone"))
        self.assertEqual(self.rows(), [])

    def test_failure_is_reported_and_kept(self):
        device = self.device()
        self.status = 400
        with self.assertLogs("app.services.webpush.sender", "WARNING"):
            response = self.client.post(f"/v1/push/subscriptions/{device}/test")
        self.assertEqual((response.status_code, response.json()["code"]), (502, "push.send_failed"))
        self.assertEqual(self.rows()[0].last_error, "HTTP 400")
        self.assertEqual(self.client.get("/v1/push/subscriptions").json()[0]["last_error"], "HTTP 400")

    def test_rate_limited(self):
        device = self.device()
        for _ in range(5):
            self.assertEqual(self.client.post(f"/v1/push/subscriptions/{device}/test").status_code, 204)
        response = self.client.post(f"/v1/push/subscriptions/{device}/test")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(self.requests), 5)


class ReminderTimesTest(PushTestCase):
    def test_create_read_update(self):
        habit = self.client.post("/v1/habits", json={"name": "Lesen", "reminders": ["20:00", "07:30"]}).json()
        self.assertEqual(habit["reminders"], ["07:30", "20:00"])
        listed = self.client.get("/v1/habits").json()[0]
        self.assertEqual(listed["reminders"], ["07:30", "20:00"])
        changed = self.client.patch(f"/v1/habits/{habit['id']}", json={"reminders": ["07:30", "12:00:00"]}).json()
        self.assertEqual(changed["reminders"], ["07:30", "12:00"])
        # Other fields leave the times alone
        renamed = self.client.patch(f"/v1/habits/{habit['id']}", json={"name": "Buch"}).json()
        self.assertEqual(renamed["reminders"], ["07:30", "12:00"])
        cleared = self.client.patch(f"/v1/habits/{habit['id']}", json={"reminders": []}).json()
        self.assertEqual(cleared["reminders"], [])
        self.assertEqual(self.client.post("/v1/habits", json={"name": "Ohne"}).json()["reminders"], [])

    def test_unchanged_times_keep_their_last_sent_day(self):
        from datetime import date

        from app.models.habit import HabitReminder

        habit = self.client.post("/v1/habits", json={"name": "Lesen", "reminders": ["07:30"]}).json()
        db = self.env.SessionLocal()
        try:
            db.query(HabitReminder).update({"last_sent_on": date(2026, 11, 24)})
            db.commit()
        finally:
            db.close()
        self.client.patch(f"/v1/habits/{habit['id']}", json={"reminders": ["07:30", "08:00"]})
        db = self.env.SessionLocal()
        try:
            sent = {r.time.strftime("%H:%M"): r.last_sent_on for r in db.query(HabitReminder)}
        finally:
            db.close()
        self.assertEqual(sent, {"07:30": date(2026, 11, 24), "08:00": None})

    def test_validation(self):
        for reminders in (
            ["07:00", "08:00", "09:00", "10:00"],
            ["07:30", "07:30"],
            ["07:30:15"],
            ["25:00"],
            ["07:30+01:00"],
            ["soon"],
        ):
            response = self.client.post("/v1/habits", json={"name": "x", "reminders": reminders})
            self.assertEqual(response.status_code, 422, reminders)


if __name__ == "__main__":
    unittest.main()
