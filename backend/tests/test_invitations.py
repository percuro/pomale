import os
import unittest
from datetime import timedelta
from unittest import mock

from app import __version__, config
from app.api.routers.auth import register_rate_limiter
from app.models.invitation import Invitation
from app.models.user import User
from app.services.auth_service import utcnow
from app.services.invitation_service import InvitationService, invitation_rate_limiter
from tests.support import PASSWORD, TEST_ORIGIN, ApiTestEnvironment

NEW_PASSWORD = "ein-ganz-neues-passwort"


class InvitationTestCase(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.admin_user = self.env.create_user("admin", role="admin")
        self.sam_user = self.env.create_user("sam")
        self.admin = self.env.client("admin")
        self.sam = self.env.client("sam")
        self.guest = self.env.client(username=None)
        invitation_rate_limiter.reset()
        register_rate_limiter.reset()

    def tearDown(self):
        self.env.close()

    def invite(self, **body) -> tuple[dict, str]:
        response = self.admin.post("/v1/admin/invitations", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        return created, created["url"].split("#", 1)[1]

    def accept(self, token, client=None, **body):
        payload = {"token": token, "password": NEW_PASSWORD} | body
        return (client or self.guest).post("/v1/invitations/accept", json=payload)

    def assertCode(self, response, status, code):
        self.assertEqual((response.status_code, response.json().get("code")), (status, code), response.text)

    def db_invitations(self) -> list[Invitation]:
        db = self.env.SessionLocal()
        try:
            return db.query(Invitation).all()
        finally:
            db.close()


class SignupInvitationTest(InvitationTestCase):
    def test_link_carries_the_token_in_the_fragment_and_only_its_hash_is_stored(self):
        created, token = self.invite(note="für Anna")
        self.assertTrue(created["url"].startswith(f"{TEST_ORIGIN}/invite#"))
        self.assertNotIn("?", created["url"])
        self.assertGreaterEqual(len(token), 40)
        stored = self.db_invitations()[0]
        self.assertNotIn(token, stored.token_hash)
        listed = self.admin.get("/v1/admin/invitations").json()
        self.assertEqual([(i["note"], i["purpose"], i["role"]) for i in listed], [("für Anna", "signup", "user")])
        self.assertNotIn(token, str(listed))
        self.assertNotIn("url", listed[0])

    def test_expiry_defaults_to_seven_days_and_is_configurable(self):
        created, _ = self.invite()
        stored = self.db_invitations()[0]
        self.assertAlmostEqual(stored.expires_at - stored.created_at, timedelta(days=7), delta=timedelta(minutes=1))
        self.assertIn("expires_at", created)
        with mock.patch.dict(os.environ, {"INVITE_EXPIRY_DAYS": "2"}):
            self.invite()
        newest = max(self.db_invitations(), key=lambda i: i.id)
        self.assertAlmostEqual(newest.expires_at - newest.created_at, timedelta(days=2), delta=timedelta(minutes=1))

    def test_inspect_and_accept(self):
        _, token = self.invite(role="admin")
        info = self.guest.post("/v1/invitations/inspect", json={"token": token}).json()
        self.assertEqual((info["purpose"], info["username"]), ("signup", None))
        response = self.accept(token, username="Anna", timezone="Europe/Berlin", locale="de", display_name="Anna")
        self.assertEqual(response.status_code, 200, response.text)
        me = self.guest.get("/v1/auth/me").json()
        self.assertEqual(
            (me["username"], me["role"], me["timezone"], me["locale"], me["display_name"]),
            ("anna", "admin", "Europe/Berlin", "de", "Anna"),
        )
        stored = self.db_invitations()[0]
        self.assertEqual(stored.used_by_user_id, me["id"])
        self.assertEqual(self.admin.get("/v1/admin/invitations").json(), [])

    def test_a_link_works_only_once(self):
        _, token = self.invite()
        self.assertEqual(self.accept(token, username="anna").status_code, 200)
        self.assertCode(
            self.accept(token, username="bert", client=self.env.client(username=None)), 404, "invite.invalid"
        )
        self.assertCode(self.guest.post("/v1/invitations/inspect", json={"token": token}), 404, "invite.invalid")

    def test_simultaneous_use_creates_one_account(self):
        _, token = self.invite()
        db = self.env.SessionLocal()
        stale = db.query(Invitation).one()
        db.expunge(stale)
        db.close()
        self.assertEqual(self.accept(token, username="anna").status_code, 200)
        # The second request read the link before the first one marked it as used
        with mock.patch.object(InvitationService, "_find_valid", return_value=stale):
            self.assertCode(
                self.accept(token, username="bert", client=self.env.client(username=None)), 404, "invite.invalid"
            )
        db = self.env.SessionLocal()
        self.assertEqual(db.query(User).filter(User.username == "bert").count(), 0)
        db.close()

    def test_failed_attempts_do_not_use_up_the_link(self):
        _, token = self.invite()
        self.assertCode(self.accept(token), 422, "account.invalid_username")
        self.assertCode(self.accept(token, username="sam"), 409, "account.username_taken")
        self.assertCode(self.accept(token, username="anna", password="kurz"), 422, "account.password_too_short")
        self.assertEqual(self.accept(token, username="anna").status_code, 200)

    def test_expired_and_revoked_links(self):
        created, token = self.invite()
        db = self.env.SessionLocal()
        db.query(Invitation).update({Invitation.expires_at: utcnow() - timedelta(seconds=1)})
        db.commit()
        db.close()
        self.assertCode(self.accept(token, username="anna"), 404, "invite.invalid")
        self.assertEqual(self.admin.get("/v1/admin/invitations").json(), [])

        created, token = self.invite()
        self.assertEqual(self.admin.delete(f"/v1/admin/invitations/{created['id']}").status_code, 204)
        self.assertCode(self.accept(token, username="anna"), 404, "invite.invalid")
        self.assertCode(self.admin.delete(f"/v1/admin/invitations/{created['id']}"), 404, "invite.not_found")

    def test_wrong_tokens_are_rate_limited_per_ip(self):
        for _ in range(5):
            self.guest.post("/v1/invitations/inspect", json={"token": "wrong"})
        _, token = self.invite()
        self.assertCode(self.accept(token, username="anna"), 429, "auth.rate_limited")

    def test_only_admins_manage_invitations(self):
        self.assertCode(self.sam.post("/v1/admin/invitations", json={}), 403, "auth.forbidden")
        self.assertCode(self.sam.get("/v1/admin/invitations"), 403, "auth.forbidden")


class PasswordResetTest(InvitationTestCase):
    def reset_link(self, user=None) -> tuple[dict, str]:
        response = self.admin.post(f"/v1/admin/users/{(user or self.sam_user).id}/password-reset")
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        return created, created["url"].split("#", 1)[1]

    def test_reset_sets_a_new_password_and_logs_out_everywhere(self):
        created, token = self.reset_link()
        self.assertEqual(created["purpose"], "password_reset")
        info = self.guest.post("/v1/invitations/inspect", json={"token": token}).json()
        self.assertEqual((info["purpose"], info["username"]), ("password_reset", "sam"))
        self.assertEqual(self.accept(token).json()["username"], "sam")
        self.assertEqual(self.sam.get("/v1/auth/me").status_code, 401)
        self.assertEqual(self.guest.get("/v1/auth/me").json()["username"], "sam")
        self.env.client("sam", NEW_PASSWORD)
        old = self.env.client(username=None).post("/v1/auth/login", json={"username": "sam", "password": PASSWORD})
        self.assertEqual(old.status_code, 401)

    def test_reset_link_is_valid_for_24_hours_and_only_the_newest_works(self):
        _, first = self.reset_link()
        _, second = self.reset_link()
        stored = max(self.db_invitations(), key=lambda i: i.id)
        self.assertAlmostEqual(stored.expires_at - stored.created_at, timedelta(hours=24), delta=timedelta(minutes=1))
        self.assertCode(self.accept(first), 404, "invite.invalid")
        self.assertEqual(self.accept(second).status_code, 200)

    def test_reset_ignores_a_username_in_the_request(self):
        _, token = self.reset_link()
        self.assertEqual(self.accept(token, username="admin").json()["username"], "sam")

    def test_inactive_accounts(self):
        self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"is_active": False})
        self.assertCode(
            self.admin.post(f"/v1/admin/users/{self.sam_user.id}/password-reset"), 409, "admin.user_inactive"
        )
        self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"is_active": True})
        _, token = self.reset_link()
        self.admin.patch(f"/v1/admin/users/{self.sam_user.id}", json={"is_active": False})
        self.assertCode(self.accept(token), 404, "invite.invalid")

    def test_reset_links_disappear_with_the_account(self):
        self.reset_link()
        self.admin.delete(f"/v1/admin/users/{self.sam_user.id}")
        self.assertEqual(self.db_invitations(), [])

    def test_only_admins_create_reset_links(self):
        self.assertCode(self.sam.post(f"/v1/admin/users/{self.admin_user.id}/password-reset"), 403, "auth.forbidden")


class RegistrationAndMetaTest(InvitationTestCase):
    def register(self, username="anna", **body):
        return self.guest.post("/v1/auth/register", json={"username": username, "password": PASSWORD} | body)

    def test_closed_by_default(self):
        self.assertCode(self.register(), 403, "registration.closed")
        self.assertEqual(
            self.guest.get("/v1/meta").json(),
            {
                "version": __version__,
                "registration": "invite",
                "setup_needed": False,
                "password_login": True,
                "oidc": None,
            },
        )

    def test_open_registration_creates_normal_accounts(self):
        with mock.patch.dict(os.environ, {"REGISTRATION": "open"}):
            self.assertEqual(self.guest.get("/v1/meta").json()["registration"], "open")
            response = self.register(locale="en")
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual((response.json()["role"], response.json()["locale"]), ("user", "en"))
            self.assertEqual(self.guest.get("/v1/auth/me").json()["username"], "anna")
            self.assertCode(self.register(), 409, "account.username_taken")

    def test_open_registration_is_rate_limited(self):
        with mock.patch.dict(os.environ, {"REGISTRATION": "open"}):
            for index in range(5):
                self.register(username=f"user{index}")
            self.assertCode(self.register(username="user9"), 429, "auth.rate_limited")

    def test_no_registration_before_setup(self):
        db = self.env.SessionLocal()
        db.query(User).delete()
        db.commit()
        db.close()
        with mock.patch.dict(os.environ, {"REGISTRATION": "open"}):
            self.assertTrue(self.guest.get("/v1/meta").json()["setup_needed"])
            self.assertCode(self.register(), 409, "setup.required")

    def test_invalid_registration_setting_stops_startup(self):
        with mock.patch.dict(os.environ, {"REGISTRATION": "everyone"}):
            with self.assertRaises(config.ConfigError):
                config.validate()


if __name__ == "__main__":
    unittest.main()
