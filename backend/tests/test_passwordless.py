"""Accounts without a password (OIDC only) and how sensitive changes are confirmed."""

import unittest
from datetime import timedelta

from app.models.audit_event import AuditEvent
from app.models.user import User, UserSession
from app.services.auth_service import utcnow
from tests.support import PASSWORD, ApiTestEnvironment

NEW_PASSWORD = "ein-neues-passwort-456"


class PasswordlessAccountTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user("admin", role="admin")
        self.kim = self.env.create_passwordless_user("kim")

    def tearDown(self):
        self.env.close()

    def assertCode(self, response, status, code):
        self.assertEqual((response.status_code, response.json().get("code")), (status, code), response.text)

    def stale_client(self):
        return self.env.session_client(self.kim, authenticated_at=utcnow() - timedelta(minutes=11))

    def test_password_login_never_works(self):
        guest = self.env.client(username=None)
        for password in (PASSWORD, "", "!"):
            response = guest.post("/v1/auth/login", json={"username": "kim", "password": password or "x"})
            self.assertCode(response, 401, "auth.invalid_credentials")

    def test_me_and_admin_list_show_login_methods(self):
        me = self.env.session_client(self.kim).get("/v1/auth/me").json()
        self.assertEqual((me["has_password"], me["oidc"]), (False, None))
        users = {u["username"]: u for u in self.env.client("admin").get("/v1/admin/users").json()}
        self.assertEqual((users["kim"]["has_password"], users["kim"]["oidc_linked"]), (False, False))
        self.assertEqual(users["admin"]["has_password"], True)

    def test_set_a_first_password_after_a_fresh_provider_login(self):
        client = self.env.session_client(self.kim)
        response = client.post("/v1/account/password", json={"new_password": NEW_PASSWORD})
        self.assertEqual(response.status_code, 204, response.text)
        self.assertTrue(client.get("/v1/auth/me").json()["has_password"])
        self.env.client("kim", password=NEW_PASSWORD)
        db = self.env.SessionLocal()
        try:
            self.assertEqual(db.query(AuditEvent).filter(AuditEvent.event == "account.password_set").count(), 1)
        finally:
            db.close()

    def test_stale_session_has_to_sign_in_again(self):
        client = self.stale_client()
        self.assertCode(
            client.post("/v1/account/password", json={"new_password": NEW_PASSWORD}), 403, "auth.reauth_required"
        )
        self.assertCode(client.request("DELETE", "/v1/account", json={}), 403, "auth.reauth_required")

    def test_password_sessions_of_passwordless_accounts_do_not_count(self):
        client = self.env.session_client(self.kim, auth_method="password")
        self.assertCode(client.request("DELETE", "/v1/account", json={}), 403, "auth.reauth_required")

    def test_delete_after_a_fresh_provider_login(self):
        response = self.env.session_client(self.kim).request("DELETE", "/v1/account", json={})
        self.assertEqual(response.status_code, 204, response.text)
        db = self.env.SessionLocal()
        try:
            self.assertIsNone(db.query(User).filter(User.username == "kim").first())
        finally:
            db.close()


class PasswordAccountTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.alex = self.env.create_user("alex", role="admin")

    def tearDown(self):
        self.env.close()

    def test_password_is_still_required(self):
        client = self.env.client("alex")
        response = client.post("/v1/account/password", json={"new_password": NEW_PASSWORD})
        self.assertEqual((response.status_code, response.json()["code"]), (403, "account.wrong_password"))
        response = client.request("DELETE", "/v1/account", json={})
        self.assertEqual((response.status_code, response.json()["code"]), (403, "account.wrong_password"))
        # A fresh OIDC session does not replace the password for accounts that have one
        oidc_client = self.env.session_client(self.alex)
        response = oidc_client.request("DELETE", "/v1/account", json={})
        self.assertEqual(response.status_code, 403)

    def test_password_login_records_method_and_time(self):
        self.env.client("alex")
        db = self.env.SessionLocal()
        try:
            session = db.query(UserSession).one()
            self.assertEqual(session.auth_method, "password")
            self.assertIsNotNone(session.authenticated_at)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
