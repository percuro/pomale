import unittest
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.day_service import (
    ALL_WEEKDAYS,
    Entry,
    Quota,
    WeekProgress,
    entries_from_done,
    evaluate_range,
    is_planned,
    raw_days,
    reduced_target,
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
    goal_type: str = "days"
    target: int | None = None


def build_days(schedules, done, start, end, today):
    return evaluate_range(schedules, entries_from_done(done), [], start, end, today).days


def quota_of(schedules, done, start, end, today):
    return evaluate_range(schedules, entries_from_done(done), [], start, end, today).quota


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

    def test_day_end_after_midnight(self):
        # Wednesday 25 Nov, local times in Vienna
        def local(hour, minute, day=25):
            return datetime(2026, 11, day, hour, minute, tzinfo=VIENNA)

        self.assertEqual(today_in(VIENNA, local(0, 59), day_end_hour=1), date(2026, 11, 24))
        self.assertEqual(today_in(VIENNA, local(1, 0), day_end_hour=1), date(2026, 11, 25))
        self.assertEqual(today_in(VIENNA, local(0, 0), day_end_hour=0), date(2026, 11, 25))
        self.assertEqual(today_in(VIENNA, local(5, 59), day_end_hour=6), date(2026, 11, 24))
        self.assertEqual(today_in(VIENNA, local(23, 59, day=24), day_end_hour=6), date(2026, 11, 24))
        # The moment may come in any zone
        self.assertEqual(
            today_in(VIENNA, datetime(2026, 11, 24, 23, 30, tzinfo=ZoneInfo("UTC")), 1), date(2026, 11, 24)
        )

    def test_day_end_keeps_monday_night_in_the_old_week(self):
        monday_night = datetime(2026, 11, 30, 0, 30, tzinfo=VIENNA)
        self.assertEqual(week_start(today_in(VIENNA, monday_night, day_end_hour=1)), date(2026, 11, 23))
        self.assertEqual(week_start(today_in(VIENNA, monday_night)), date(2026, 11, 30))

    def test_day_end_on_clock_change_nights(self):
        new_york = ZoneInfo("America/New_York")
        utc = ZoneInfo("UTC")
        # Spring, 8 Mar 2026: 01:59 EST is followed by 03:00 EDT; with a day end of 02:00 the night
        # is one hour shorter, nothing is skipped or counted twice
        self.assertEqual(today_in(new_york, datetime(2026, 3, 8, 6, 59, tzinfo=utc), 2), date(2026, 3, 7))
        self.assertEqual(today_in(new_york, datetime(2026, 3, 8, 7, 0, tzinfo=utc), 2), date(2026, 3, 8))
        # Autumn, 1 Nov 2026: 01:30 happens twice, both still belong to Saturday; 02:00 EST is Sunday
        self.assertEqual(today_in(new_york, datetime(2026, 11, 1, 5, 30, tzinfo=utc), 2), date(2026, 10, 31))
        self.assertEqual(today_in(new_york, datetime(2026, 11, 1, 6, 30, tzinfo=utc), 2), date(2026, 10, 31))
        self.assertEqual(today_in(new_york, datetime(2026, 11, 1, 7, 0, tzinfo=utc), 2), date(2026, 11, 1))

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
        q_before = quota_of(before, done, week, week + timedelta(days=6), today)
        q_after = quota_of(after, done, week, week + timedelta(days=6), today)
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
        today = date(2026, 11, 26)  # Thursday
        monday, wednesday = date(2026, 11, 23), date(2026, 11, 25)

        def states(schedules, done):
            return [d.state for d in build_days(schedules, done, monday, today + timedelta(days=1), today)]

        planned = [Schedule(date(2026, 11, 1), MON | TUE | THU)]
        self.assertEqual(states(planned, set()), ["open", "open", "not_planned", "open", "future"])
        self.assertEqual(
            states(planned, {monday, monday + timedelta(days=1), today}),
            ["done", "done", "not_planned", "done", "future"],
        )
        self.assertEqual(states([Schedule(date(2026, 11, 1), MON)], {wednesday})[2], "extra_done")

    def test_quota_four_of_five(self):
        # plan Mon–Fri, today is Saturday; Wednesday missed; Saturday done as extra
        week = date(2026, 11, 16)
        schedules = [Schedule(date(2026, 11, 1), MON | TUE | WED | THU | FRI)]
        done = {date(2026, 11, 16), date(2026, 11, 17), date(2026, 11, 19), date(2026, 11, 20), date(2026, 11, 21)}
        today = date(2026, 11, 21)
        days = build_days(schedules, done, week, week + timedelta(days=6), today)
        self.assertEqual(days[5].state, "extra_done")
        self.assertEqual(days[6].state, "future")
        self.assertEqual(quota_of(schedules, done, week, week + timedelta(days=6), today), Quota(done=4, due=5))

    def test_open_today_does_not_count_against_quota(self):
        week = date(2026, 11, 23)
        schedules = [Schedule(date(2026, 11, 1), ALL_WEEKDAYS)]
        today = date(2026, 11, 24)
        q = quota_of(schedules, {date(2026, 11, 23)}, week, week + timedelta(days=6), today)
        self.assertEqual((q.done, q.due), (1, 1))
        q = quota_of(schedules, {date(2026, 11, 23), today}, week, week + timedelta(days=6), today)
        self.assertEqual((q.done, q.due), (2, 2))

    def test_future_done_entries_are_ignored(self):
        week = date(2026, 11, 23)
        schedules = [Schedule(date(2026, 11, 1), ALL_WEEKDAYS)]
        today = date(2026, 11, 24)
        days = build_days(schedules, {date(2026, 11, 26)}, week, week + timedelta(days=6), today)
        self.assertFalse(days[3].done)
        self.assertEqual(days[3].state, "future")


@dataclass
class Pause:
    start_on: date
    end_on: date


MONDAY = date(2026, 11, 16)
SUNDAY = MONDAY + timedelta(days=6)


def weekly(valid_from, target, weekdays=ALL_WEEKDAYS):
    return Schedule(valid_from, weekdays, "weekly_count", target)


class ReducedTargetTest(unittest.TestCase):
    def test_round_half_up_and_at_least_one(self):
        self.assertEqual(reduced_target(3, 7), 3)
        self.assertEqual(reduced_target(3, 5), 2)  # 2.14
        self.assertEqual(reduced_target(5, 4), 3)  # 2.86
        self.assertEqual(reduced_target(7, 3), 3)
        self.assertEqual(reduced_target(7, 1), 1)
        self.assertEqual(reduced_target(3, 1), 1)  # 0.43, but one active day is left
        self.assertEqual(reduced_target(1, 4), 1)  # 0.57
        self.assertEqual(reduced_target(3, 0), 0)


class RawDaysTest(unittest.TestCase):
    def raw(self, schedules, pauses=(), entries=None, today=date(2026, 11, 25)):
        return raw_days(schedules, entries or {}, list(pauses), MONDAY, SUNDAY, today)

    def test_whole_weeks_around_the_range(self):
        days = raw_days([Schedule(date(2026, 11, 1), ALL_WEEKDAYS)], {}, [], date(2026, 11, 20), date(2026, 11, 24),
                        date(2026, 11, 25))  # fmt: skip
        self.assertEqual((days[0].date, days[-1].date, len(days)), (MONDAY, date(2026, 11, 29), 14))

    def test_first_week_of_a_weekly_goal_has_a_reduced_target(self):
        days = self.raw([weekly(date(2026, 11, 18), 3)])  # from Wednesday: 5 active days
        self.assertEqual([d.goal_type for d in days[:3]], ["days", "days", "weekly_count"])
        self.assertEqual({d.target for d in days[2:]}, {2})
        self.assertEqual([d.planned for d in days], [False, False, True, True, True, True, True])

    def test_pauses_reduce_the_weekly_target_and_mark_days(self):
        days = self.raw([weekly(date(2026, 11, 1), 3)], [Pause(date(2026, 11, 21), date(2026, 11, 30))])
        self.assertEqual({d.target for d in days}, {2})
        self.assertEqual([d.paused for d in days], [False] * 5 + [True] * 2)
        self.assertEqual([d.planned for d in days], [True] * 5 + [False] * 2)

    def test_pause_on_an_unplanned_day_is_not_marked(self):
        days = self.raw([Schedule(date(2026, 11, 1), MON | TUE)], [Pause(MONDAY, SUNDAY)])
        self.assertEqual([d.paused for d in days], [True, True, False, False, False, False, False])

    def test_weekly_target_comes_from_the_plan_at_the_end_of_the_week(self):
        days = self.raw([weekly(date(2026, 11, 1), 3), weekly(date(2026, 11, 19), 5)], today=date(2026, 11, 30))
        self.assertEqual({d.target for d in days}, {5})

    def test_running_week_uses_todays_plan(self):
        days = self.raw([weekly(date(2026, 11, 1), 3), weekly(date(2026, 11, 20), 5)], today=date(2026, 11, 19))
        self.assertEqual({d.target for d in days}, {3})

    def test_archiving_mid_week_reduces_the_target(self):
        schedules = [weekly(date(2026, 11, 1), 3), weekly(date(2026, 11, 19), 3, weekdays=0)]
        days = self.raw(schedules, today=date(2026, 11, 30))
        self.assertEqual({d.target for d in days}, {1})  # 3 active days: 1.29
        self.assertEqual([d.planned for d in days], [True, True, True, False, False, False, False])

    def test_quantity_values_and_old_check_offs(self):
        schedules = [
            Schedule(date(2026, 11, 1), ALL_WEEKDAYS),
            Schedule(date(2026, 11, 18), ALL_WEEKDAYS, "quantity", 8),
        ]
        entries = {
            MONDAY: Entry(done=True),
            date(2026, 11, 18): Entry(done=True),  # done without a value: counts as reached
            date(2026, 11, 19): Entry(done=True, value=3),
            date(2026, 11, 20): Entry(done=False, value=0),
        }
        days = self.raw(schedules, entries=entries)
        self.assertEqual([d.value for d in days[2:5]], [8, 3, 0])
        self.assertEqual([d.target for d in days[:3]], [None, None, 8])
        self.assertTrue(days[0].done)


class EvaluateRangeTest(unittest.TestCase):
    def test_weekly_goal_end_to_end(self):
        schedules = [weekly(date(2026, 11, 1), 3)]
        entries = entries_from_done([MONDAY, date(2026, 11, 18)])
        today = date(2026, 11, 19)
        result = evaluate_range(schedules, entries, [], MONDAY, SUNDAY, today)
        self.assertEqual(result.week, WeekProgress(done=2, target=3))
        self.assertEqual(result.days[3].state, "open")
        self.assertEqual(result.quota, Quota(done=2, due=2))

    def test_pause_keeps_the_quota_of_a_days_goal_intact(self):
        schedules = [Schedule(date(2026, 11, 1), MON | TUE | WED | THU | FRI)]
        entries = entries_from_done([MONDAY, date(2026, 11, 17)])
        pauses = [Pause(date(2026, 11, 18), date(2026, 11, 20))]
        result = evaluate_range(schedules, entries, pauses, MONDAY, SUNDAY, date(2026, 11, 23))
        self.assertEqual(result.quota, Quota(done=2, due=2))
        self.assertEqual([d.state for d in result.days][2:5], ["paused"] * 3)

    def test_quantity_quota_over_a_plan_change(self):
        schedules = [
            Schedule(date(2026, 11, 1), ALL_WEEKDAYS, "quantity", 8),
            Schedule(date(2026, 11, 19), ALL_WEEKDAYS, "quantity", 4),
        ]
        entries = {MONDAY + timedelta(days=i): Entry(done=True, value=5) for i in range(7)}
        result = evaluate_range(schedules, entries, [], MONDAY, SUNDAY, date(2026, 11, 23))
        # 5 of 8 until Wednesday, 5 of 4 from Thursday
        self.assertEqual([d.state for d in result.days], ["partial"] * 3 + ["done"] * 4)
        self.assertEqual(result.quota, Quota(done=4, due=7))


if __name__ == "__main__":
    unittest.main()
