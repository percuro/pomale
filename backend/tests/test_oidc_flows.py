"""Sign-in through OIDC end to end against the in-process fake provider."""

import unittest
from datetime import timedelta
from unittest import mock

from app.config import get_oidc_settings
from app.models.audit_event import AuditEvent
from app.models.invitation import Invitation
from app.models.oidc_state import OidcLoginState
from app.models.user import OidcIdentity, User, UserSession
from app.services import oidc_service, setup_service
from app.services.auth_service import utcnow
from app.services.invitation_service import invitation_rate_limiter
from app.services.oidc_client import OidcClient
from tests.oidc_fake import CLIENT_ID, CLIENT_SECRET, ISSUER, FakeProvider
from tests.support import PASSWORD, TEST_ORIGIN, ApiTestEnvironment

OIDC_ENV = {"OIDC_ISSUER": ISSUER, "OIDC_CLIENT_ID": CLIENT_ID, "OIDC_CLIENT_SECRET": CLIENT_SECRET}


class OidcTestCase(unittest.TestCase):
    extra_env: dict[str, str] = {}

    def setUp(self):
        self.env = ApiTestEnvironment()
        self._oidc_env = mock.patch.dict("os.environ", {**OIDC_ENV, **self.extra_env})
        self._oidc_env.start()
        self.provider = FakeProvider()
        self.provider.add_user("sub-anna", email="anna@example.org", preferred_username="anna", name="Anna A.")
        self.provider.add_user("sub-ben", email="ben@example.org", preferred_username="ben")
        self.oidc_client = OidcClient(get_oidc_settings(), transport=self.provider)
        self._client = mock.patch.object(oidc_service, "client_for", lambda _settings: self.oidc_client)
        self._client.start()
        oidc_service.oidc_rate_limiter.reset()
        invitation_rate_limiter.reset()

    def tearDown(self):
        self._client.stop()
        self._oidc_env.stop()
        self.env.close()

    # --- Helpers ------------------------------------------------------------

    def start(self, client, path="/v1/auth/oidc/start", **body):
        response = client.post(path, json=body or {"purpose": "login"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["authorize_url"]

    def finish(self, client, url, subject, **auth) -> str:
        """Sign in at the provider and come back; returns where the web app is sent (path#fragment)."""
        callback = self.provider.sign_in(url, subject, **auth)
        response = client.get("/v1/auth/oidc/callback", params=callback, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text)
        location = response.headers["location"]
        self.assertTrue(location.startswith(TEST_ORIGIN), location)
        return location[len(TEST_ORIGIN) :]

    def sign_in(self, client, subject, path="/v1/auth/oidc/start", **body) -> str:
        return self.finish(client, self.start(client, path, **body), subject)

    def guest(self):
        return self.env.client(username=None)

    def db(self):
        return self.env.SessionLocal()

    def query(self, model, **filters):
        db = self.db()
        try:
            return db.query(model).filter_by(**filters).all()
        finally:
            db.close()

    def link(self, username, subject):
        db = self.db()
        try:
            user = db.query(User).filter_by(username=username).one()
            db.add(OidcIdentity(user_id=user.id, issuer=ISSUER, subject=subject))
            db.commit()
        finally:
            db.close()

    def events(self, name):
        return self.query(AuditEvent, event=name)

    def assertCode(self, response, status, code):
        self.assertEqual((response.status_code, response.json().get("code")), (status, code), response.text)


class OidcLoginTest(OidcTestCase):
    def setUp(self):
        super().setUp()
        self.alex = self.env.create_user("alex", role="admin")

    def test_meta_announces_oidc(self):
        with mock.patch.dict("os.environ", {"OIDC_LABEL": "Authelia"}):
            meta = self.guest().get("/v1/meta").json()
        self.assertEqual((meta["password_login"], meta["oidc"]), (True, {"label": "Authelia"}))

    def test_unknown_subject_has_no_account(self):
        self.assertEqual(self.sign_in(self.guest(), "sub-anna"), "/login#error=oidc.no_account")
        self.assertEqual(self.query(User, username="anna"), [])
        failed = self.events("auth.login_failed")
        self.assertEqual(len(failed), 1)
        self.assertIn('"method": "oidc"', failed[0].details)

    def test_link_then_sign_in_with_the_provider(self):
        alex = self.env.client("alex")
        url = self.start(alex, purpose="link", password=PASSWORD, return_to="/account")
        self.assertEqual(self.finish(alex, url, "sub-anna"), "/account#oidc=linked")
        me = alex.get("/v1/auth/me").json()
        self.assertEqual(me["oidc"]["email"], "anna@example.org")
        self.assertEqual(me["oidc"]["preferred_username"], "anna")

        guest = self.guest()
        self.assertEqual(self.sign_in(guest, "sub-anna"), "/")
        self.assertEqual(guest.get("/v1/auth/me").json()["username"], "alex")
        sessions = self.query(UserSession, auth_method="oidc")
        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(self.events("auth.login")), 2)
        self.assertEqual(len(self.events("account.oidc_linked")), 1)

    def test_linking_needs_the_password_and_no_existing_link(self):
        alex = self.env.client("alex")
        self.assertCode(alex.post("/v1/auth/oidc/start", json={"purpose": "link"}), 403, "account.wrong_password")
        self.link("alex", "sub-anna")
        response = alex.post("/v1/auth/oidc/start", json={"purpose": "link", "password": PASSWORD})
        self.assertCode(response, 409, "oidc.already_linked")
        self.assertEqual(self.guest().post("/v1/auth/oidc/start", json={"purpose": "link"}).status_code, 401)

    def test_subject_of_another_account_cannot_be_linked(self):
        self.env.create_user("sam")
        self.link("sam", "sub-anna")
        alex = self.env.client("alex")
        url = self.start(alex, purpose="link", password=PASSWORD)
        self.assertEqual(self.finish(alex, url, "sub-anna"), "/account#error=oidc.already_linked")

    def test_state_must_match_the_browser(self):
        guest, other = self.guest(), self.guest()
        url = self.start(guest)
        callback = self.provider.sign_in(url, "sub-anna")
        # Another browser (no cookie) cannot finish this sign-in
        response = other.get("/v1/auth/oidc/callback", params=callback, follow_redirects=False)
        self.assertTrue(response.headers["location"].endswith("/login#error=oidc.state_invalid"))
        # A forged state with the right cookie neither
        response = guest.get("/v1/auth/oidc/callback", params={**callback, "state": "forged"}, follow_redirects=False)
        self.assertTrue(response.headers["location"].endswith("#error=oidc.state_invalid"))

    def test_state_is_used_once_and_expires(self):
        self.link("alex", "sub-anna")
        guest = self.guest()
        url = self.start(guest)
        callback = self.provider.sign_in(url, "sub-anna")
        cookie = guest.cookies.get(oidc_service.STATE_COOKIE_NAME)
        guest.get("/v1/auth/oidc/callback", params=callback, follow_redirects=False)
        replay = self.guest()
        replay.cookies.set(oidc_service.STATE_COOKIE_NAME, cookie)
        response = replay.get("/v1/auth/oidc/callback", params=callback, follow_redirects=False)
        self.assertTrue(response.headers["location"].endswith("#error=oidc.state_invalid"))

        late = self.guest()
        url = self.start(late)
        db = self.db()
        try:
            db.query(OidcLoginState).update({"expires_at": utcnow() - timedelta(seconds=1)})
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.finish(late, url, "sub-anna"), "/login#error=oidc.state_invalid")

    def test_state_cookie_is_lax_and_http_only(self):
        with mock.patch.dict("os.environ", {"COOKIE_SAMESITE": "strict"}):
            response = self.guest().post("/v1/auth/oidc/start", json={"purpose": "login"})
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("pomale_oidc=", cookie)
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("path=/v1/auth/oidc", cookie)

    def test_provider_reports_access_denied(self):
        guest = self.guest()
        url = self.start(guest)
        state = self.provider.sign_in(url, "sub-anna")["state"]
        response = guest.get(
            "/v1/auth/oidc/callback", params={"state": state, "error": "access_denied"}, follow_redirects=False
        )
        self.assertTrue(response.headers["location"].endswith("/login#error=oidc.denied"))

    def test_invalid_token_is_an_error(self):
        self.link("alex", "sub-anna")
        self.provider.claim_overrides = {"aud": "someone-else"}
        self.assertEqual(self.sign_in(self.guest(), "sub-anna"), "/login#error=oidc.invalid_response")

    def test_deactivated_account_cannot_sign_in(self):
        self.env.create_user("sam")
        self.link("sam", "sub-ben")
        db = self.db()
        try:
            db.query(User).filter_by(username="sam").update({"is_active": False})
            db.commit()
        finally:
            db.close()
        self.assertEqual(self.sign_in(self.guest(), "sub-ben"), "/login#error=auth.account_disabled")

    def test_unlink_needs_a_remaining_password(self):
        self.link("alex", "sub-anna")
        alex = self.env.client("alex")
        self.assertCode(alex.request("DELETE", "/v1/account/oidc", json={}), 403, "account.wrong_password")
        self.assertEqual(alex.request("DELETE", "/v1/account/oidc", json={"password": PASSWORD}).status_code, 204)
        self.assertIsNone(alex.get("/v1/auth/me").json()["oidc"])
        self.assertCode(alex.request("DELETE", "/v1/account/oidc", json={"password": PASSWORD}), 404, "oidc.not_linked")
        kim = self.env.create_passwordless_user("kim")
        self.link("kim", "sub-ben")
        kim_client = self.env.session_client(kim)
        self.assertCode(kim_client.request("DELETE", "/v1/account/oidc", json={}), 409, "account.last_login_method")

    def test_admin_unlink_signs_the_account_out(self):
        kim = self.env.create_passwordless_user("kim")
        self.link("kim", "sub-ben")
        kim_client = self.env.session_client(kim)
        admin = self.env.client("alex")
        self.assertEqual(admin.delete(f"/v1/admin/users/{kim.id}/oidc").status_code, 204)
        self.assertEqual(kim_client.get("/v1/auth/me").status_code, 401)
        users = {u["username"]: u for u in admin.get("/v1/admin/users").json()}
        self.assertFalse(users["kim"]["oidc_linked"])
        self.assertEqual(self.events("account.oidc_unlinked")[0].actor_username, "alex")

    def test_return_to_only_inside_the_app(self):
        kim = self.env.create_passwordless_user("kim")
        self.link("kim", "sub-ben")
        client = self.env.session_client(kim)
        url = self.start(client, purpose="reauth", return_to="https://evil.test/")
        self.assertEqual(self.finish(client, url, "sub-ben"), "/account#reauth=ok")

    def test_provider_down_at_start(self):
        self.provider.down = True
        self.assertCode(
            self.guest().post("/v1/auth/oidc/start", json={"purpose": "login"}), 503, "oidc.provider_unavailable"
        )


class OidcReauthTest(OidcTestCase):
    def setUp(self):
        super().setUp()
        self.env.create_user("admin", role="admin")
        self.kim = self.env.create_passwordless_user("kim")
        self.link("kim", "sub-ben")

    def test_reauth_unlocks_sensitive_changes(self):
        client = self.env.session_client(self.kim, authenticated_at=utcnow() - timedelta(hours=1))
        self.assertCode(client.request("DELETE", "/v1/account", json={}), 403, "auth.reauth_required")
        url = self.start(client, purpose="reauth", return_to="/account")
        self.assertIn("prompt=login", url)
        self.assertEqual(self.finish(client, url, "sub-ben"), "/account#reauth=ok")
        self.assertEqual(client.request("DELETE", "/v1/account", json={}).status_code, 204)

    def test_reauth_with_another_provider_account(self):
        client = self.env.session_client(self.kim, authenticated_at=utcnow() - timedelta(hours=1))
        url = self.start(client, purpose="reauth")
        self.assertEqual(self.finish(client, url, "sub-anna"), "/account#error=oidc.wrong_account")
        self.assertCode(client.request("DELETE", "/v1/account", json={}), 403, "auth.reauth_required")


class OidcInvitationTest(OidcTestCase):
    def setUp(self):
        super().setUp()
        self.env.create_user("admin", role="admin")
        self.admin = self.env.client("admin")

    def invitation(self, role="user") -> str:
        return self.admin.post("/v1/admin/invitations", json={"role": role}).json()["url"].split("#", 1)[1]

    def test_signup_through_the_provider(self):
        token = self.invitation(role="admin")
        guest = self.guest()
        url = self.start(guest, "/v1/invitations/oidc", token=token, username="Anna", timezone="Europe/Berlin")
        self.assertEqual(self.finish(guest, url, "sub-anna"), "/")
        me = guest.get("/v1/auth/me").json()
        self.assertEqual(
            (me["username"], me["role"], me["has_password"], me["timezone"], me["display_name"]),
            ("anna", "admin", False, "Europe/Berlin", "Anna A."),
        )
        invitation = self.query(Invitation)[0]
        self.assertIsNotNone(invitation.used_at)
        self.assertEqual(invitation.used_by_user_id, me["id"])
        # The link is used up
        self.assertCode(
            guest.post("/v1/invitations/oidc", json={"token": token, "username": "x1y"}), 404, "invite.invalid"
        )

    def test_username_is_checked_before_leaving(self):
        token = self.invitation()
        response = self.guest().post("/v1/invitations/oidc", json={"token": token, "username": "admin"})
        self.assertCode(response, 409, "account.username_taken")
        response = self.guest().post("/v1/invitations/oidc", json={"token": token, "username": "A B"})
        self.assertCode(response, 422, "account.invalid_username")

    def test_already_linked_subject_keeps_the_invitation(self):
        self.link("admin", "sub-anna")
        token = self.invitation()
        guest = self.guest()
        url = self.start(guest, "/v1/invitations/oidc", token=token, username="anna")
        self.assertEqual(self.finish(guest, url, "sub-anna"), "/login#error=oidc.already_linked")
        self.assertIsNone(self.query(Invitation)[0].used_at)
        url = self.start(guest, "/v1/invitations/oidc", token=token, username="anna")
        self.assertEqual(self.finish(guest, url, "sub-ben"), "/")

    def test_recover_links_a_new_provider_account(self):
        kim = self.env.create_passwordless_user("kim")
        self.link("kim", "sub-anna")
        old_session = self.env.session_client(kim)
        self.admin.delete(f"/v1/admin/users/{kim.id}/oidc")
        reset = self.admin.post(f"/v1/admin/users/{kim.id}/password-reset").json()["url"].split("#", 1)[1]
        guest = self.guest()
        url = self.start(guest, "/v1/invitations/oidc", token=reset)
        self.assertEqual(self.finish(guest, url, "sub-ben"), "/")
        self.assertEqual(guest.get("/v1/auth/me").json()["username"], "kim")
        self.assertEqual(old_session.get("/v1/auth/me").status_code, 401)
        self.assertEqual([i.subject for i in self.query(OidcIdentity)], ["sub-ben"])

    def test_recover_with_the_subject_of_someone_else(self):
        kim = self.env.create_passwordless_user("kim")
        self.link("admin", "sub-anna")
        reset = self.admin.post(f"/v1/admin/users/{kim.id}/password-reset").json()["url"].split("#", 1)[1]
        guest = self.guest()
        url = self.start(guest, "/v1/invitations/oidc", token=reset)
        self.assertEqual(self.finish(guest, url, "sub-anna"), "/login#error=oidc.already_linked")


class OidcAutoCreateTest(OidcTestCase):
    extra_env = {"OIDC_AUTO_CREATE": "on"}

    def test_accounts_are_created_from_the_claims(self):
        self.env.create_user("admin", role="admin")
        self.env.create_user("anna")
        guest = self.guest()
        self.assertEqual(self.sign_in(guest, "sub-anna"), "/")
        me = guest.get("/v1/auth/me").json()
        self.assertEqual((me["username"], me["role"], me["display_name"]), ("anna-2", "user", "Anna A."))
        self.assertEqual(self.events("account.created")[-1].details, '{"via": "oidc"}')
        # Second sign-in finds the same account
        again = self.guest()
        self.sign_in(again, "sub-anna")
        self.assertEqual(again.get("/v1/auth/me").json()["id"], me["id"])

    def test_not_before_setup(self):
        self.assertEqual(self.sign_in(self.guest(), "sub-anna"), "/login#error=setup.required")

    def test_username_suggestions(self):
        from app.services.oidc_client import Identity

        suggest = oidc_service.suggest_username
        self.assertEqual(suggest(Identity(ISSUER, "s", preferred_username="Anna.Berg")), "anna.berg")
        self.assertEqual(suggest(Identity(ISSUER, "s", preferred_username="ä", email="Ben+x@example.org")), "benx")
        self.assertEqual(suggest(Identity(ISSUER, "s")), "user")


class OidcSetupTest(OidcTestCase):
    def test_first_admin_through_the_provider(self):
        token = setup_service.issue_token()
        guest = self.guest()
        response = guest.post("/v1/setup/oidc", json={"token": "wrong", "username": "anna"})
        self.assertCode(response, 403, "setup.invalid_token")
        url = self.start(guest, "/v1/setup/oidc", token=token, username="anna", locale="de")
        self.assertEqual(self.finish(guest, url, "sub-anna"), "/")
        me = guest.get("/v1/auth/me").json()
        self.assertEqual((me["username"], me["role"], me["has_password"], me["locale"]), ("anna", "admin", False, "de"))
        self.assertFalse(setup_service.token_matches(token))
        self.assertCode(guest.post("/v1/setup/oidc", json={"token": token, "username": "x1y"}), 409, "setup.done")


class PasswordLoginOffTest(OidcTestCase):
    extra_env = {"PASSWORD_LOGIN": "off", "REGISTRATION": "open"}

    def test_passwords_are_refused_everywhere(self):
        self.env.create_user("admin", role="admin")
        guest = self.guest()
        self.assertCode(
            guest.post("/v1/auth/login", json={"username": "admin", "password": PASSWORD}),
            403,
            "auth.password_login_disabled",
        )
        self.assertCode(
            guest.post("/v1/auth/register", json={"username": "newbie", "password": PASSWORD}),
            403,
            "auth.password_login_disabled",
        )
        self.assertCode(
            guest.post("/v1/invitations/accept", json={"token": "x", "username": "y", "password": PASSWORD}),
            403,
            "auth.password_login_disabled",
        )
        self.assertCode(
            guest.post("/v1/setup", json={"token": "x", "username": "y", "password": PASSWORD}),
            403,
            "auth.password_login_disabled",
        )
        admin = self.env.session_client(self.query(User, username="admin")[0])
        self.assertCode(
            admin.post("/v1/account/password", json={"current_password": PASSWORD, "new_password": "x" * 12}),
            403,
            "auth.password_login_disabled",
        )
        self.link("admin", "sub-anna")
        self.assertCode(
            admin.request("DELETE", "/v1/account/oidc", json={"password": PASSWORD}), 409, "account.last_login_method"
        )
        self.assertEqual(guest.get("/v1/meta").json()["password_login"], False)


class OidcDisabledTest(unittest.TestCase):
    def test_start_is_not_found(self):
        env = ApiTestEnvironment()
        try:
            response = env.client(username=None).post("/v1/auth/oidc/start", json={"purpose": "login"})
            self.assertEqual((response.status_code, response.json()["code"]), (404, "oidc.disabled"))
            self.assertIsNone(env.client(username=None).get("/v1/meta").json()["oidc"])
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
