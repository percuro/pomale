"""GET /v1/today: what is still open, for shortcuts and home automation."""

import unittest
from datetime import date

from tests.support import ApiTestEnvironment

TUESDAY = date(2026, 11, 24)


class TodayApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=TUESDAY)
        self.env.create_user("alex", locale="de")
        self.client = self.env.client("alex")

    def tearDown(self):
        self.env.close()

    def habit(self, name: str, **fields) -> dict:
        response = self.client.post("/v1/habits", json={"name": name, "start_on": "2026-11-23", **fields})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_open_partial_weekly_and_done(self):
        self.habit("Lesen", cue="nach dem Frühstück")
        water = self.habit("Wasser", goal_type="quantity", target=8, unit="Gläser")
        run = self.habit("Laufen", goal_type="weekly_count", target=3)
        stretch = self.habit("Dehnen")
        self.habit("Nur montags", weekdays=1)
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-24", json={"value": 3})
        self.client.put(f"/v1/habits/{run['id']}/days/2026-11-23", json={"done": True})
        self.client.put(f"/v1/habits/{stretch['id']}/days/2026-11-24", json={"done": True})

        today = self.client.get("/v1/today").json()
        self.assertEqual((today["date"], today["due"], today["done"]), ("2026-11-24", 4, 1))
        self.assertEqual(
            [(h["name"], h["state"], h["progress"]) for h in today["open"]],
            [
                ("Lesen", "open", None),
                ("Wasser", "partial", "3 von 8 Gläser"),
                ("Laufen", "open", "1 von 3 diese Woche"),
            ],
        )
        self.assertEqual(today["message"], "Noch offen: Lesen, Wasser (3 von 8 Gläser), Laufen (1 von 3 diese Woche)")
        self.assertEqual(today["open"][0]["cue"], "nach dem Frühstück")

    def test_all_done_and_nothing_due(self):
        self.assertEqual(self.client.get("/v1/today").json()["message"], "Heute ist nichts geplant.")
        habit = self.habit("Lesen")
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True})
        today = self.client.get("/v1/today").json()
        self.assertEqual((today["open"], today["message"]), ([], "Heute ist alles erledigt."))

    def test_paused_habits_are_not_due(self):
        habit = self.habit("Lesen")
        self.client.post("/v1/pauses", json={"habit_id": habit["id"], "start_on": "2026-11-24", "end_on": "2026-11-30"})
        self.assertEqual(self.client.get("/v1/today").json()["due"], 0)

    def test_language_follows_the_account_else_the_device(self):
        self.habit("Read")
        self.client.patch("/v1/account", json={"locale": None})
        english = self.client.get("/v1/today", headers={"Accept-Language": "en-US"}).json()
        self.assertEqual(english["message"], "Still open: Read")

    def test_with_a_key_limited_to_one_habit(self):
        read = self.habit("Lesen")
        self.habit("Laufen")
        key = self.client.post("/v1/account/tokens", json={"scopes": ["read"], "habit_ids": [read["id"]]}).json()
        script = self.env.client(username=None)
        script.headers.clear()
        today = script.get("/v1/today", headers={"Authorization": f"Bearer {key['token']}"}).json()
        self.assertEqual((today["due"], [h["name"] for h in today["open"]]), (1, ["Lesen"]))


if __name__ == "__main__":
    unittest.main()
