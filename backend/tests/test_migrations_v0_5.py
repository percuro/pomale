"""Upgrade a real pomale 0.5.0 database (fixtures/v0.5.0.sql) to the current schema."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic, table_columns, table_source

FIXTURE = Path(__file__).with_name("fixtures") / "v0.5.0.sql"
DATA_TABLES = (
    "users",
    "user_sessions",
    "oidc_identities",
    "habits",
    "habit_schedules",
    "checkins",
    "shortcut_tokens",
    "audit_events",
)


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def _original_columns() -> dict[str, set[str]]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(FIXTURE.read_text(encoding="utf-8"))
    columns = {table: set(_columns(connection, table)) for table in DATA_TABLES}
    connection.close()
    return columns


ORIGINAL_COLUMNS = _original_columns()


def snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    """All 0.5.0 columns of the 0.5.0 tables, so new columns do not affect the comparison."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in table_columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        result[table] = connection.execute(
            f"SELECT {', '.join(original)} FROM {table_source(connection, table)} ORDER BY 1, 2"
        ).fetchall()
    return result


class UpgradeFromV050Test(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "habits.db"
        connection = sqlite3.connect(self.path)
        connection.executescript(FIXTURE.read_text(encoding="utf-8"))
        self.before = snapshot(connection)
        connection.close()

    def tearDown(self):
        self.directory.cleanup()

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def test_fixture_is_at_schema_0004_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0004",))
        connection.close()
        self.assertEqual(len(self.before["habits"]), 3)
        self.assertEqual(len(self.before["habit_schedules"]), 5)
        self.assertEqual(len(self.before["checkins"]), 4)

    def test_upgrade_keeps_data_and_makes_existing_plans_day_goals(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        # Rebuilding habits, schedules and check-ins must not cascade anywhere
        self.assertEqual(snapshot(connection), self.before)
        self.assertEqual(
            connection.execute("SELECT DISTINCT goal_type, target FROM habit_schedules").fetchall(), [("days", None)]
        )
        self.assertEqual(
            connection.execute("SELECT DISTINCT unit, color, group_id FROM habits").fetchall(), [(None, None, None)]
        )
        self.assertEqual(connection.execute("SELECT DISTINCT value, note FROM checkins").fetchall(), [(None, None)])
        for table in ("habit_groups", "habit_pauses"):
            self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone(), (0,))
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_goal_and_value_checks(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        insert = (
            "INSERT INTO habit_schedules (habit_id, valid_from, weekdays, goal_type, target) VALUES (?, ?, ?, ?, ?)"
        )
        connection.execute(insert, (3, "2026-12-01", 127, "weekly_count", 3))
        connection.execute(insert, (3, "2026-12-08", 21, "quantity", 8))
        for row in (
            (3, "2026-12-15", 127, "weekly_count", 8),
            (3, "2026-12-15", 127, "weekly_count", None),
            (3, "2026-12-15", 127, "quantity", 0),
            (3, "2026-12-15", 127, "days", 2),
            (3, "2026-12-15", 127, "monthly", 2),
        ):
            with self.assertRaises(sqlite3.IntegrityError, msg=row):
                connection.execute(insert, row)
        connection.execute("UPDATE checkins SET value = 9999, note = 'ok' WHERE habit_id = 3")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("UPDATE checkins SET value = -1 WHERE habit_id = 3")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO habit_pauses (user_id, start_on, end_on) VALUES (1, '2026-12-02', '2026-12-01')"
            )
        connection.close()

    def test_deleting_a_group_keeps_its_habits(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO habit_groups (id, user_id, name, sort_order) VALUES (1, 1, 'Morning', 1)")
        connection.execute("UPDATE habits SET group_id = 1 WHERE id = 1")
        connection.execute("DELETE FROM habit_groups WHERE id = 1")
        habit = connection.execute("SELECT name, group_id FROM habits WHERE id = 1").fetchone()
        self.assertEqual(habit, ("Lesen", None))
        connection.close()

    def test_downgrade_keeps_data_and_turns_new_goals_into_day_plans(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute(
            "INSERT INTO habit_schedules (habit_id, valid_from, weekdays, goal_type, target)"
            " VALUES (3, '2026-12-01', 127, 'weekly_count', 3)"
        )
        connection.execute("INSERT INTO habit_groups (id, user_id, name, sort_order) VALUES (1, 1, 'Morning', 1)")
        connection.execute("UPDATE habits SET group_id = 1, color = 'teal' WHERE id = 1")
        connection.execute("UPDATE checkins SET value = 3, note = 'x' WHERE habit_id = 3")
        connection.commit()
        connection.close()
        alembic(self.path, "downgrade", "0004")
        connection = self.connect()
        self.assertEqual(
            connection.execute("SELECT weekdays FROM habit_schedules WHERE valid_from = '2026-12-01'").fetchone(),
            (127,),
        )
        connection.execute("DELETE FROM habit_schedules WHERE valid_from = '2026-12-01'")
        connection.commit()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
