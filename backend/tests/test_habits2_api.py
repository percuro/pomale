"""Goal types, groups, ordering, pauses and notes through the API."""

import unittest
from datetime import date

from tests.support import ApiTestEnvironment

WEEK = ("2026-11-23", "2026-11-29")  # Monday to Sunday; today is Wednesday 25 Nov


class Habits2ApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 25))
        self.env.create_user()
        self.client = self.env.client()

    def tearDown(self):
        self.env.close()

    def create(self, **body):
        body.setdefault("name", "Habit")
        body.setdefault("start_on", "2026-11-01")
        response = self.client.post("/v1/habits", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def put_day(self, habit_id, day, **body):
        return self.client.put(f"/v1/habits/{habit_id}/days/{day}", json=body)

    def week(self):
        response = self.client.get("/v1/days", params={"from": WEEK[0], "to": WEEK[1]})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def habit_days(self, habit_id):
        return next(h for h in self.week()["habits"] if h["id"] == habit_id)

    # Goal types

    def test_goal_validation(self):
        for body in (
            {"goal_type": "weekly_count"},
            {"goal_type": "weekly_count", "target": 8},
            {"goal_type": "quantity", "target": 0},
            {"goal_type": "quantity", "target": 10000},
            {"goal_type": "days", "target": 3},
            {"goal_type": "monthly", "target": 3},
            {"color": "neon"},
        ):
            with self.subTest(body=body):
                response = self.client.post("/v1/habits", json={"name": "x", **body})
                self.assertEqual(response.status_code, 422, response.text)

    def test_weekly_goal_counts_any_day(self):
        habit = self.create(goal_type="weekly_count", target=3, weekdays=1)
        self.assertEqual((habit["weekdays"], habit["goal_type"], habit["target"]), (127, "weekly_count", 3))
        self.put_day(habit["id"], "2026-11-23", done=True)
        self.put_day(habit["id"], "2026-11-24", done=True)
        days = self.habit_days(habit["id"])
        self.assertEqual(days["week"], {"done": 2, "target": 3})
        self.assertEqual(days["quota"], {"done": 2, "due": 2})
        self.assertEqual([d["state"] for d in days["days"]][:3], ["done", "done", "open"])
        third = self.put_day(habit["id"], "2026-11-25", done=True).json()
        self.assertEqual(third["state"], "done")
        # Further check-ins are extra and do not count; the response knows the week
        self.assertEqual(self.habit_days(habit["id"])["week"], {"done": 3, "target": 3})

    def test_quantity_goal_with_values(self):
        habit = self.create(name="Water", goal_type="quantity", target=8, unit=" glasses ")
        self.assertEqual(habit["unit"], "glasses")
        first = self.put_day(habit["id"], "2026-11-25", value=3).json()
        self.assertEqual((first["state"], first["value"], first["done"], first["version"]), ("partial", 3, False, 1))
        reached = self.put_day(habit["id"], "2026-11-25", value=8).json()
        self.assertEqual((reached["state"], reached["done"], reached["version"]), ("done", True, 2))
        same = self.put_day(habit["id"], "2026-11-25", value=8).json()
        self.assertEqual(same["version"], 2)
        # done on a quantity goal sets the value to the target or 0
        self.assertEqual(self.put_day(habit["id"], "2026-11-24", done=True).json()["value"], 8)
        cleared = self.put_day(habit["id"], "2026-11-24", done=False).json()
        self.assertEqual((cleared["value"], cleared["state"]), (0, "open"))
        days = self.habit_days(habit["id"])
        self.assertEqual(days["unit"], "glasses")
        today = days["days"][2]
        self.assertEqual((today["goal_type"], today["target"], today["value"]), ("quantity", 8, 8))

    def test_value_and_done_rules(self):
        days_habit = self.create()
        quantity = self.create(goal_type="quantity", target=4)
        self.assertEqual(
            self.put_day(days_habit["id"], "2026-11-25", value=1).json()["code"], "checkin.value_not_allowed"
        )
        for body in ({}, {"done": True, "value": 2}, {"value": -1}, {"value": 10000}):
            with self.subTest(body=body):
                self.assertEqual(self.put_day(quantity["id"], "2026-11-25", **body).status_code, 422)

    def test_value_conflict_with_base_version(self):
        habit = self.create(goal_type="quantity", target=8)
        self.put_day(habit["id"], "2026-11-25", value=2, base_version=0)
        conflict = self.put_day(habit["id"], "2026-11-25", value=5, base_version=0)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["server"]["value"], 2)
        # Arriving at the same value is no conflict
        self.assertEqual(self.put_day(habit["id"], "2026-11-25", value=2, base_version=0).status_code, 200)

    def test_type_change_from_a_date_keeps_old_days(self):
        habit = self.create()
        self.put_day(habit["id"], "2026-11-23", done=True)
        response = self.client.put(
            f"/v1/habits/{habit['id']}/schedule",
            json={"goal_type": "quantity", "target": 5, "valid_from": "2026-11-24"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        days = self.habit_days(habit["id"])["days"]
        self.assertEqual([d["goal_type"] for d in days[:3]], ["days", "quantity", "quantity"])
        self.assertEqual(days[0]["state"], "done")
        # Only the weekdays: type and target stay
        habit = self.client.put(f"/v1/habits/{habit['id']}/schedule", json={"weekdays": 3}).json()
        self.assertEqual((habit["goal_type"], habit["target"], habit["weekdays"]), ("quantity", 5, 3))

    def test_archive_and_unarchive_keep_the_goal(self):
        habit = self.create(goal_type="weekly_count", target=2)
        self.client.post(f"/v1/habits/{habit['id']}/archive")
        self.env.today = date(2026, 11, 27)
        habit = self.client.post(f"/v1/habits/{habit['id']}/unarchive").json()
        self.assertEqual((habit["goal_type"], habit["target"], habit["weekdays"]), ("weekly_count", 2, 127))
        self.assertEqual(habit["schedules"][-1]["valid_from"], "2026-11-27")

    # Groups and order

    def test_groups(self):
        morning = self.client.post("/v1/groups", json={"name": " Morning "}).json()
        evening = self.client.post("/v1/groups", json={"name": "Evening"}).json()
        self.assertEqual((morning["name"], morning["sort_order"], evening["sort_order"]), ("Morning", 1, 2))
        self.assertEqual(self.client.post("/v1/groups", json={"name": "morning"}).status_code, 409)
        self.assertEqual(self.client.post("/v1/groups", json={"name": "  "}).status_code, 422)
        renamed = self.client.patch(f"/v1/groups/{evening['id']}", json={"name": "Night"}).json()
        self.assertEqual(renamed["name"], "Night")
        order = self.client.put("/v1/groups/order", json={"ids": [evening["id"]]}).json()
        self.assertEqual([g["name"] for g in order], ["Night", "Morning"])

        habit = self.create(group_id=morning["id"], color="teal")
        self.assertEqual((habit["group_id"], habit["color"]), (morning["id"], "teal"))
        week = self.week()
        self.assertEqual([g["name"] for g in week["groups"]], ["Night", "Morning"])
        self.assertEqual((week["habits"][0]["group_id"], week["habits"][0]["color"]), (morning["id"], "teal"))

        self.assertEqual(self.client.delete(f"/v1/groups/{morning['id']}").status_code, 204)
        habits = self.client.get("/v1/habits").json()
        self.assertEqual([(h["name"], h["group_id"]) for h in habits], [("Habit", None)])

    def test_reorder_habits_and_move_between_groups(self):
        group = self.client.post("/v1/groups", json={"name": "Morning"}).json()
        a, b, c = (self.create(name=name) for name in "abc")
        response = self.client.put(
            "/v1/habits/order", json={"habits": [{"id": c["id"], "group_id": group["id"]}, {"id": a["id"]}]}
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([(h["name"], h["sort_order"], h["group_id"]) for h in response.json()],
                         [("c", 1, group["id"]), ("a", 2, None), ("b", 3, None)])  # fmt: skip
        duplicate = self.client.put("/v1/habits/order", json={"habits": [{"id": a["id"]}, {"id": a["id"]}]})
        self.assertEqual(duplicate.status_code, 422)

    # Pauses

    def test_pauses_crud_and_validation(self):
        habit = self.create()
        pause = self.client.post(
            "/v1/pauses", json={"start_on": "2026-11-24", "end_on": "2026-11-26", "reason": " Holiday "}
        ).json()
        self.assertEqual((pause["habit_id"], pause["reason"]), (None, "Holiday"))
        bad = [
            {"start_on": "2026-11-24", "end_on": "2026-11-23"},
            {"start_on": "2026-01-01", "end_on": "2027-01-02"},
            {"start_on": "2026-11-24", "end_on": "2026-11-25", "habit_id": 99999},
        ]
        for body in bad:
            with self.subTest(body=body):
                self.assertIn(self.client.post("/v1/pauses", json=body).status_code, (404, 422))
        updated = self.client.patch(f"/v1/pauses/{pause['id']}", json={"habit_id": habit["id"], "reason": ""}).json()
        self.assertEqual((updated["habit_id"], updated["reason"]), (habit["id"], None))
        refused = self.client.patch(f"/v1/pauses/{pause['id']}", json={"end_on": "2026-11-01"})
        self.assertEqual(refused.json()["code"], "pause.end_before_start")
        self.assertEqual(self.client.get("/v1/pauses").json()[0]["end_on"], "2026-11-26")
        self.assertEqual(self.client.delete(f"/v1/pauses/{pause['id']}").status_code, 204)
        self.assertEqual(self.client.get("/v1/pauses").json(), [])

    def test_pause_takes_days_out_of_the_quota(self):
        habit = self.create()
        other = self.create(name="Other")
        self.client.post("/v1/pauses", json={"habit_id": habit["id"], "start_on": "2026-11-23", "end_on": "2026-11-24"})
        days = self.habit_days(habit["id"])
        self.assertEqual([d["state"] for d in days["days"][:3]], ["paused", "paused", "open"])
        self.assertTrue(days["days"][0]["paused"])
        self.assertEqual(days["quota"], {"done": 0, "due": 0})
        # The pause belongs to one habit only
        self.assertEqual(self.habit_days(other["id"])["quota"], {"done": 0, "due": 2})
        # Checking off a paused day is allowed and extra
        self.assertEqual(self.put_day(habit["id"], "2026-11-23", done=True).json()["state"], "extra_done")

    # Notes

    def test_note_does_not_change_the_version(self):
        habit = self.create()
        put_note = lambda day, note: self.client.put(f"/v1/habits/{habit['id']}/days/{day}/note", json={"note": note})  # noqa: E731
        self.assertEqual(put_note("2026-11-24", "  sore knee ").json()["note"], "sore knee")
        day = self.habit_days(habit["id"])["days"][1]
        self.assertEqual((day["note"], day["version"], day["state"]), ("sore knee", 0, "open"))
        # The offline queue still sees "no state": base_version 0 is right
        checked = self.put_day(habit["id"], "2026-11-24", done=True, base_version=0).json()
        self.assertEqual(checked["version"], 1)
        put_note("2026-11-24", "better")
        day = self.habit_days(habit["id"])["days"][1]
        self.assertEqual((day["note"], day["version"], day["done"]), ("better", 1, True))
        self.assertEqual(put_note("2026-11-24", "").json()["note"], None)
        self.assertIsNone(self.habit_days(habit["id"])["days"][1]["note"])
        self.assertEqual(put_note("2026-11-26", "later").status_code, 422)
        self.assertEqual(
            self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24/note", json={"note": "x" * 501}).status_code, 422
        )


if __name__ == "__main__":
    unittest.main()
