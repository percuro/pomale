"""Upgrade a real pomale 0.10.0 database (fixtures/v0.10.0.sql), with API keys, to the current schema.

0.10.0 is at schema 0008. As long as that is head, the test checks that nothing is lost and that the
fixture stays loadable; the first migration after it gets its checks here.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic, table_columns

FIXTURE = Path(__file__).with_name("fixtures") / "v0.10.0.sql"
DATA_TABLES = (
    "users",
    "user_sessions",
    "oidc_identities",
    "habit_groups",
    "habits",
    "habit_schedules",
    "checkins",
    "habit_pauses",
    "api_tokens",
    "api_token_habits",
    "audit_events",
    "instance_secrets",
    "push_subscriptions",
    "habit_reminders",
)


def _original_columns() -> dict[str, set[str]]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(FIXTURE.read_text(encoding="utf-8"))
    columns = {table: set(table_columns(connection, table)) for table in DATA_TABLES}
    connection.close()
    return columns


ORIGINAL_COLUMNS = _original_columns()


def snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    """All 0.10.0 columns of the 0.10.0 tables, so new columns do not affect the comparison."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in table_columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        query = f'SELECT {", ".join(original)} FROM "{table}" ORDER BY 1, 2'
        result[table] = connection.execute(query).fetchall()
    return result


class UpgradeFromV0100Test(unittest.TestCase):
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

    def test_fixture_is_at_schema_0008_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0008",))
        connection.close()
        self.assertEqual(len(self.before["api_tokens"]), 5)
        self.assertEqual(len(self.before["api_token_habits"]), 5)

    def test_upgrade_keeps_everything(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_downgrade_to_0008_and_upgrade_again(self):
        alembic(self.path, "upgrade", "head")
        alembic(self.path, "downgrade", "0008")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
