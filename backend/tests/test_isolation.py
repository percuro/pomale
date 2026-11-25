"""No account can read or change another account's data.

Every route with an ID in its path must appear in ROUTES below. The test reads the
routes from the app's OpenAPI schema and fails when one is missing, so a new route cannot slip
through untested. Foreign IDs must give 404 (not 403), so IDs cannot be probed.
"""

import unittest

from app.main import app
from app.models.habit import Checkin, Habit
from app.models.shortcut_token import ShortcutToken
from app.models.user import UserSession
from app.services.shortcut_service import shortcut_rate_limiter
from tests.support import ApiTestEnvironment

# (method, path) -> (expected status for account A using B's IDs, request body)
ROUTES = {
    ("PATCH", "/v1/habits/{habit_id}"): (404, {"name": "taken over"}),
    ("PUT", "/v1/habits/{habit_id}/schedule"): (404, {"weekdays": 1}),
    ("POST", "/v1/habits/{habit_id}/archive"): (404, None),
    ("POST", "/v1/habits/{habit_id}/unarchive"): (404, None),
    ("PUT", "/v1/habits/{habit_id}/days/{day}"): (404, {"done": False}),
    ("GET", "/v1/habits/{habit_id}/shortcut-tokens"): (404, None),
    ("POST", "/v1/habits/{habit_id}/shortcut-tokens"): (404, {"label": "mine now"}),
    ("DELETE", "/v1/habits/{habit_id}/shortcut-tokens/{token_id}"): (404, None),
    ("DELETE", "/v1/account/sessions/{session_id}"): (404, None),
    # Shortcut: authenticated by key only; A's key on B's habit is refused the same way as on any other id
    ("PUT", "/v1/habits/{habit_id}/days/today"): (403, {"done": True}),
    # Admin routes act on other accounts by design: a normal account gets 403
    ("PATCH", "/v1/admin/users/{user_id}"): (403, {"is_active": False}),
    ("DELETE", "/v1/admin/users/{user_id}"): (403, None),
    ("POST", "/v1/admin/users/{user_id}/password-reset"): (403, None),
    ("DELETE", "/v1/admin/users/{user_id}/oidc"): (403, None),
    ("DELETE", "/v1/admin/invitations/{invitation_id}"): (403, None),
}


def routes_with_ids() -> set[tuple[str, str]]:
    # The OpenAPI schema lists every API route with its full path, however routers are nested
    paths = app.openapi()["paths"]
    return {(method.upper(), path) for path, operations in paths.items() if "{" in path for method in operations}


class IsolationTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.env.create_user("anna")
        self.bert_user = self.env.create_user("bert")
        self.anna = self.env.client("anna")
        self.bert = self.env.client("bert")
        shortcut_rate_limiter.reset()

        self.bert_habit = self.bert.post("/v1/habits", json={"name": "Bert's secret", "start_on": "2026-11-16"}).json()
        self.bert.put(f"/v1/habits/{self.bert_habit['id']}/days/2026-11-23", json={"done": True})
        bert_token = self.bert.post(f"/v1/habits/{self.bert_habit['id']}/shortcut-tokens", json={"label": "B"}).json()
        self.bert_token_id = bert_token["id"]
        self.bert_session_id = self.bert.get("/v1/account/sessions").json()[0]["id"]

        self.anna_habit = self.anna.post("/v1/habits", json={"name": "Anna's own"}).json()
        self.anna_token = self.anna.post(
            f"/v1/habits/{self.anna_habit['id']}/shortcut-tokens", json={"label": "A"}
        ).json()["token"]

    def tearDown(self):
        self.env.close()

    def fill(self, path: str) -> str:
        return path.format(
            habit_id=self.bert_habit["id"],
            day="2026-11-23",
            token_id=self.bert_token_id,
            session_id=self.bert_session_id,
            user_id=self.bert_user.id,
            invitation_id=1,
        )

    def test_every_route_with_an_id_is_covered(self):
        missing = routes_with_ids() - set(ROUTES)
        self.assertEqual(missing, set(), "add these routes to ROUTES in tests/test_isolation.py")
        self.assertEqual(set(ROUTES) - routes_with_ids(), set(), "ROUTES lists routes that no longer exist")

    def test_foreign_ids_are_not_found(self):
        for (method, path), (expected, body) in ROUTES.items():
            with self.subTest(method=method, path=path):
                headers = {}
                client = self.anna
                if path.endswith("/days/today"):
                    client = self.env.client(username=None)
                    client.headers.clear()
                    headers = {"Authorization": f"Bearer {self.anna_token}"}
                response = client.request(method, self.fill(path), json=body, headers=headers)
                self.assertEqual(response.status_code, expected, response.text)
                self.assertNotIn("Bert's secret", response.text)
        self.assertBertUntouched()

    def test_foreign_and_missing_ids_look_the_same(self):
        foreign = self.anna.get(f"/v1/habits/{self.bert_habit['id']}/shortcut-tokens")
        missing = self.anna.get("/v1/habits/99999/shortcut-tokens")
        self.assertEqual((foreign.status_code, foreign.json()), (missing.status_code, missing.json()))

    def test_lists_days_and_export_contain_only_own_data(self):
        self.anna.put(f"/v1/habits/{self.anna_habit['id']}/days/2026-11-24", json={"done": True})
        habits = self.anna.get("/v1/habits", params={"include_archived": True, "user_id": self.bert_user.id})
        self.assertEqual([h["name"] for h in habits.json()], ["Anna's own"])
        days = self.anna.get(
            "/v1/days", params={"from": "2026-11-01", "to": "2026-11-30", "user_id": self.bert_user.id}
        )
        self.assertEqual([h["name"] for h in days.json()["habits"]], ["Anna's own"])
        export = self.anna.get("/v1/export.csv", params={"from": "2020-01-01", "user_id": self.bert_user.id})
        self.assertIn("Anna's own", export.text)
        self.assertNotIn("Bert", export.text)

    def test_session_list_shows_only_own_sessions(self):
        ids = {s["id"] for s in self.anna.get("/v1/account/sessions").json()}
        self.assertNotIn(self.bert_session_id, ids)

    def assertBertUntouched(self):
        db = self.env.SessionLocal()
        try:
            habit = db.get(Habit, self.bert_habit["id"])
            self.assertEqual((habit.name, habit.archived_on), ("Bert's secret", None))
            self.assertEqual([(s.weekdays) for s in habit.schedules], [127])
            self.assertEqual(
                [(c.local_date.isoformat(), c.done) for c in db.query(Checkin).filter_by(habit_id=habit.id)],
                [("2026-11-23", True)],
            )
            tokens = db.query(ShortcutToken).filter_by(habit_id=habit.id).all()
            self.assertEqual([(t.label, t.revoked_at) for t in tokens], [("B", None)])
            self.assertIsNotNone(db.get(UserSession, self.bert_session_id))
        finally:
            db.close()
        self.assertEqual(self.bert.get("/v1/auth/me").status_code, 200)


if __name__ == "__main__":
    unittest.main()
