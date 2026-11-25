import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from app.cli import create_user, set_role
from app.models.habit import Habit
from app.models.user import User
from app.services.shortcut_service import shortcut_rate_limiter
from tests.support import PASSWORD, ApiTestEnvironment

ADMIN_USER_FIELDS = {"id", "username", "display_name", "role", "is_active", "created_at", "last_seen_at"}


class AdminApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.admin_user = self.env.create_user("admin", role="admin")
        self.sam_user = self.env.create_user("sam", display_name="Sam")
        self.admin = self.env.client("admin")
        self.sam = self.env.client("sam")
        shortcut_rate_limiter.reset()

    def tearDown(self):
        self.env.close()

    def users(self) -> dict[str, dict]:
        return {u["username"]: u for u in self.admin.get("/v1/admin/users").json()}

    def patch(self, user, body, client=None):
        return (client or self.admin).patch(f"/v1/admin/users/{user.id}", json=body)

    def assertCode(self, response, status, code):
        self.assertEqual((response.status_code, response.json().get("code")), (status, code), response.text)

    def test_normal_accounts_get_403_everywhere(self):
        for method, path in (
            ("GET", "/v1/admin/users"),
            ("PATCH", f"/v1/admin/users/{self.sam_user.id}"),
            ("DELETE", f"/v1/admin/users/{self.admin_user.id}"),
        ):
            response = self.sam.request(method, path, json={"role": "admin"})
            self.assertCode(response, 403, "auth.forbidden")
        self.assertEqual(self.env.client(username=None).get("/v1/admin/users").status_code, 401)

    def test_list_shows_metadata_only(self):
        self.sam.post("/v1/habits", json={"name": "Geheime Gewohnheit"})
        response = self.admin.get("/v1/admin/users")
        self.assertNotIn("Geheime", response.text)
        users = {u["username"]: u for u in response.json()}
        self.assertEqual(set(users), {"admin", "sam"})
        self.assertEqual(set(users["sam"]), ADMIN_USER_FIELDS)
        self.assertEqual((users["sam"]["role"], users["sam"]["display_name"]), ("user", "Sam"))
        self.assertIsNotNone(users["sam"]["last_seen_at"])

    def test_promote_and_demote(self):
        self.assertEqual(self.patch(self.sam_user, {"role": "admin"}).json()["role"], "admin")
        self.assertEqual(self.sam.get("/v1/admin/users").status_code, 200)
        self.assertEqual(self.patch(self.admin_user, {"role": "user"}, client=self.sam).json()["role"], "user")
        self.assertCode(self.admin.get("/v1/admin/users"), 403, "auth.forbidden")

    def test_last_active_admin_is_protected(self):
        self.assertCode(self.patch(self.admin_user, {"role": "user"}), 409, "account.last_admin")
        # A deactivated second admin does not help
        self.patch(self.sam_user, {"role": "admin"})
        self.patch(self.sam_user, {"is_active": False})
        self.assertCode(self.patch(self.admin_user, {"role": "user"}), 409, "account.last_admin")
        self.assertEqual(self.users()["admin"]["role"], "admin")

    def test_cannot_deactivate_or_delete_yourself(self):
        self.patch(self.sam_user, {"role": "admin"})
        self.assertCode(self.patch(self.admin_user, {"is_active": False}), 409, "admin.self_deactivate")
        self.assertCode(self.admin.delete(f"/v1/admin/users/{self.admin_user.id}"), 409, "admin.self_delete")

    def test_deactivate_logs_out_at_once_and_stops_shortcut_keys(self):
        habit = self.sam.post("/v1/habits", json={"name": "Lesen"}).json()
        token = self.sam.post(f"/v1/habits/{habit['id']}/shortcut-tokens", json={"label": "iPhone"}).json()["token"]
        phone = self.env.client(username=None)
        phone.headers.clear()

        def tap():
            return phone.put(
                f"/v1/habits/{habit['id']}/days/today", headers={"Authorization": f"Bearer {token}"}, json={}
            )

        self.assertEqual(self.patch(self.sam_user, {"is_active": False}).json()["is_active"], False)
        self.assertEqual(self.sam.get("/v1/auth/me").status_code, 401)
        self.assertEqual(tap().status_code, 401)
        login = self.env.client(username=None).post("/v1/auth/login", json={"username": "sam", "password": PASSWORD})
        self.assertEqual(login.status_code, 401)
        # Data stays; reactivating restores access
        self.patch(self.sam_user, {"is_active": True})
        sam = self.env.client("sam")
        self.assertEqual([h["name"] for h in sam.get("/v1/habits").json()], ["Lesen"])
        self.assertEqual(tap().status_code, 200)

    def test_delete_account_with_data(self):
        self.sam.post("/v1/habits", json={"name": "Lesen"})
        self.assertEqual(self.admin.delete(f"/v1/admin/users/{self.sam_user.id}").status_code, 204)
        self.assertEqual(set(self.users()), {"admin"})
        db = self.env.SessionLocal()
        self.assertEqual(db.query(Habit).count(), 0)
        db.close()
        self.assertEqual(self.sam.get("/v1/auth/me").status_code, 401)

    def test_unknown_account(self):
        self.assertCode(self.admin.patch("/v1/admin/users/999", json={"role": "user"}), 404, "account.not_found")
        self.assertCode(self.admin.delete("/v1/admin/users/999"), 404, "account.not_found")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.patches = [
            mock.patch.object(create_user, "SessionLocal", self.env.SessionLocal),
            mock.patch.object(set_role, "SessionLocal", self.env.SessionLocal),
            mock.patch("getpass.getpass", return_value=PASSWORD),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.env.close()

    def run_cli(self, module, *args) -> str:
        out = io.StringIO()
        with mock.patch.object(sys, "argv", ["cli", *args]), redirect_stdout(out):
            module.main()
        return out.getvalue()

    def role(self, username: str) -> str:
        db = self.env.SessionLocal()
        try:
            return db.query(User).filter(User.username == username).one().role
        finally:
            db.close()

    def test_first_account_is_admin_then_user_by_default(self):
        self.run_cli(create_user, "alex")
        self.run_cli(create_user, "sam")
        self.run_cli(create_user, "kim", "--role", "admin")
        self.assertEqual([self.role(n) for n in ("alex", "sam", "kim")], ["admin", "user", "admin"])

    def test_set_role_is_the_emergency_exit(self):
        self.run_cli(create_user, "alex")
        self.run_cli(create_user, "sam")
        self.assertIn("now admin", self.run_cli(set_role, "sam", "admin"))
        self.run_cli(set_role, "alex", "user")
        self.assertEqual(self.role("alex"), "user")
        with self.assertRaises(SystemExit) as context:
            self.run_cli(set_role, "sam", "user")
        self.assertIn("last active admin", str(context.exception))
        with self.assertRaises(SystemExit):
            self.run_cli(set_role, "nobody", "admin")

    def test_invalid_new_username(self):
        with self.assertRaises(SystemExit) as context:
            self.run_cli(create_user, "A B")
        self.assertIn("3 to 32 characters", str(context.exception))


if __name__ == "__main__":
    unittest.main()
