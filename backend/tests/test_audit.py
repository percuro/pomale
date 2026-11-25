import json
import unittest
from datetime import timedelta
from unittest import mock

from fastapi.testclient import TestClient

from app.main import app
from app.models.audit_event import AuditEvent
from app.services import audit_service
from app.services.auth_service import utcnow
from app.services.invitation_service import invitation_rate_limiter
from app.services.login_rate_limiter import login_rate_limiter
from tests.support import PASSWORD, TEST_ORIGIN, ApiTestEnvironment

NEW_PASSWORD = "ein-neues-passwort-456"


class IpPrefixTest(unittest.TestCase):
    def test_shortens_addresses(self):
        self.assertEqual(audit_service.ip_prefix("203.0.113.7"), "203.0.113.0/24")
        self.assertEqual(audit_service.ip_prefix("2001:db8:1:2::5"), "2001:db8:1::/48")
        self.assertEqual(audit_service.ip_prefix("::ffff:198.51.100.9"), "198.51.100.0/24")
        self.assertIsNone(audit_service.ip_prefix("testclient"))
        self.assertIsNone(audit_service.ip_prefix(None))


class AuditLogTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.admin_user = self.env.create_user("admin", role="admin")
        self.sam_user = self.env.create_user("sam")
        self.admin = self.env.client("admin")
        invitation_rate_limiter.reset()

    def tearDown(self):
        self.env.close()

    def events(self) -> list[AuditEvent]:
        db = self.env.SessionLocal()
        try:
            return list(db.query(AuditEvent).order_by(AuditEvent.id))
        finally:
            db.close()

    def names(self) -> list[str]:
        return [event.event for event in self.events()]

    def last(self, name: str) -> AuditEvent:
        matching = [event for event in self.events() if event.event == name]
        self.assertTrue(matching, f"no {name} in {self.names()}")
        return matching[-1]

    def remote_client(self, ip: str) -> TestClient:
        return TestClient(app, headers={"X-Habit-CSRF": "1", "Origin": TEST_ORIGIN}, client=(ip, 50000))

    def test_login_success_and_failure(self):
        self.assertEqual(self.last("auth.login").actor_username, "admin")
        remote = self.remote_client("203.0.113.7")
        remote.post("/v1/auth/login", json={"username": "sam", "password": "falsch"})
        remote.post("/v1/auth/login", json={"username": "nobody-here", "password": "falsch"})
        failed = [event for event in self.events() if event.event == "auth.login_failed"]
        self.assertEqual([event.target_username for event in failed], ["sam", None])
        self.assertEqual({event.ip_prefix for event in failed}, {"203.0.113.0/24"})
        self.assertNotIn("nobody-here", json.dumps([event.details for event in failed]))
        # Successful logins store no address
        self.assertIsNone(self.last("auth.login").ip_prefix)

    def test_rate_limit_block_is_logged_once(self):
        remote = self.remote_client("198.51.100.20")
        for _ in range(login_rate_limiter.account_limit + 2):
            remote.post("/v1/auth/login", json={"username": "sam", "password": "falsch"})
        blocks = [event for event in self.events() if event.event == "auth.rate_limited"]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(
            (blocks[0].target_username, blocks[0].ip_prefix, audit_service.details_of(blocks[0])),
            ("sam", "198.51.100.0/24", {"limiter": "login"}),
        )

    def test_each_action_writes_its_event(self):
        sam = self.env.client("sam")
        habit = sam.post("/v1/habits", json={"name": "Lesen"}).json()
        actions = [
            (
                lambda: self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"role": "admin"}),
                "admin.role_changed",
                "admin",
                "sam",
                {"before": "user", "after": "admin"},
            ),
            (
                lambda: self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"role": "user"}),
                "admin.role_changed",
                "admin",
                "sam",
                {"before": "admin", "after": "user"},
            ),
            (
                lambda: self.admin.post("/v1/admin/invitations", json={"role": "user"}),
                "invite.created",
                "admin",
                None,
                {"purpose": "signup", "role": "user"},
            ),
            (
                lambda: self.admin.post(f"/v1/admin/users/{self.sam_user.id}/password-reset"),
                "invite.created",
                "admin",
                "sam",
                {"purpose": "password_reset"},
            ),
            (
                lambda: sam.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPhone"}),
                "shortcut.key_created",
                "sam",
                None,
                {"habit_id": habit["id"], "label": "iPhone"},
            ),
            (
                lambda: sam.post(
                    "/v1/account/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
                ),
                "account.password_changed",
                "sam",
                "sam",
                {},
            ),
            (lambda: sam.post("/v1/account/sessions/revoke-others"), None, None, None, None),
            (
                lambda: self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"is_active": False}),
                "admin.deactivated",
                "admin",
                "sam",
                {},
            ),
            (
                lambda: self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"is_active": True}),
                "admin.reactivated",
                "admin",
                "sam",
                {},
            ),
        ]
        for action, name, actor, target, details in actions:
            before = len(self.events())
            response = action()
            self.assertLess(response.status_code, 300, response.text)
            if name is None:
                # Nothing to revoke: no entry
                self.assertEqual(len(self.events()), before)
                continue
            event = self.events()[-1]
            self.assertEqual(
                (event.event, event.actor_username, event.target_username, audit_service.details_of(event)),
                (name, actor, target, details),
            )

    def test_shortcut_key_revoked(self):
        sam = self.env.client("sam")
        habit = sam.post("/v1/habits", json={"name": "Lesen"}).json()
        key = sam.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPad"}).json()
        sam.delete(f"/v1/habits/{habit['id']}/shortcut-tokens/{key['id']}")
        event = self.last("shortcut.key_revoked")
        self.assertEqual((event.actor_username, audit_service.details_of(event)["label"]), ("sam", "iPad"))

    def test_invitation_used_revoked_and_account_created(self):
        created = self.admin.post("/v1/admin/invitations", json={"role": "user", "note": "Kim"}).json()
        token = created["url"].split("#", 1)[1]
        guest = self.env.client(username=None)
        guest.post("/v1/invitations/accept", json={"token": token, "username": "kim", "password": PASSWORD})
        created_event = self.last("account.created")
        self.assertEqual(
            (created_event.target_username, audit_service.details_of(created_event)),
            ("kim", {"via": "invite", "role": "user"}),
        )
        self.assertEqual(audit_service.details_of(self.last("invite.used")), {"purpose": "signup"})
        other = self.admin.post("/v1/admin/invitations", json={"role": "admin"}).json()
        self.admin.delete(f"/v1/admin/invitations/{other['id']}")
        self.assertEqual(self.last("invite.revoked").actor_username, "admin")

    def test_deleted_accounts_stay_readable(self):
        self.admin.delete(f"/v1/admin/users/{self.sam_user.id}")
        event = self.last("account.deleted")
        self.assertEqual((event.target_user_id, event.target_username), (None, "sam"))
        self.assertEqual(audit_service.details_of(event), {"by": "admin"})
        kim = self.env.create_user("kim")
        kim_client = self.env.client("kim")
        kim_client.request("DELETE", "/v1/account", json={"password": PASSWORD})
        event = self.last("account.deleted")
        self.assertEqual((event.actor_user_id, event.actor_username, event.target_username), (None, "kim", "kim"))
        self.assertIsNotNone(kim)

    def test_no_secrets_in_the_log(self):
        sam = self.env.client("sam")
        habit = sam.post("/v1/habits", json={"name": "Lesen"}).json()
        key = sam.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPhone"}).json()["token"]
        link = self.admin.post("/v1/admin/invitations", json={"role": "user"}).json()["url"]
        sam.post("/v1/account/password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
        dump = json.dumps([[e.event, e.details] for e in self.events()])
        for secret in (PASSWORD, NEW_PASSWORD, key, link.split("#", 1)[1]):
            self.assertNotIn(secret, dump)

    def test_api_pages_and_filters(self):
        for _ in range(3):
            self.env.client("sam")
        response = self.admin.get("/v1/admin/audit", params={"limit": 2})
        self.assertEqual(response.status_code, 200, response.text)
        page = response.json()
        self.assertEqual(len(page["events"]), 2)
        self.assertGreater(page["events"][0]["id"], page["events"][1]["id"])
        rest = self.admin.get("/v1/admin/audit", params={"limit": 50, "before_id": page["next_before_id"]}).json()
        self.assertIsNone(rest["next_before_id"])
        self.assertEqual(len(page["events"]) + len(rest["events"]), len(self.events()))
        only_sam = self.admin.get("/v1/admin/audit", params={"user_id": self.sam_user.id}).json()["events"]
        self.assertEqual({e["actor_username"] for e in only_sam}, {"sam"})
        self.assertEqual(self.env.client("sam").get("/v1/admin/audit").status_code, 403)

    def test_old_entries_are_pruned(self):
        db = self.env.SessionLocal()
        try:
            db.add(AuditEvent(event="auth.login", created_at=utcnow() - timedelta(days=181)))
            db.add(AuditEvent(event="auth.login", created_at=utcnow() - timedelta(days=179)))
            db.commit()
            before = db.query(AuditEvent).count()
            self.assertEqual(audit_service.prune(db), 1)
            db.commit()
            self.assertEqual(db.query(AuditEvent).count(), before - 1)
            with mock.patch.dict("os.environ", {"AUDIT_RETENTION_DAYS": "30"}):
                self.assertEqual(audit_service.prune(db), 1)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
