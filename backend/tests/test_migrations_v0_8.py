"""Upgrade a real pomale 0.8.0 database (fixtures/v0.8.0.sql) to the current schema."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic

FIXTURE = Path(__file__).with_name("fixtures") / "v0.8.0.sql"
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
    "instance_secrets",
    "push_subscriptions",
    "habit_reminders",
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
    """All 0.8.0 columns of the 0.8.0 tables, so new columns do not affect the comparison."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in _columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        result[table] = connection.execute(f'SELECT {", ".join(original)} FROM "{table}" ORDER BY 1, 2').fetchall()
    return result


class UpgradeFromV080Test(unittest.TestCase):
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

    def test_fixture_is_at_schema_0006_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0006",))
        connection.close()
        self.assertEqual(len(self.before["users"]), 2)
        self.assertEqual(len(self.before["habit_reminders"]), 3)
        self.assertEqual(len(self.before["push_subscriptions"]), 1)

    def test_upgrade_keeps_data_and_days_end_at_midnight(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        self.assertEqual(
            connection.execute("SELECT id, day_end_hour FROM users ORDER BY id").fetchall(), [(1, 0), (2, 0)]
        )
        # New accounts get midnight from the database default as well
        connection.execute("INSERT INTO users (username, password_hash, is_active) VALUES ('new', NULL, 1)")
        self.assertEqual(connection.execute("SELECT day_end_hour FROM users WHERE username = 'new'").fetchone(), (0,))
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_downgrade_and_upgrade_again_keep_data(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("UPDATE users SET day_end_hour = 2 WHERE id = 1")
        connection.commit()
        connection.close()
        alembic(self.path, "downgrade", "0006")
        connection = self.connect()
        self.assertNotIn("day_end_hour", _columns(connection, "users"))
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
