import unittest
from datetime import date

from tests.support import ApiTestEnvironment

MON_FRI = 0b0011111


class HabitsApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))  # Tuesday
        self.env.create_user()
        self.env.create_user("andere", "anderes-passwort-123")
        self.client = self.env.client()

    def tearDown(self):
        self.env.close()

    def create(self, **body):
        body.setdefault("name", "10 Minuten lesen")
        response = self.client.post("/v1/habits", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def put_day(self, habit_id, day, done, client=None):
        return (client or self.client).put(f"/v1/habits/{habit_id}/days/{day}", json={"done": done})

    def test_create_and_list(self):
        habit = self.create(cue="  nach dem Frühstück ", weekdays=MON_FRI)
        self.assertEqual(habit["cue"], "nach dem Frühstück")
        self.assertEqual(habit["weekdays"], MON_FRI)
        self.assertEqual(habit["schedules"], [{"valid_from": "2026-11-24", "weekdays": MON_FRI}])
        self.assertEqual([h["id"] for h in self.client.get("/v1/habits").json()], [habit["id"]])

    def test_empty_name_rejected(self):
        self.assertEqual(self.client.post("/v1/habits", json={"name": "   "}).status_code, 422)
        self.assertEqual(self.client.post("/v1/habits", json={"name": "x", "weekdays": 0}).status_code, 422)

    def test_put_is_idempotent_and_sets_state(self):
        habit = self.create()
        first = self.put_day(habit["id"], "2026-11-24", True).json()
        second = self.put_day(habit["id"], "2026-11-24", True).json()
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "done")
        self.assertEqual(first["version"], 1)
        undo = self.put_day(habit["id"], "2026-11-24", False).json()
        self.assertEqual((undo["done"], undo["state"], undo["version"]), (False, "open", 2))
        days = self.client.get("/v1/days").json()
        self.assertEqual(len(days["habits"]), 1)
        today = [d for d in days["habits"][0]["days"] if d["date"] == "2026-11-24"][0]
        self.assertEqual(today["state"], "open")

    def test_undo_without_entry_creates_nothing(self):
        habit = self.create()
        response = self.put_day(habit["id"], "2026-11-24", False).json()
        self.assertEqual((response["done"], response["version"]), (False, 0))

    def test_future_day_rejected(self):
        habit = self.create()
        self.assertEqual(self.put_day(habit["id"], "2026-11-25", True).status_code, 422)

    def test_other_users_habit_is_not_found(self):
        habit = self.create()
        other = self.env.client("andere", "anderes-passwort-123")
        self.assertEqual(self.put_day(habit["id"], "2026-11-24", True, client=other).status_code, 404)
        self.assertEqual(other.get("/v1/days").json()["habits"], [])
        self.assertEqual(other.patch(f"/v1/habits/{habit['id']}", json={"name": "x"}).status_code, 404)

    def test_week_view_backfill_and_quota(self):
        habit = self.create(weekdays=MON_FRI, start_on="2026-11-23")
        self.put_day(habit["id"], "2026-11-23", True)  # backfill yesterday
        self.put_day(habit["id"], "2026-11-22", True)  # Sunday before the start: extra
        week = self.client.get("/v1/days", params={"from": "2026-11-23", "to": "2026-11-29"}).json()
        row = week["habits"][0]
        self.assertEqual(week["today"], "2026-11-24")
        self.assertEqual(week["timezone"], "UTC")
        self.assertEqual(
            [d["state"] for d in row["days"]], ["done", "open", "future", "future", "future", "future", "future"]
        )
        self.assertEqual(row["quota"], {"done": 1, "due": 1})
        prev = self.client.get("/v1/days", params={"from": "2026-11-16", "to": "2026-11-22"}).json()
        self.assertEqual(prev["habits"][0]["days"][-1]["state"], "extra_done")
        self.assertEqual(prev["habits"][0]["quota"], {"done": 0, "due": 0})

    def test_range_limits(self):
        self.assertEqual(
            self.client.get("/v1/days", params={"from": "2026-11-24", "to": "2026-11-20"}).status_code, 422
        )
        self.assertEqual(
            self.client.get("/v1/days", params={"from": "2026-01-01", "to": "2026-12-31"}).status_code, 422
        )

    def test_schedule_change_keeps_previous_week(self):
        habit = self.create(weekdays=127, start_on="2026-11-09")
        for day in ("2026-11-16", "2026-11-17", "2026-11-18"):
            self.put_day(habit["id"], day, True)
        before = self.client.get("/v1/days", params={"from": "2026-11-16", "to": "2026-11-22"}).json()
        response = self.client.put(f"/v1/habits/{habit['id']}/schedule", json={"weekdays": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["weekdays"], 1)
        after = self.client.get("/v1/days", params={"from": "2026-11-16", "to": "2026-11-22"}).json()
        self.assertEqual(before["habits"][0]["quota"], after["habits"][0]["quota"])
        self.assertEqual(before["habits"][0]["quota"], {"done": 3, "due": 7})
        # Mondays only from today: Tuesday (today) is no longer planned
        today = self.client.get("/v1/days").json()["habits"][0]["days"][1]
        self.assertEqual(today["state"], "not_planned")

    def test_retroactive_schedule_change(self):
        habit = self.create(weekdays=127, start_on="2026-11-16")
        self.client.put(f"/v1/habits/{habit['id']}/schedule", json={"weekdays": 1, "valid_from": "2026-11-18"})
        days = self.client.get("/v1/days", params={"from": "2026-11-16", "to": "2026-11-22"}).json()
        states = [d["state"] for d in days["habits"][0]["days"]]
        self.assertEqual(
            states, ["open", "open", "not_planned", "not_planned", "not_planned", "not_planned", "not_planned"]
        )

    def test_archive_keeps_history_and_hides_from_today(self):
        habit = self.create(weekdays=127, start_on="2026-11-16")
        self.put_day(habit["id"], "2026-11-17", True)
        archived = self.client.post(f"/v1/habits/{habit['id']}/archive").json()
        self.assertEqual(archived["archived_on"], "2026-11-24")
        self.assertEqual(archived["weekdays"], 127)
        self.assertEqual(self.client.get("/v1/habits").json(), [])
        self.assertEqual(len(self.client.get("/v1/habits", params={"include_archived": True}).json()), 1)
        prev = self.client.get("/v1/days", params={"from": "2026-11-16", "to": "2026-11-22"}).json()
        self.assertEqual(prev["habits"][0]["quota"], {"done": 1, "due": 7})
        later = self.client.get("/v1/days", params={"from": "2026-11-30", "to": "2026-12-06"}).json()
        self.assertEqual(later["habits"], [])
        self.assertEqual(self.client.put(f"/v1/habits/{habit['id']}/schedule", json={"weekdays": 1}).status_code, 409)
        restored = self.client.post(f"/v1/habits/{habit['id']}/unarchive").json()
        self.assertIsNone(restored["archived_on"])
        self.assertEqual(restored["weekdays"], 127)
        week = self.client.get("/v1/days").json()["habits"][0]["days"]
        self.assertEqual(week[2]["state"], "future")
        self.assertTrue(week[2]["planned"])

    def test_rename_and_clear_cue(self):
        habit = self.create(cue="abends")
        updated = self.client.patch(f"/v1/habits/{habit['id']}", json={"name": "Lesen", "cue": None}).json()
        self.assertEqual((updated["name"], updated["cue"]), ("Lesen", None))


if __name__ == "__main__":
    unittest.main()
