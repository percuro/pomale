import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.day_service import (
    ALL_WEEKDAYS,
    Quota,
    build_days,
    day_state,
    is_planned,
    quota,
    today_in,
    week_start,
    weekdays_for,
)

VIENNA = ZoneInfo("Europe/Vienna")
MON, TUE, WED, THU, FRI, SAT, SUN = (1 << i for i in range(7))


@dataclass
class Schedule:
    valid_from: date
    weekdays: int


class TodayTest(unittest.TestCase):
    def test_uses_tracker_timezone_not_utc(self):
        # 23:30 UTC on 24 Nov is already 25 Nov in Vienna
        utc_late = datetime(2026, 11, 24, 23, 30, tzinfo=ZoneInfo("UTC"))
        self.assertEqual(today_in(VIENNA, utc_late), date(2026, 11, 25))

    def test_daylight_saving_switch(self):
        # DST starts 29 Mar 2026: 00:30 UTC = 01:30 CET, 01:30 UTC = 03:30 CEST
        self.assertEqual(today_in(VIENNA, datetime(2026, 3, 28, 22, 59, tzinfo=ZoneInfo("UTC"))), date(2026, 3, 28))
        self.assertEqual(today_in(VIENNA, datetime(2026, 3, 28, 23, 0, tzinfo=ZoneInfo("UTC"))), date(2026, 3, 29))
        # DST ends 25 Oct 2026: midnight in Vienna = 22:00 UTC the day before
        self.assertEqual(today_in(VIENNA, datetime(2026, 10, 24, 21, 59, tzinfo=ZoneInfo("UTC"))), date(2026, 10, 24))
        self.assertEqual(today_in(VIENNA, datetime(2026, 10, 24, 22, 0, tzinfo=ZoneInfo("UTC"))), date(2026, 10, 25))
        self.assertEqual(today_in(VIENNA, datetime(2026, 10, 25, 22, 59, tzinfo=ZoneInfo("UTC"))), date(2026, 10, 25))
        self.assertEqual(today_in(VIENNA, datetime(2026, 10, 25, 23, 0, tzinfo=ZoneInfo("UTC"))), date(2026, 10, 26))

    def test_naive_datetime_rejected(self):
        with self.assertRaises(ValueError):
            today_in(VIENNA, datetime(2026, 11, 24, 12, 0))

    def test_week_starts_monday(self):
        self.assertEqual(week_start(date(2026, 11, 29)), date(2026, 11, 23))
        self.assertEqual(week_start(date(2026, 11, 23)), date(2026, 11, 23))


class ScheduleTest(unittest.TestCase):
    def test_schedule_valid_from_applies_only_forward(self):
        schedules = [
            Schedule(date(2026, 11, 1), ALL_WEEKDAYS),
            Schedule(date(2026, 11, 16), MON | FRI),
        ]
        self.assertEqual(weekdays_for(schedules, date(2026, 10, 31)), 0)
        self.assertEqual(weekdays_for(schedules, date(2026, 11, 10)), ALL_WEEKDAYS)
        self.assertEqual(weekdays_for(schedules, date(2026, 11, 16)), MON | FRI)
        self.assertTrue(is_planned(schedules, date(2026, 11, 11)))  # Wednesday, old plan
        self.assertFalse(is_planned(schedules, date(2026, 11, 18)))  # Wednesday, new plan
        self.assertTrue(is_planned(schedules, date(2026, 11, 20)))  # Friday

    def test_previous_week_quota_stays_after_plan_change(self):
        week = date(2026, 11, 9)
        done = {week + timedelta(days=i) for i in range(5)}  # Mon–Fri done
        before = [Schedule(date(2026, 11, 1), MON | TUE | WED | THU | FRI)]
        after = before + [Schedule(date(2026, 11, 16), MON)]
        today = date(2026, 11, 18)
        q_before = quota(build_days(before, done, week, week + timedelta(days=6), today), today)
        q_after = quota(build_days(after, done, week, week + timedelta(days=6), today), today)
        self.assertEqual(q_before, q_after)
        self.assertEqual((q_after.done, q_after.due), (5, 5))

    def test_retroactive_plan_change_changes_only_days_from_valid_from(self):
        week = date(2026, 11, 16)
        schedules = [
            Schedule(date(2026, 11, 1), ALL_WEEKDAYS),
            Schedule(date(2026, 11, 18), SAT | SUN),  # retroactively from Wednesday
        ]
        today = date(2026, 11, 20)
        days = build_days(schedules, set(), week, week + timedelta(days=6), today)
        states = [d.state for d in days]
        self.assertEqual(states, ["open", "open", "not_planned", "not_planned", "not_planned", "future", "future"])

    def test_archived_schedule_zero_means_not_planned(self):
        schedules = [Schedule(date(2026, 11, 1), ALL_WEEKDAYS), Schedule(date(2026, 11, 20), 0)]
        self.assertTrue(is_planned(schedules, date(2026, 11, 19)))
        self.assertFalse(is_planned(schedules, date(2026, 11, 20)))


class StateAndQuotaTest(unittest.TestCase):
    def test_states(self):
        today = date(2026, 11, 24)
        self.assertEqual(day_state(True, False, today, today), "open")
        self.assertEqual(day_state(True, True, today, today), "done")
        self.assertEqual(day_state(False, True, today, today), "extra_done")
        self.assertEqual(day_state(False, False, today, today), "not_planned")
        self.assertEqual(day_state(True, False, today + timedelta(days=1), today), "future")

    def test_quota_four_of_five(self):
        # plan Mon–Fri, today is Saturday; Wednesday missed; Saturday done as extra
        week = date(2026, 11, 16)
        schedules = [Schedule(date(2026, 11, 1), MON | TUE | WED | THU | FRI)]
        done = {date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21)}
        today = date(2026, 11, 21)
        days = build_days(schedules, done, week, week + timedelta(days=6), today)
        self.assertEqual(days[5].state, "extra_done")
        self.assertEqual(days[6].state, "future")
        self.assertEqual(quota(days, today), Quota(done=4, due=5))

    def test_open_today_does_not_count_against_quota(self):
        week = date(2026, 11, 23)
        schedules = [Schedule(date(2026, 11, 1), ALL_WEEKDAYS)]
        today = date(2026, 11, 24)
        days = build_days(schedules, {date(2026, 11, 23)}, week, week + timedelta(days=6), today)
        q = quota(days, today)
        self.assertEqual((q.done, q.due), (1, 1))
        days = build_days(schedules, {date(2026, 11, 23), today}, week, week + timedelta(days=6), today)
        q = quota(days, today)
        self.assertEqual((q.done, q.due), (2, 2))

    def test_future_done_entries_are_ignored(self):
        week = date(2026, 11, 23)
        schedules = [Schedule(date(2026, 11, 1), ALL_WEEKDAYS)]
        today = date(2026, 11, 24)
        days = build_days(schedules, {date(2026, 11, 26)}, week, week + timedelta(days=6), today)
        self.assertFalse(days[3].done)
        self.assertEqual(days[3].state, "future")


if __name__ == "__main__":
    unittest.main()
