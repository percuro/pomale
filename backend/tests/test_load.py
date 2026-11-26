"""Many habits and two years of check-ins: the main reads must not make a query per habit (N+1)."""

import os
import time
import unittest
from contextlib import contextmanager
from datetime import date, timedelta

from sqlalchemy import event, text

from tests.support import ApiTestEnvironment

TODAY = date(2026, 11, 24)
START = TODAY - timedelta(days=730)
INSERT_CHECKIN = text("INSERT INTO checkins (habit_id, local_date, done, value, version) VALUES (:h, :d, 1, :v, 1)")
READS = {
    "days": f"/v1/days?from={TODAY - timedelta(days=6)}&to={TODAY}",
    "history": f"/v1/history?from={TODAY - timedelta(days=365)}&to={TODAY}",
    "today": "/v1/today",
    "habits": "/v1/habits",
    "export.json": "/v1/export.json",
    "export.csv": "/v1/export.csv",
}


class LoadTest(unittest.TestCase):
    def account(self, habits: int) -> tuple[ApiTestEnvironment, object]:
        env = ApiTestEnvironment(today=TODAY)
        self.addCleanup(env.close)
        env.create_user("alex")
        client = env.client("alex")
        goals = [
            {},
            {"weekdays": 21},
            {"goal_type": "weekly_count", "target": 3},
            {"goal_type": "quantity", "target": 8},
        ]
        ids = []
        for number in range(habits):
            body = {"name": f"Habit {number}", "start_on": str(START), **goals[number % len(goals)]}
            response = client.post("/v1/habits", json=body)
            self.assertEqual(response.status_code, 201, response.text)
            ids.append(response.json()["id"])
        rows = [
            {"h": habit, "d": START + timedelta(days=offset), "v": 5 if index % 4 == 3 else None}
            for index, habit in enumerate(ids)
            for offset in range(731)
            if (offset + index) % 10 < 7
        ]
        with env.engine.begin() as connection:
            connection.execute(
                INSERT_CHECKIN,
                rows,
            )
        return env, client

    @contextmanager
    def counting(self, env: ApiTestEnvironment):
        statements: list[str] = []

        def count(_conn, _cursor, statement, *_args):
            statements.append(statement)

        event.listen(env.engine, "before_cursor_execute", count)
        try:
            yield statements
        finally:
            event.remove(env.engine, "before_cursor_execute", count)

    def measure(self, habits: int) -> dict[str, tuple[int, float]]:
        env, client = self.account(habits)
        result = {}
        for name, path in READS.items():
            with self.counting(env) as statements:
                started = time.perf_counter()
                response = client.get(path)
                elapsed = time.perf_counter() - started
            self.assertEqual(response.status_code, 200, (name, response.text[:200]))
            result[name] = (len(statements), elapsed)
        return result

    def test_queries_do_not_grow_with_the_number_of_habits(self):
        few, many = self.measure(3), self.measure(30)
        for name in READS:
            with self.subTest(read=name):
                self.assertEqual(many[name][0], few[name][0], f"{name}: {few[name][0]} → {many[name][0]} queries")
        if os.getenv("LOAD_REPORT"):
            for name, (queries, elapsed) in many.items():
                print(f"{name:12} {queries:3} queries {elapsed * 1000:7.1f} ms")


if __name__ == "__main__":
    unittest.main()
