"""Upgrade a real pomale 0.9.0 database (fixtures/v0.9.0.sql): shortcut keys become API tokens."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic, table_columns, table_source

FIXTURE = Path(__file__).with_name("fixtures") / "v0.9.0.sql"
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


def _original_columns() -> dict[str, set[str]]:
    connection = sqlite3.connect(":memory:")
    connection.executescript(FIXTURE.read_text(encoding="utf-8"))
    columns = {table: set(table_columns(connection, table)) for table in DATA_TABLES}
    connection.close()
    return columns


ORIGINAL_COLUMNS = _original_columns()


def snapshot(connection: sqlite3.Connection) -> dict[str, list[tuple]]:
    """All 0.9.0 columns of the 0.9.0 tables; shortcut keys are read back from api_tokens after 0008."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in table_columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        query = f"SELECT {', '.join(original)} FROM {table_source(connection, table)} ORDER BY 1, 2"
        result[table] = connection.execute(query).fetchall()
    return result


class UpgradeFromV090Test(unittest.TestCase):
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

    def test_fixture_is_at_schema_0007_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0007",))
        connection.close()
        self.assertEqual(len(self.before["shortcut_tokens"]), 3)

    def test_shortcut_keys_become_checkin_tokens_for_their_habit(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        tokens = connection.execute(
            "SELECT id, user_id, scopes, expires_at, revoked_at IS NOT NULL FROM api_tokens ORDER BY id"
        ).fetchall()
        # Owners come from the habit: habit 3 belongs to sam (2)
        self.assertEqual(tokens, [(1, 1, "checkin", None, 0), (2, 2, "checkin", None, 0), (5, 1, "checkin", None, 1)])
        self.assertNotIn(
            "shortcut_tokens",
            [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")],
        )
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_tokens_follow_their_owner_and_habits(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO api_tokens (user_id, label, token_hash, scopes) VALUES (1, 'x', ?, 'read')", ("b" * 64,)
            )
        connection.execute("DELETE FROM habits WHERE id = 1")
        self.assertEqual(connection.execute("SELECT token_id FROM api_token_habits").fetchall(), [(2,)])
        connection.execute("DELETE FROM users WHERE id = 2")
        self.assertEqual(connection.execute("SELECT id FROM api_tokens ORDER BY id").fetchall(), [(1,), (5,)])
        connection.close()

    def test_downgrade_keeps_what_a_shortcut_key_can_express(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        # Tokens a shortcut key cannot express are dropped on the way back
        connection.execute(
            "INSERT INTO api_tokens (id, user_id, label, token_hash, scopes) VALUES (9, 1, 'r', ?, 'read')", ("f" * 64,)
        )
        connection.execute("INSERT INTO api_token_habits VALUES (9, 1)")
        connection.execute(
            "INSERT INTO api_tokens (id, user_id, label, token_hash, scopes) VALUES (10, 1, 'all', ?, 'checkin')",
            ("9" * 64,),
        )
        connection.commit()
        connection.close()
        alembic(self.path, "downgrade", "0007")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
