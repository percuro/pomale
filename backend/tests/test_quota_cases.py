"""Run the shared evaluation cases (fixtures/quota_cases.json); the web app runs the same set."""

import json
import unittest
from datetime import date, timedelta
from pathlib import Path

from app.services.day_service import Quota, RawDay, WeekProgress, evaluate

CASES = json.loads((Path(__file__).with_name("fixtures") / "quota_cases.json").read_text(encoding="utf-8"))["cases"]


def _per_day(value, index):
    return value[index] if isinstance(value, list) else value


def raw_days(case) -> list[RawDay]:
    result = []
    for week in case["weeks"]:
        monday = date.fromisoformat(week["start"])
        values = week.get("value") or [0] * 7
        for i in range(7):
            result.append(
                RawDay(
                    date=monday + timedelta(days=i),
                    goal_type=_per_day(week["goal_type"], i),
                    target=_per_day(week["target"], i),
                    planned=week["planned"][i] == "1",
                    paused=week["paused"][i] == "1",
                    done=week["done"][i] == "1",
                    value=values[i],
                )
            )
    return result


class SharedQuotaCasesTest(unittest.TestCase):
    def test_cases(self):
        self.assertGreater(len(CASES), 10)
        for case in CASES:
            with self.subTest(case["name"]):
                result = evaluate(
                    raw_days(case),
                    date.fromisoformat(case["today"]),
                    date.fromisoformat(case["start"]),
                    date.fromisoformat(case["end"]),
                )
                expect = case["expect"]
                self.assertEqual([d.state for d in result.days], expect["states"])
                self.assertEqual(result.quota, Quota(**expect["quota"]))
                self.assertEqual(result.week, WeekProgress(**expect["week"]) if expect["week"] else None)
                if "weeks" in expect:
                    self.assertEqual(
                        [(monday.isoformat(), q.done, q.due) for monday, q in result.weeks],
                        [tuple(w) for w in expect["weeks"]],
                    )


if __name__ == "__main__":
    unittest.main()
