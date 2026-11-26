"""Upgrade a real pomale 0.6.0 database (fixtures/v0.6.0.sql) to the current schema."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic, table_columns, table_source

FIXTURE = Path(__file__).with_name("fixtures") / "v0.6.0.sql"
DATA_TABLES = (
    "users",
    "user_sessions",
    "oidc_identities",
    "habit_groups",
    "habits",
    "habit_schedules",
    "checkins",
    "habit_pauses",
    "shortcut_tokens",
    "audit_events",
)
NEW_TABLES = ("instance_secrets", "push_subscriptions", "habit_reminders")


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
    """All 0.6.0 columns of the 0.6.0 tables, so columns added later do not affect the comparison."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in table_columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        result[table] = connection.execute(
            f"SELECT {', '.join(original)} FROM {table_source(connection, table)} ORDER BY 1, 2"
        ).fetchall()
    return result


class UpgradeFromV060Test(unittest.TestCase):
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
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def test_fixture_is_at_schema_0005_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0005",))
        connection.close()
        self.assertEqual(len(self.before["habits"]), 4)
        self.assertEqual(len(self.before["habit_pauses"]), 2)
        self.assertEqual(len(self.before["checkins"]), 5)

    def test_upgrade_keeps_data_and_adds_empty_tables(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        # Every 0.6.0 row and column must be untouched
        self.assertEqual(snapshot(connection), self.before)
        for table in NEW_TABLES:
            self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone(), (0,))
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_reminders_and_subscriptions_follow_their_owners(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("INSERT INTO habit_reminders (habit_id, time) VALUES (1, '07:30:00.000000')")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO habit_reminders (habit_id, time) VALUES (1, '07:30:00.000000')")
        subscription = (
            "INSERT INTO push_subscriptions (user_id, session_id, endpoint, p256dh, auth) VALUES (?, ?, ?, 'k', 'a')"
        )
        connection.execute(subscription, (1, 1, "https://fcm.googleapis.com/fcm/send/a"))
        connection.execute(subscription, (2, 2, "https://fcm.googleapis.com/fcm/send/b"))
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(subscription, (2, None, "https://fcm.googleapis.com/fcm/send/a"))
        # An expired session goes away; the device keeps its reminders
        connection.execute("DELETE FROM user_sessions WHERE id = 1")
        self.assertEqual(
            connection.execute("SELECT session_id FROM push_subscriptions WHERE user_id = 1").fetchone(), (None,)
        )
        connection.execute("DELETE FROM habits WHERE id = 1")
        self.assertEqual(connection.execute("SELECT count(*) FROM habit_reminders").fetchone(), (0,))
        connection.execute("DELETE FROM users WHERE id = 2")
        self.assertEqual(connection.execute("SELECT user_id FROM push_subscriptions").fetchall(), [(1,)])
        connection.close()

    def test_downgrade_and_upgrade_again_keep_data(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("INSERT INTO habit_reminders (habit_id, time) VALUES (1, '07:30:00.000000')")
        connection.execute("INSERT INTO instance_secrets (name, value) VALUES ('vapid_private_key', 'x')")
        connection.commit()
        connection.close()
        alembic(self.path, "downgrade", "0005")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
