"""Upgrade a real pomale 0.3.0 database (fixtures/v0.3.0.sql) to the current schema."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic, table_columns, table_source

FIXTURE = Path(__file__).with_name("fixtures") / "v0.3.0.sql"
DATA_TABLES = ("users", "user_sessions", "habits", "habit_schedules", "checkins", "shortcut_tokens")


def snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    """All original columns of the 0.3.0 tables, so new columns do not affect the comparison."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in table_columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        result[table] = connection.execute(
            f"SELECT {', '.join(original)} FROM {table_source(connection, table)} ORDER BY 1, 2"
        ).fetchall()
    return result


def _columns_from_fixture() -> dict[str, set[str]]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(FIXTURE.read_text(encoding="utf-8"))
    columns = {table: {row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')} for table in DATA_TABLES}
    connection.close()
    return columns


ORIGINAL_COLUMNS = _columns_from_fixture()


class UpgradeFromV030Test(unittest.TestCase):
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

    def test_fixture_is_at_schema_0002_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0002",))
        connection.close()
        self.assertEqual(len(self.before["users"]), 2)
        self.assertEqual(len(self.before["checkins"]), 4)

    def test_upgrade_keeps_data_and_makes_existing_accounts_admins(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        rows = connection.execute(
            "SELECT username, role, display_name, timezone, locale, is_active FROM users ORDER BY id"
        ).fetchall()
        self.assertEqual(rows, [("alex", "admin", None, None, None, 1), ("sam", "admin", None, None, None, 0)])
        self.assertEqual(connection.execute("SELECT count(*) FROM invitations").fetchone(), (0,))
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_new_accounts_default_to_role_user(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("INSERT INTO users (username, password_hash, is_active) VALUES ('new', 'x', 1)")
        self.assertEqual(connection.execute("SELECT role FROM users WHERE username = 'new'").fetchone(), ("user",))
        connection.close()

    def test_downgrade_and_upgrade_again(self):
        alembic(self.path, "upgrade", "head")
        alembic(self.path, "downgrade", "0002")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
