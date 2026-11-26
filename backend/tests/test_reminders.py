"""Reminder selection, texts and sending (ReminderService) and the scheduler loop."""

import asyncio
import json
import unittest
from datetime import UTC, date, datetime, time
from unittest import mock
from zoneinfo import ZoneInfo

import httpx
from cryptography.hazmat.primitives.asymmetric import ec

from app.models import PushSubscription
from app.models.habit import HabitReminder
from app.models.user import User
from app.services.reminder_service import ReminderService, build_payload, due_on, is_due
from app.services.scheduler import ReminderScheduler, seconds_until_next_run
from app.services.webpush.crypto import public_bytes
from app.services.webpush.encoding import b64url_encode
from app.services.webpush.keys import ensure_vapid_keys
from app.services.webpush.sender import PushSender
from app.services.webpush.vapid import Vapid
from tests.support import ApiTestEnvironment, push_subscription
from tests.test_webpush_crypto import decrypt

VIENNA = ZoneInfo("Europe/Vienna")
SECRET = b"0123456789abcdef"


def at(day: date, hour: int, minute: int, zone: ZoneInfo = VIENNA, second: int = 2) -> datetime:
    return datetime.combine(day, time(hour, minute, second), tzinfo=zone)


class IsDueTest(unittest.TestCase):
    def test_window(self):
        day = date(2026, 11, 24)
        reminder = time(7, 30)
        self.assertFalse(is_due(reminder, None, at(day, 7, 29, second=59), VIENNA))
        self.assertTrue(is_due(reminder, None, at(day, 7, 30, second=0), VIENNA))
        self.assertTrue(is_due(reminder, None, at(day, 7, 44), VIENNA))  # caught up after a restart
        self.assertTrue(is_due(reminder, None, at(day, 7, 45, second=0), VIENNA))
        self.assertFalse(is_due(reminder, None, at(day, 7, 46), VIENNA))  # too late, dropped
        self.assertFalse(is_due(reminder, day, at(day, 7, 30), VIENNA))  # already sent today
        self.assertTrue(is_due(reminder, date(2026, 11, 23), at(day, 7, 30), VIENNA))

    def test_now_in_another_zone(self):
        self.assertTrue(is_due(time(7, 30), None, datetime(2026, 11, 24, 6, 30, 30, tzinfo=UTC), VIENNA))

    def test_spring_forward(self):
        # 29 March 2026: 02:00 → 03:00 in Vienna; 02:30 does not exist and fires at 03:30
        day = date(2026, 3, 29)
        self.assertFalse(is_due(time(2, 30), None, at(day, 3, 0), VIENNA))
        self.assertTrue(is_due(time(2, 30), None, at(day, 3, 30), VIENNA))
        # 03:10 exists and fires on time, not an hour early or late
        self.assertTrue(is_due(time(3, 10), None, at(day, 3, 10), VIENNA))
        self.assertFalse(is_due(time(3, 10), None, at(day, 3, 9), VIENNA))

    def test_fall_back(self):
        # 25 October 2026: 03:00 → 02:00; 02:30 happens twice and fires the first time
        first = datetime(2026, 10, 25, 0, 30, 2, tzinfo=UTC)  # 02:30 CEST
        second = datetime(2026, 10, 25, 1, 30, 2, tzinfo=UTC)  # 02:30 CET
        self.assertTrue(is_due(time(2, 30), None, first, VIENNA))
        self.assertFalse(is_due(time(2, 30), date(2026, 10, 25), second, VIENNA))
        # 23:00 on that day is 25 hours after midnight; still on time
        self.assertTrue(is_due(time(23, 0), None, at(date(2026, 10, 25), 23, 0), VIENNA))


class DayEndTest(unittest.TestCase):
    """Reminders with a day end after midnight: times before it belong to the day that is ending."""

    def test_time_before_the_day_end_belongs_to_the_day_before(self):
        tuesday, wednesday = date(2026, 11, 24), date(2026, 11, 25)
        self.assertEqual(due_on(time(0, 30), None, at(wednesday, 0, 30), VIENNA, 2), tuesday)
        self.assertIsNone(due_on(time(0, 30), tuesday, at(wednesday, 0, 31), VIENNA, 2))
        # Tuesday 00:30 is Monday's reminder, already sent: nothing on Tuesday morning
        self.assertIsNone(due_on(time(0, 30), date(2026, 11, 23), at(tuesday, 0, 45, second=59), VIENNA, 2))
        self.assertIsNone(due_on(time(0, 30), None, at(tuesday, 0, 29), VIENNA, 2))
        # After the day end nothing changes
        self.assertEqual(due_on(time(23, 0), None, at(tuesday, 23, 0), VIENNA, 2), tuesday)
        self.assertEqual(due_on(time(7, 30), None, at(tuesday, 7, 30), VIENNA, 2), tuesday)

    def test_caught_up_just_after_the_day_end(self):
        tuesday, wednesday = date(2026, 11, 24), date(2026, 11, 25)
        # A restart over midnight: 23:55 is sent at 00:05, still for Tuesday
        self.assertEqual(due_on(time(23, 55), None, at(wednesday, 0, 5), VIENNA), tuesday)
        self.assertIsNone(due_on(time(23, 55), tuesday, at(wednesday, 0, 5), VIENNA))
        # The same over a day end of 01:00
        self.assertEqual(due_on(time(0, 55), None, at(wednesday, 1, 5), VIENNA, 1), tuesday)
        self.assertIsNone(due_on(time(0, 55), None, at(wednesday, 1, 11), VIENNA, 1))

    def test_spring_forward_inside_the_night(self):
        # 29 Mar 2026: 02:30 does not exist; with a day end of 03:00 it fires at 03:30 for Saturday
        saturday, sunday = date(2026, 3, 28), date(2026, 3, 29)
        self.assertEqual(due_on(time(2, 30), None, at(sunday, 3, 30), VIENNA, 3), saturday)
        self.assertIsNone(due_on(time(2, 30), saturday, at(sunday, 3, 31), VIENNA, 3))


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment(today=date(2026, 11, 24))  # a Tuesday
        self.addCleanup(self.env.close)
        self.env.create_user("alex", timezone="Europe/Vienna", locale="de")
        self.client = self.env.client("alex")
        self.requests: list[httpx.Request] = []
        self.status = 201
        self.receivers: dict[str, ec.EllipticCurvePrivateKey] = {}
        db = self.env.SessionLocal()
        try:
            vapid = Vapid(ensure_vapid_keys(db), "https://habits.example.org")
        finally:
            db.close()

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return httpx.Response(self.status)

        self.sender = PushSender(vapid, httpx.Client(transport=httpx.MockTransport(handler)))
        self.service = ReminderService(self.env.SessionLocal, self.sender)

    def device(self, client, name: str) -> None:
        receiver = ec.generate_private_key(ec.SECP256R1())
        body = push_subscription(name)
        body["keys"]["p256dh"] = b64url_encode(public_bytes(receiver))
        self.receivers[body["endpoint"]] = receiver
        self.assertEqual(client.post("/v1/push/subscriptions", json=body).status_code, 201)

    def habit(self, name: str, reminders: list[str], **fields) -> dict:
        body = {"name": name, "start_on": "2026-11-16", "reminders": reminders, **fields}
        response = self.client.post("/v1/habits", json=body)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def run_at(self, hour: int, minute: int, day: date = date(2026, 11, 24), zone: ZoneInfo = VIENNA) -> int:
        self.requests.clear()
        return self.service.run_due(at(day, hour, minute, zone))

    def payloads(self) -> list[dict]:
        return [json.loads(decrypt(r.content, self.receivers[str(r.url)], SECRET)) for r in self.requests]

    def test_open_habit_is_reminded_once(self):
        self.device(self.client, "phone")
        habit = self.habit("Lesen", ["07:30"], cue="nach dem Frühstück")
        self.assertEqual(self.run_at(7, 29), 0)
        self.assertEqual(self.run_at(7, 30), 1)
        payload = self.payloads()[0]
        self.assertEqual(payload["title"], "Lesen")
        self.assertEqual(payload["body"], "nach dem Frühstück")
        self.assertEqual(payload["habit"], {"id": habit["id"], "date": "2026-11-24", "version": 0, "user": 1})
        self.assertEqual(payload["done_label"], "Erledigt")
        self.assertEqual(payload["url"], "/today")
        self.assertEqual(self.requests[0].headers["Topic"], "reminders")
        self.assertEqual(self.run_at(7, 31), 0)
        self.assertEqual(self.run_at(7, 30, day=date(2026, 11, 25)), 1)

    def test_done_paused_archived_and_not_planned_stay_quiet(self):
        self.device(self.client, "phone")
        done = self.habit("Erledigt", ["07:30"])
        self.client.put(f"/v1/habits/{done['id']}/days/2026-11-24", json={"done": True})
        paused = self.habit("Pausiert", ["07:30"])
        self.client.post(
            "/v1/pauses", json={"habit_id": paused["id"], "start_on": "2026-11-24", "end_on": "2026-11-24"}
        )
        archived = self.habit("Archiviert", ["07:30"])
        self.client.post(f"/v1/habits/{archived['id']}/archive")
        self.habit("Nur Montag", ["07:30"], weekdays=1)
        self.habit("Später", ["07:30"], start_on="2026-12-01")
        self.assertEqual(self.run_at(7, 30), 0)
        self.assertEqual(self.requests, [])
        db = self.env.SessionLocal()
        try:
            # Due but quiet ones count as handled for today
            sent = {r.last_sent_on for r in db.query(HabitReminder)} - {None}
        finally:
            db.close()
        self.assertEqual(sent, {date(2026, 11, 24)})

    def test_account_pause_stays_quiet(self):
        self.device(self.client, "phone")
        self.habit("Lesen", ["07:30"])
        self.client.post("/v1/pauses", json={"start_on": "2026-11-20", "end_on": "2026-11-30"})
        self.assertEqual(self.run_at(7, 30), 0)

    def test_quantity_and_weekly_texts(self):
        self.device(self.client, "phone")
        water = self.habit("Wasser", ["09:00"], goal_type="quantity", target=8, unit="Gläser")
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-24", json={"value": 3})
        self.habit("Laufen", ["10:00"], goal_type="weekly_count", target=3)
        self.assertEqual(self.run_at(9, 0), 1)
        payload = self.payloads()[0]
        self.assertEqual((payload["title"], payload["body"], payload["habit"]), ("Wasser", "3 von 8 Gläser", None))
        self.assertEqual(self.run_at(10, 0), 1)
        payload = self.payloads()[0]
        self.assertEqual((payload["title"], payload["body"]), ("Laufen", "0 von 3 diese Woche"))
        self.assertIsNotNone(payload["habit"])

    def test_quantity_reached_and_weekly_target_met_stay_quiet(self):
        self.device(self.client, "phone")
        water = self.habit("Wasser", ["09:00"], goal_type="quantity", target=2)
        self.client.put(f"/v1/habits/{water['id']}/days/2026-11-24", json={"value": 2})
        run = self.habit("Laufen", ["09:00"], goal_type="weekly_count", target=1)
        self.client.put(f"/v1/habits/{run['id']}/days/2026-11-23", json={"done": True})
        self.assertEqual(self.run_at(9, 0), 0)

    def test_same_minute_is_bundled_without_button(self):
        self.device(self.client, "phone")
        self.habit("Lesen", ["20:00"])
        self.habit("Dehnen", ["20:00"])
        self.habit("Zähne", ["20:00", "07:00"])
        self.assertEqual(self.run_at(20, 0), 1)
        payload = self.payloads()[0]
        self.assertEqual(payload["title"], "3 Gewohnheiten offen")
        self.assertEqual(payload["body"], "Lesen, Dehnen, Zähne")
        self.assertIsNone(payload["habit"])

    def test_every_device_gets_it_and_gone_devices_are_removed(self):
        self.device(self.client, "phone")
        self.device(self.env.client("alex"), "laptop")
        self.habit("Lesen", ["07:30"])
        self.assertEqual(self.run_at(7, 30), 2)
        self.assertEqual({str(r.url).rsplit("/", 1)[1] for r in self.requests}, {"phone", "laptop"})
        self.habit("Dehnen", ["08:00"])
        self.status = 410
        self.assertEqual(self.run_at(8, 0), 0)
        db = self.env.SessionLocal()
        try:
            self.assertEqual(db.query(PushSubscription).count(), 0)
        finally:
            db.close()

    def test_failures_are_recorded_and_not_retried(self):
        self.device(self.client, "phone")
        self.habit("Lesen", ["07:30"])
        self.status = 500
        with self.assertLogs("app.services.webpush.sender", "WARNING"):
            self.assertEqual(self.run_at(7, 30), 0)
        self.status = 201
        self.assertEqual(self.run_at(7, 31), 0)
        db = self.env.SessionLocal()
        try:
            self.assertEqual(db.query(PushSubscription).one().last_error, "HTTP 500")
        finally:
            db.close()

    def set_day_end(self, hour: int) -> None:
        db = self.env.SessionLocal()
        try:
            db.query(User).filter(User.username == "alex").update({"day_end_hour": hour})
            db.commit()
        finally:
            db.close()

    def test_reminder_after_midnight_belongs_to_the_day_before(self):
        self.set_day_end(2)
        self.device(self.client, "phone")
        habit = self.habit("Lesen", ["00:30", "23:00"])
        self.assertEqual(self.run_at(23, 0), 1)
        self.assertEqual(self.payloads()[0]["habit"]["date"], "2026-11-24")
        # Wednesday 00:30 is still Tuesday: open, and the button checks off Tuesday
        self.assertEqual(self.run_at(0, 30, day=date(2026, 11, 25)), 1)
        self.assertEqual(self.payloads()[0]["habit"]["date"], "2026-11-24")
        # Done for Tuesday: Wednesday 00:30 stays quiet the next time around (that is Wednesday's)
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True})
        self.assertEqual(self.run_at(0, 31, day=date(2026, 11, 25)), 0)
        db = self.env.SessionLocal()
        try:
            sent = sorted((r.time.isoformat(), r.last_sent_on.isoformat()) for r in db.query(HabitReminder))
        finally:
            db.close()
        self.assertEqual(sent, [("00:30:00", "2026-11-24"), ("23:00:00", "2026-11-24")])

    def test_done_late_at_night_keeps_the_reminder_quiet(self):
        self.set_day_end(2)
        self.device(self.client, "phone")
        habit = self.habit("Lesen", ["00:30"])
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True})
        self.assertEqual(self.run_at(0, 30, day=date(2026, 11, 25)), 0)

    def test_time_zone_and_language_per_account(self):
        self.device(self.client, "alex")
        self.habit("Lesen", ["07:30"])
        self.env.create_user("sam", timezone="America/New_York", locale="en")
        sam = self.env.client("sam")
        self.device(sam, "sam")
        sam.post("/v1/habits", json={"name": "Run", "start_on": "2026-11-16", "reminders": ["07:30"]})
        sam.post("/v1/habits", json={"name": "Read", "start_on": "2026-11-16", "reminders": ["07:30"]})
        self.assertEqual(self.run_at(7, 30), 1)
        self.assertEqual(str(self.requests[0].url).rsplit("/", 1)[1], "alex")
        self.assertEqual(self.run_at(7, 30, zone=ZoneInfo("America/New_York")), 1)
        self.assertEqual(self.payloads()[0]["title"], "2 habits open")

    def test_accounts_without_device_or_inactive_are_skipped(self):
        self.habit("Lesen", ["07:30"])
        self.assertEqual(self.run_at(7, 30), 0)
        db = self.env.SessionLocal()
        try:
            # Nothing was due for an account without devices, so a device added later still gets it
            self.assertEqual({r.last_sent_on for r in db.query(HabitReminder)}, {None})
        finally:
            db.close()
        self.device(self.client, "phone")
        self.assertEqual(self.run_at(7, 31), 1)

    def test_done_button_carries_the_entry_version(self):
        self.device(self.client, "phone")
        habit = self.habit("Lesen", ["07:30"])
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": True})
        self.client.put(f"/v1/habits/{habit['id']}/days/2026-11-24", json={"done": False})
        self.assertEqual(self.run_at(7, 30), 1)
        self.assertEqual(self.payloads()[0]["habit"]["version"], 2)

    def test_editing_does_not_fire_again(self):
        self.device(self.client, "phone")
        habit = self.habit("Lesen", ["07:30"])
        self.assertEqual(self.run_at(7, 30), 1)
        self.client.patch(f"/v1/habits/{habit['id']}", json={"reminders": ["07:30", "07:00"], "name": "Buch"})
        self.assertEqual(self.run_at(7, 32), 0)


class PayloadTest(unittest.TestCase):
    def test_long_lists_are_shortened(self):
        from app.services.day_service import DayInfo
        from app.services.reminder_service import OpenHabit

        class FakeHabit:
            def __init__(self, index):
                self.id, self.name, self.cue, self.unit = index, f"Gewohnheit {index} " + "x" * 100, None, None

        day = DayInfo(date=date(2026, 11, 24), planned=True, done=False, state="open")
        items = [OpenHabit(FakeHabit(i), day, None) for i in range(60)]
        payload = build_payload("de", items, date(2026, 11, 24), 1)
        self.assertLessEqual(len(json.dumps(payload, ensure_ascii=False).encode()), 3000)
        self.assertTrue(payload["body"].endswith(" …"))
        self.assertEqual(payload["title"], "60 Gewohnheiten offen")


class SchedulerTest(unittest.TestCase):
    def test_next_run_is_two_seconds_after_the_minute(self):
        self.assertEqual(seconds_until_next_run(datetime(2026, 11, 24, 7, 29, 0, tzinfo=UTC)), 62)
        self.assertEqual(seconds_until_next_run(datetime(2026, 11, 24, 7, 29, 59, 500000, tzinfo=UTC)), 2.5)

    def test_loop_runs_survives_errors_and_stops(self):
        sender = mock.Mock(spec=PushSender)
        scheduler = ReminderScheduler(mock.Mock(), sender=sender)
        calls = []

        def tick():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("database is locked")
            return 0

        async def scenario():
            with (
                mock.patch("app.services.scheduler.seconds_until_next_run", return_value=0),
                mock.patch.object(scheduler, "tick", side_effect=tick),
                self.assertLogs("app.services.scheduler", "ERROR"),
            ):
                scheduler.start()
                while len(calls) < 3:
                    await asyncio.sleep(0.01)
                await scheduler.stop()

        asyncio.run(scenario())
        self.assertGreaterEqual(len(calls), 3)
        sender.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
