"""JSON export and import (format "pomale-export", version 1)."""

import copy
import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from unittest import mock

from app.models.audit_event import AuditEvent
from tests.support import ApiTestEnvironment

FIXTURE = json.loads((Path(__file__).with_name("fixtures") / "export_v1.json").read_text(encoding="utf-8"))


def comparable(data: dict) -> dict:
    data = copy.deepcopy(data)
    data.pop("exported_at")
    data.pop("app_version")
    return data


class DataExportTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user("alex")
        self.client = self.env.client("alex")

    def tearDown(self):
        self.env.close()

    def import_file(self, client, data):
        return client.post("/v1/import", content=json.dumps(data), headers={"Content-Type": "application/json"})

    def test_the_version_1_file_imports_and_exports_unchanged(self):
        response = self.import_file(self.client, FIXTURE)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json(),
            {
                "groups": 2,
                "habits": 3,
                "checkins": 8,
                "pauses": 2,
                "reminders": 3,
                "settings": ["day_end_hour", "locale", "timezone"],
            },
        )
        exported = self.client.get("/v1/export.json")
        self.assertEqual(exported.status_code, 200)
        self.assertIn('filename="pomale-', exported.headers["Content-Disposition"])
        self.assertEqual(comparable(exported.json()), comparable(FIXTURE))
        me = self.client.get("/v1/auth/me").json()
        self.assertEqual((me["timezone"], me["locale"], me["day_end_hour"]), ("America/New_York", "en", 1))

    def test_imported_data_behaves_like_the_original(self):
        self.import_file(self.client, FIXTURE)
        days = self.client.get("/v1/days?from=2026-11-16&to=2026-11-22").json()
        read = next(h for h in days["habits"] if h["name"] == "Read")
        self.assertEqual([d["state"] for d in read["days"]][:5], ["open", "done", "done", "open", "done"])
        self.assertEqual(read["days"][2]["note"], "Chapter 3")
        habits = self.client.get("/v1/habits?include_archived=true").json()
        self.assertEqual([h["reminders"] for h in habits if h["name"] == "Water"], [["10:00", "15:30"]])
        self.assertEqual(len(self.client.get("/v1/pauses").json()), 2)

    def test_export_with_import_into_another_account(self):
        self.import_file(self.client, FIXTURE)
        first = self.client.get("/v1/export.json").json()
        self.env.create_user("sam")
        sam = self.env.client("sam")
        self.assertEqual(self.import_file(sam, first).status_code, 200)
        self.assertEqual(comparable(sam.get("/v1/export.json").json()), comparable(first))

    def test_only_into_an_empty_account(self):
        self.client.post("/v1/groups", json={"name": "Morning"})
        response = self.import_file(self.client, FIXTURE)
        self.assertEqual((response.status_code, response.json()["code"]), (409, "import.not_empty"))

    def test_all_or_nothing(self):
        broken = copy.deepcopy(FIXTURE)
        broken["habits"][1]["checkins"].append(dict(broken["habits"][1]["checkins"][0]))
        response = self.import_file(self.client, broken)
        self.assertEqual((response.status_code, response.json()["code"]), (422, "validation"))
        self.assertEqual(self.client.get("/v1/habits").json(), [])
        self.assertEqual(self.client.get("/v1/groups").json(), [])

    def test_invalid_files_are_refused(self):
        cases = [
            {"format": "something-else"},
            {**FIXTURE, "version": 2},
            {**FIXTURE, "groups": [], "habits": FIXTURE["habits"]},  # group_ref without group
            {**FIXTURE, "pauses": [{"habit_ref": 99, "start_on": "2026-11-01", "end_on": "2026-11-02"}]},
            {**FIXTURE, "habits": [{**FIXTURE["habits"][0], "color": "gold"}]},
            {**FIXTURE, "habits": [{**FIXTURE["habits"][0], "schedules": []}]},
            {
                **FIXTURE,
                "habits": [
                    {
                        **FIXTURE["habits"][1],
                        "schedules": [{"valid_from": "2026-11-01", "weekdays": 1, "goal_type": "quantity"}],
                    }
                ],
            },
            {**FIXTURE, "account": {"day_end_hour": 9}},
            {**FIXTURE, "groups": [{"ref": 1, "name": "A"}, {"ref": 2, "name": "A"}]},
        ]
        for data in cases:
            response = self.import_file(self.client, data)
            self.assertEqual(response.status_code, 422, (data.get("format"), response.text[:200]))
        self.assertEqual(self.client.get("/v1/habits").json(), [])

    def test_unknown_time_zone_is_left_out(self):
        data = {**FIXTURE, "account": {**FIXTURE["account"], "timezone": "Mars/Olympus_Mons"}}
        self.assertEqual(self.import_file(self.client, data).json()["settings"], ["day_end_hour", "locale"])
        self.assertIsNone(self.client.get("/v1/auth/me").json()["timezone_setting"])

    def test_too_large_or_without_length(self):
        with mock.patch("app.middleware.body_limit.MAX_IMPORT_BYTES", 100):
            response = self.import_file(self.client, FIXTURE)
        self.assertEqual((response.status_code, response.json()["code"]), (413, "import.too_large"))

    def test_audit_and_keys(self):
        self.import_file(self.client, FIXTURE)
        db = self.env.SessionLocal()
        try:
            event = db.query(AuditEvent).filter_by(event="account.imported").one()
            self.assertEqual(event.actor_username, "alex")
        finally:
            db.close()
        # A read key for all habits may export, a limited one may not, and no key may import
        key = self.client.post("/v1/account/tokens", json={"scopes": ["read", "checkin"]}).json()["token"]
        limited = self.client.post("/v1/account/tokens", json={"scopes": ["read"], "habit_ids": [1]}).json()["token"]
        script = self.env.client(username=None)
        script.headers.clear()
        self.assertEqual(script.get("/v1/export.json", headers={"Authorization": f"Bearer {key}"}).status_code, 200)
        self.assertEqual(script.get("/v1/export.json", headers={"Authorization": f"Bearer {limited}"}).status_code, 403)
        refused = script.post("/v1/import", json=FIXTURE, headers={"Authorization": f"Bearer {key}"})
        self.assertEqual((refused.status_code, refused.json()["code"]), (403, "token.not_allowed"))


class CliTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))
        self.env.create_user("alex")
        self.env.create_user("sam")

    def tearDown(self):
        self.env.close()

    def test_export_and_import_from_the_command_line(self):
        from app.cli import export_account, import_account

        with (
            mock.patch("app.cli.export_account.SessionLocal", self.env.SessionLocal),
            mock.patch("app.cli.import_account.SessionLocal", self.env.SessionLocal),
        ):
            with mock.patch("sys.argv", ["import", "alex"]), mock.patch("sys.stdin", io.StringIO(json.dumps(FIXTURE))):
                out = io.StringIO()
                with redirect_stdout(out):
                    import_account.main()
            self.assertIn("3 habits", out.getvalue())
            out = io.StringIO()
            with mock.patch("sys.argv", ["export", "alex"]), redirect_stdout(out):
                export_account.main()
            self.assertEqual(comparable(json.loads(out.getvalue())), comparable(FIXTURE))
            with mock.patch("sys.argv", ["export", "nobody"]), self.assertRaises(SystemExit):
                export_account.main()


if __name__ == "__main__":
    unittest.main()
