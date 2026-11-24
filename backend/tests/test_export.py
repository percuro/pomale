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
        self.assertIn("attachment", response.headers["content-disposition"])
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith("﻿"))
        lines = text.lstrip("﻿").strip().split("\r\n")
        self.assertEqual(lines[0], "datum;gewohnheit;hinweis;geplant;zustand")
        self.assertEqual(
            lines[1:],
            [
                "2026-11-16;'=Lesen;abends;ja;erledigt",
                "2026-11-18;'=Lesen;abends;nein;zusätzlich erledigt",
                "2026-11-23;'=Lesen;abends;ja;offen",
            ],
        )

    def test_requires_login(self):
        self.assertEqual(self.env.client(username=None).get("/v1/export.csv").status_code, 401)


if __name__ == "__main__":
    unittest.main()
