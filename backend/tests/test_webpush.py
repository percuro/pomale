"""VAPID keys and tokens, endpoint checks and sending (with a mocked push service)."""

import json
import unittest
from unittest import mock

import httpx
from cryptography.hazmat.primitives.asymmetric import ec
from joserfc import jwt
from joserfc.jwk import ECKey
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base, configure_sqlite
from app.models import InstanceSecret
from app.services.webpush.crypto import public_bytes
from app.services.webpush.encoding import b64url_decode, b64url_encode
from app.services.webpush.endpoints import decode_keys, endpoint_allowed
from app.services.webpush.keys import ensure_vapid_keys, load_vapid_keys
from app.services.webpush.sender import PushSender
from app.services.webpush.vapid import Vapid
from tests.support import TEST_ENV
from tests.test_webpush_crypto import decrypt

ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc:def"


def make_db(test: unittest.TestCase):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    configure_sqlite(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    test.addCleanup(engine.dispose)
    test.addCleanup(session.close)
    return session


def subscription() -> tuple[ec.EllipticCurvePrivateKey, bytes, str, str]:
    receiver = ec.generate_private_key(ec.SECP256R1())
    secret = b"0123456789abcdef"
    return receiver, secret, b64url_encode(public_bytes(receiver)), b64url_encode(secret)


class EnvTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict("os.environ", TEST_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)


class KeysTest(EnvTestCase):
    def test_created_once_and_stable(self):
        db = make_db(self)
        self.assertIsNone(load_vapid_keys(db))
        with self.assertLogs("app.services.webpush.keys", "INFO"):
            first = ensure_vapid_keys(db)
        second = ensure_vapid_keys(db)
        self.assertEqual(first.public_key, second.public_key)
        self.assertEqual(len(b64url_decode(first.public_key)), 65)
        self.assertEqual(len(db.scalars(select(InstanceSecret)).all()), 1)

    def test_lost_race_uses_the_stored_key(self):
        db = make_db(self)
        other = make_db(self)
        winner = ensure_vapid_keys(other)
        # Simulate the other process inserting between our read and our insert
        db.add(InstanceSecret(name="vapid_private_key", value=winner.private_pem))
        db.commit()
        with mock.patch("app.services.webpush.keys.load_vapid_keys", side_effect=[None, load_vapid_keys(db)]):
            keys = ensure_vapid_keys(db)
        self.assertEqual(keys.public_key, winner.public_key)


class VapidTest(EnvTestCase):
    def test_token_verifies_and_has_the_claims(self):
        keys = ensure_vapid_keys(make_db(self))
        now = [1_800_000_000.0]
        vapid = Vapid(keys, "mailto:ops@example.org", clock=lambda: now[0])
        header = vapid.authorization(ENDPOINT)
        token = header.removeprefix("vapid t=").split(",")[0]
        self.assertTrue(header.endswith(f", k={keys.public_key}"))
        public = ECKey.import_key(keys.private_key.public_key())
        claims = jwt.decode(token, public, algorithms=["ES256"]).claims
        self.assertEqual(
            claims,
            {"aud": "https://fcm.googleapis.com", "exp": 1_800_000_000 + 12 * 3600, "sub": "mailto:ops@example.org"},
        )
        # Cached per audience for an hour
        self.assertEqual(vapid.authorization(ENDPOINT + "x"), header)
        self.assertNotEqual(vapid.authorization("https://web.push.apple.com/abc"), header)
        now[0] += 3601
        self.assertNotEqual(vapid.authorization(ENDPOINT), header)


class EndpointTest(EnvTestCase):
    def test_known_push_services_only(self):
        for url in (
            ENDPOINT,
            "https://updates.push.services.mozilla.com/wpush/v2/gAAA",
            "https://web.push.apple.com/QGuQ",
            "https://wns2-par02p.notify.windows.com/w/?token=BQYA",
            "https://fcm.googleapis.com:443/fcm/send/x",
        ):
            self.assertTrue(endpoint_allowed(url), url)
        for url in (
            "http://fcm.googleapis.com/fcm/send/x",
            "https://fcm.googleapis.com:8443/x",
            "https://evil.example/fcm.googleapis.com",
            "https://fcm.googleapis.com.evil.example/x",
            "https://push.apple.com/x",
            "https://user:pw@fcm.googleapis.com/x",
            "https://127.0.0.1/x",
            "https://localhost/x",
            "https://[::1]:99999/x",
            "https://fcm.googleapis.com/" + "x" * 1000,
            "not a url",
        ):
            self.assertFalse(endpoint_allowed(url), url)

    def test_extra_hosts(self):
        with mock.patch.dict("os.environ", {"PUSH_ALLOWED_HOSTS": "push.example.org, *.autopush.test:8443"}):
            self.assertTrue(endpoint_allowed("https://push.example.org/x"))
            self.assertTrue(endpoint_allowed("https://a.autopush.test:8443/x"))
            self.assertFalse(endpoint_allowed("https://a.autopush.test/x"))
            self.assertFalse(endpoint_allowed("https://sub.push.example.org/x"))

    def test_keys(self):
        _, _, p256dh, auth = subscription()
        self.assertEqual(len(decode_keys(p256dh, auth)[0]), 65)
        for bad in ((p256dh[:-2], auth), (p256dh, auth[:-2]), ("", auth), (p256dh, "a+b/")):
            with self.assertRaises(ValueError):
                decode_keys(*bad)


class SenderTest(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.keys = ensure_vapid_keys(make_db(self))
        self.requests: list[httpx.Request] = []
        self.status = 201

    def sender(self, handler=None) -> PushSender:
        def default(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(self.status)

        client = httpx.Client(transport=httpx.MockTransport(handler or default), follow_redirects=False)
        return PushSender(Vapid(self.keys, "https://habits.example.org"), client)

    def test_sends_an_encrypted_message_with_headers(self):
        receiver, secret, p256dh, auth = subscription()
        result = self.sender().send(ENDPOINT, p256dh, auth, b'{"title":"Lesen"}', topic="reminders")
        self.assertEqual((result.outcome, result.status), ("ok", 201))
        request = self.requests[0]
        self.assertEqual(str(request.url), ENDPOINT)
        self.assertEqual(request.headers["Content-Encoding"], "aes128gcm")
        self.assertEqual(request.headers["TTL"], "7200")
        self.assertEqual(request.headers["Urgency"], "normal")
        self.assertEqual(request.headers["Topic"], "reminders")
        self.assertTrue(request.headers["Authorization"].startswith("vapid t="))
        self.assertEqual(json.loads(decrypt(request.content, receiver, secret)), {"title": "Lesen"})

    def test_gone_and_failures(self):
        _, _, p256dh, auth = subscription()
        for status, outcome in ((404, "gone"), (410, "gone"), (400, "failed"), (429, "failed"), (500, "failed")):
            self.status = status
            with (
                self.assertNoLogs("app.services.webpush.sender", "WARNING")
                if outcome == "gone"
                else self.assertLogs("app.services.webpush.sender", "WARNING")
            ):
                result = self.sender().send(ENDPOINT, p256dh, auth, b"{}")
            self.assertEqual((result.outcome, result.status), (outcome, status))

    def test_redirects_are_not_followed(self):
        _, _, p256dh, auth = subscription()

        def redirect(request):
            self.requests.append(request)
            return httpx.Response(307, headers={"Location": "http://127.0.0.1/admin"})

        with self.assertLogs("app.services.webpush.sender", "WARNING"):
            result = self.sender(redirect).send(ENDPOINT, p256dh, auth, b"{}")
        self.assertEqual((result.outcome, len(self.requests)), ("failed", 1))

    def test_network_error(self):
        _, _, p256dh, auth = subscription()

        def fail(request):
            raise httpx.ConnectTimeout("timed out", request=request)

        with self.assertLogs("app.services.webpush.sender", "WARNING"):
            result = self.sender(fail).send(ENDPOINT, p256dh, auth, b"{}")
        self.assertEqual((result.outcome, result.reason), ("failed", "ConnectTimeout"))

    def test_refuses_unknown_hosts_and_bad_keys_without_a_request(self):
        _, _, p256dh, auth = subscription()
        sender = self.sender()
        self.assertEqual(sender.send("https://127.0.0.1/x", p256dh, auth, b"{}").outcome, "failed")
        self.assertEqual(sender.send(ENDPOINT, p256dh[:-4], auth, b"{}").outcome, "failed")
        self.assertEqual(self.requests, [])


if __name__ == "__main__":
    unittest.main()
