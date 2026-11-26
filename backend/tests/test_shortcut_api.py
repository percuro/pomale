import os
import unittest
from datetime import date
from unittest import mock

from app.services.token_service import token_rate_limiter
from tests.support import ApiTestEnvironment


class ShortcutApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user()
        self.client = self.env.client()
        token_rate_limiter.reset()
        self.habit = self.client.post("/v1/habits", json={"name": "Lesen"}).json()
        self.other = self.client.post("/v1/habits", json={"name": "Laufen"}).json()
        created = self.client.post(f"/v1/habits/{self.habit['id']}/shortcut-tokens", json={"label": "iPhone"})
        self.assertEqual(created.status_code, 201)
        self.token_info = created.json()
        self.token = self.token_info["token"]
        # Shortcut: separate client without cookie, CSRF header or Origin
        self.shortcut = self.env.client(username=None)
        self.shortcut.headers.clear()

    def tearDown(self):
        self.env.close()

    def tap(self, habit_id=None, token=None, json=None):
        headers = {"Authorization": f"Bearer {token or self.token}"}
        return self.shortcut.put(
            f"/v1/habits/{habit_id or self.habit['id']}/days/today",
            headers=headers,
            json=json if json is not None else {"done": True},
        )

    def test_token_is_shown_once_and_stored_hashed(self):
        self.assertTrue(self.token.startswith("pm_"))
        listed = self.client.get(f"/v1/habits/{self.habit['id']}/shortcut-tokens").json()
        self.assertEqual(len(listed), 1)
        self.assertNotIn("token", listed[0])
        from app.models.api_token import ApiToken

        db = self.env.SessionLocal()
        stored = db.query(ApiToken).one()
        self.assertEqual((stored.scopes, stored.habit_ids), ("checkin", [self.habit["id"]]))
        self.assertNotEqual(stored.token_hash, self.token)
        self.assertNotIn(self.token, stored.token_hash)
        db.close()

    def test_double_tap_creates_one_entry(self):
        first = self.tap()
        second = self.tap()
        self.assertEqual(first.status_code, 200)
        self.assertEqual((first.json()["result"], first.json()["status"]), ("done", "Done today"))
        self.assertEqual(first.json()["date"], "2026-11-24")
        self.assertEqual(second.json()["result"], "already_done")
        self.assertEqual(second.json()["message"], "Lesen: Already done")
        day = self.client.get("/v1/days").json()["habits"][0]["days"][1]
        self.assertEqual((day["state"], day["version"]), ("done", 1))

    def test_message_in_the_owners_language_else_the_phones(self):
        german_phone = self.shortcut.put(
            f"/v1/habits/{self.habit['id']}/days/today",
            headers={"Authorization": f"Bearer {self.token}", "Accept-Language": "de-DE,de;q=0.9"},
            json={"done": True},
        )
        self.assertEqual(german_phone.json()["message"], "Lesen: Heute erledigt")
        self.client.patch("/v1/account", json={"locale": "en"})
        english_owner = self.shortcut.put(
            f"/v1/habits/{self.habit['id']}/days/today",
            headers={"Authorization": f"Bearer {self.token}", "Accept-Language": "de"},
            json={"done": True},
        )
        self.assertEqual(english_owner.json()["message"], "Lesen: Already done")

    def test_quantity_goal_adds_one_or_the_amount(self):
        water = self.client.post(
            "/v1/habits", json={"name": "Wasser", "goal_type": "quantity", "target": 8, "unit": "Gläser"}
        ).json()
        token = self.client.post(f"/v1/habits/{water['id']}/shortcut-tokens", json={"label": "iPhone"}).json()["token"]
        first = self.tap(water["id"], token)
        self.assertEqual(first.status_code, 200, first.text)
        body = first.json()
        self.assertEqual((body["result"], body["value"], body["target"], body["done"]), ("counted", 1, 8, False))
        self.assertEqual(body["message"], "Wasser: 1 of 8 Gläser")
        self.assertEqual(self.tap(water["id"], token, json={"amount": 7}).json()["value"], 8)
        reached = self.tap(water["id"], token).json()
        self.assertEqual((reached["value"], reached["done"]), (9, True))
        self.assertEqual(self.tap(water["id"], token, json={"amount": 0}).status_code, 422)
        self.assertEqual(self.tap(water["id"], token, json={"amount": 1001}).status_code, 422)
        day = self.client.get("/v1/days").json()["habits"][2]["days"][1]
        self.assertEqual((day["value"], day["state"], day["version"]), (9, "done", 3))

    def test_quantity_counts_on_top_of_a_value_set_in_the_app(self):
        water = self.client.post("/v1/habits", json={"name": "Water", "goal_type": "quantity", "target": 8}).json()
        token = self.client.post(f"/v1/habits/{water['id']}/shortcut-tokens", json={"label": "iPhone"}).json()["token"]
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-24", json={"value": 4})
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-24/note", json={"note": "kept"})
        self.assertEqual(self.tap(water["id"], token).json()["value"], 5)
        day = self.client.get("/v1/days").json()["habits"][2]["days"][1]
        self.assertEqual((day["value"], day["note"]), (5, "kept"))

    def test_concurrent_adds_are_not_lost(self):
        from app.repositories.habit_repository import HabitRepository

        water = self.client.post("/v1/habits", json={"name": "Water", "goal_type": "quantity", "target": 8}).json()
        first, second = self.env.SessionLocal(), self.env.SessionLocal()
        try:
            # Both sessions see "no entry yet"; the second insert loses and must add instead
            self.assertIsNone(HabitRepository(first).get_checkin(water["id"], date(2026, 11, 24)))
            self.assertIsNone(HabitRepository(second).get_checkin(water["id"], date(2026, 11, 24)))
            HabitRepository(first).add_to_value(water["id"], date(2026, 11, 24), 1, 8, 9999)
            HabitRepository(second).add_to_value(water["id"], date(2026, 11, 24), 1, 8, 9999)
        finally:
            first.close()
            second.close()
        day = self.client.get("/v1/days").json()["habits"][2]["days"][1]
        self.assertEqual((day["value"], day["version"]), (2, 2))

    def test_server_decides_today_in_tracker_timezone(self):
        self.env.today = date(2026, 11, 25)
        self.assertEqual(self.tap().json()["date"], "2026-11-25")

    def test_revoked_token_gets_no_success(self):
        revoke = self.client.delete(f"/v1/habits/{self.habit['id']}/shortcut-tokens/{self.token_info['id']}")
        self.assertEqual(revoke.status_code, 204)
        response = self.tap()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("erledigt", response.text.lower())

    def test_wrong_habit_wrong_token_and_no_token(self):
        self.assertEqual(self.tap(habit_id=self.other["id"]).status_code, 403)
        self.assertEqual(self.tap(token="ht_falsch").status_code, 401)
        no_auth = self.shortcut.put(f"/v1/habits/{self.habit['id']}/days/today", json={"done": True})
        # without a bearer key the CSRF check already rejects (403); what matters: no success
        self.assertIn(no_auth.status_code, (401, 403))

    def test_only_done_true(self):
        self.assertEqual(self.tap(json={"done": False}).status_code, 422)

    def test_with_a_session_the_endpoint_works_like_any_other(self):
        # The web app does not use it, but a logged-in browser may: CSRF rules apply as usual
        response = self.client.put(f"/v1/habits/{self.habit['id']}/days/today", json={"done": True})
        self.assertEqual((response.status_code, response.json()["date"]), (200, "2026-11-24"))
        stranger = self.env.client(username=None)
        stranger.cookies.update(self.client.cookies)
        stranger.headers.pop("X-Habit-CSRF")
        forged = stranger.put(f"/v1/habits/{self.habit['id']}/days/today", json={"done": True})
        self.assertEqual(forged.status_code, 403)

    def test_rate_limit_for_wrong_tokens(self):
        for _ in range(20):
            self.tap(token="ht_falsch")
        self.assertEqual(self.tap().status_code, 429)

    def test_archived_habit_gets_no_success(self):
        self.client.post(f"/v1/habits/{self.habit['id']}/archive")
        self.assertEqual(self.tap().status_code, 409)

    def test_other_user_cannot_manage_tokens(self):
        self.env.create_user("andere", "anderes-passwort-123")
        other = self.env.client("andere", "anderes-passwort-123")
        self.assertEqual(other.get(f"/v1/habits/{self.habit['id']}/shortcut-tokens").status_code, 404)
        self.assertEqual(
            other.delete(f"/v1/habits/{self.habit['id']}/shortcut-tokens/{self.token_info['id']}").status_code, 404
        )

    def test_csrf_exemption_only_for_bearer_without_cookie(self):
        env = {"CSRF_PROTECTION": "true", "PUBLIC_URL": "https://habits.example.org"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(self.tap().status_code, 200)
            # a web app request without the CSRF header stays blocked
            blocked = self.client.put(
                f"/v1/habits/{self.habit['id']}/days/2026-11-24",
                json={"done": False},
                headers={"X-Habit-CSRF": "", "Origin": "https://evil.example"},
            )
            self.assertEqual(blocked.status_code, 403)


class VersionedPutTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user()
        self.client = self.env.client()
        self.habit = self.client.post("/v1/habits", json={"name": "Lesen", "start_on": "2026-11-16"}).json()

    def tearDown(self):
        self.env.close()

    def put(self, day, done, base_version, op_id="op-1"):
        return self.client.put(
            f"/v1/habits/{self.habit['id']}/days/{day}",
            json={"done": done, "base_version": base_version, "op_id": op_id},
        )

    def test_same_target_state_counts_as_success(self):
        self.put("2026-11-24", True, 0)
        laptop_change_then_same = self.put("2026-11-24", True, 0, op_id="op-2")
        self.assertEqual(laptop_change_then_same.status_code, 200)
        self.assertEqual(laptop_change_then_same.json()["version"], 1)

    def test_conflict_when_server_changed_meanwhile(self):
        self.put("2026-11-23", True, 0, op_id="laptop")  # laptop: done (version 1)
        self.put("2026-11-23", False, 1, op_id="laptop-2")  # laptop: back to open (version 2)
        offline_phone = self.put("2026-11-23", True, 0, op_id="phone")  # iPhone knew version 0
        self.assertEqual(offline_phone.status_code, 409)
        body = offline_phone.json()
        self.assertEqual(body["code"], "checkin.conflict")
        self.assertEqual(body["server"]["done"], False)
        self.assertEqual(body["server"]["version"], 2)
        # after choosing "keep this device's state" with the current version
        resolved = self.put("2026-11-23", True, 2, op_id="phone-2")
        self.assertEqual((resolved.status_code, resolved.json()["version"]), (200, 3))

    def test_offline_entry_synced_after_midnight_stays_on_original_day(self):
        self.env.today = date(2026, 11, 25)
        response = self.put("2026-11-24", True, 0, op_id="offline-2359")
        self.assertEqual(response.json()["date"], "2026-11-24")
        week = self.client.get("/v1/days").json()["habits"][0]["days"]
        self.assertEqual(week[1]["state"], "done")
        self.assertEqual(week[2]["state"], "open")

    def test_op_id_is_recorded(self):
        self.put("2026-11-24", True, 0, op_id="abc-123")
        from app.models.habit import Checkin

        db = self.env.SessionLocal()
        self.assertEqual(db.query(Checkin).one().last_op_id, "abc-123")
        db.close()


if __name__ == "__main__":
    unittest.main()
