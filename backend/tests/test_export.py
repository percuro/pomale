import unittest
from datetime import date

from tests.support import ApiTestEnvironment


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user()
        self.client = self.env.client()

    def tearDown(self):
        self.env.close()

    def test_csv_with_bom_semicolon_and_states(self):
        habit = self.client.post(
            "/v1/habits", json={"name": "=Lesen", "cue": "abends", "weekdays": 1, "start_on": "2026-11-16"}
        ).json()
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-16", json={"done": True})
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-18", json={"done": True})
        response = self.client.get("/v1/export.csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="pomale-2026-11-24.csv"', response.headers["content-disposition"])
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("\ufeff"))
        lines = text.lstrip("\ufeff").strip().split("\r\n")
        self.assertEqual(lines[0], "date;habit;cue;planned;state;value;target;note")
        self.assertEqual(
            lines[1:],
            [
                "2026-11-16;'=Lesen;abends;yes;done;;;",
                "2026-11-18;'=Lesen;abends;no;extra_done;;;",
                "2026-11-23;'=Lesen;abends;yes;open;;;",
            ],
        )

    def test_columns_and_values_are_the_same_in_every_language(self):
        self.client.post("/v1/habits", json={"name": "Lesen", "weekdays": 1, "start_on": "2026-11-16"})
        english = self.client.get("/v1/export.csv").text
        self.client.patch("/v1/account", json={"locale": "de"})
        self.assertEqual(self.client.get("/v1/export.csv").text, english)
        self.assertEqual(self.client.get("/v1/export.csv", headers={"Accept-Language": "de"}).text, english)
        self.assertEqual(
            english.lstrip("\ufeff").split("\r\n")[:2],
            ["date;habit;cue;planned;state;value;target;note", "2026-11-16;Lesen;;yes;open;;;"],
        )

    def test_goal_types_pauses_and_notes(self):
        water = self.client.post(
            "/v1/habits", json={"name": "Water", "goal_type": "quantity", "target": 8, "start_on": "2026-11-23"}
        ).json()
        run = self.client.post(
            "/v1/habits", json={"name": "Run", "goal_type": "weekly_count", "target": 2, "start_on": "2026-11-23"}
        ).json()
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-23", json={"value": 5})
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-23/note", json={"note": "-hot day"})
        self.client.put(f"/v1/habits/{run['id']}/days/2026-11-23", json={"done": True})
        self.client.post("/v1/pauses", json={"habit_id": water["id"], "start_on": "2026-11-24", "end_on": "2026-11-24"})
        lines = self.client.get("/v1/export.csv").text.lstrip("\ufeff").strip().split("\r\n")
        self.assertEqual(
            lines[1:],
            [
                "2026-11-23;Water;;yes;partial;5;8;'-hot day",
                "2026-11-23;Run;;yes;done;;2;",
                "2026-11-24;Water;;no;paused;0;8;",
                "2026-11-24;Run;;yes;open;;2;",
            ],
        )

    def test_requires_login(self):
        self.assertEqual(self.env.client(username=None).get("/v1/export.csv").status_code, 401)


if __name__ == "__main__":
    unittest.main()
