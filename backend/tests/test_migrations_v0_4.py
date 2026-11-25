"""Upgrade a real pomale 0.4.0 database (fixtures/v0.4.0.sql) to the current schema."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.migration_support import alembic

FIXTURE = Path(__file__).with_name("fixtures") / "v0.4.0.sql"
DATA_TABLES = (
    "users",
    "user_sessions",
    "habits",
    "habit_schedules",
    "checkins",
    "shortcut_tokens",
    "invitations",
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
    """All 0.4.0 columns of the 0.4.0 tables, so new columns do not affect the comparison."""
    result = {}
    for table in DATA_TABLES:
        original = [c for c in _columns(connection, table) if c in ORIGINAL_COLUMNS[table]]
        result[table] = connection.execute(f'SELECT {", ".join(original)} FROM "{table}" ORDER BY 1, 2').fetchall()
    return result


class UpgradeFromV040Test(unittest.TestCase):
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

    def test_fixture_is_at_schema_0003_with_data(self):
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT version_num FROM alembic_version").fetchone(), ("0003",))
        connection.close()
        self.assertEqual(len(self.before["users"]), 3)
        self.assertEqual(len(self.before["user_sessions"]), 2)
        self.assertEqual(len(self.before["invitations"]), 3)

    def test_upgrade_keeps_accounts_passwords_sessions_and_invitations(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        # Rebuilding users must not cascade into sessions, habits or invitations
        self.assertEqual(snapshot(connection), self.before)
        self.assertEqual(
            connection.execute("SELECT auth_method, authenticated_at FROM user_sessions ORDER BY id").fetchall(),
            [("password", None), ("password", None)],
        )
        for table in ("oidc_identities", "oidc_login_states", "audit_events"):
            self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone(), (0,))
        self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))
        connection.close()

    def test_accounts_without_password_are_allowed_after_upgrade(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("INSERT INTO users (username, password_hash, is_active) VALUES ('sso', NULL, 1)")
        connection.commit()
        self.assertEqual(connection.execute("SELECT role FROM users WHERE username = 'sso'").fetchone(), ("user",))
        connection.close()

    def test_issuer_and_subject_are_unique(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("INSERT INTO oidc_identities (user_id, issuer, subject) VALUES (1, 'https://idp', 'a')")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO oidc_identities (user_id, issuer, subject) VALUES (2, 'https://idp', 'a')")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO oidc_identities (user_id, issuer, subject) VALUES (1, 'https://idp', 'b')")
        connection.close()

    def test_downgrade_keeps_data_and_gives_oidc_accounts_an_unusable_password(self):
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        connection.execute("INSERT INTO users (id, username, password_hash, is_active) VALUES (9, 'sso', NULL, 1)")
        connection.commit()
        connection.close()
        alembic(self.path, "downgrade", "0003")
        connection = self.connect()
        self.assertEqual(connection.execute("SELECT password_hash FROM users WHERE id = 9").fetchone(), ("!",))
        connection.execute("DELETE FROM users WHERE id = 9")
        connection.commit()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()
        alembic(self.path, "upgrade", "head")
        connection = self.connect()
        self.assertEqual(snapshot(connection), self.before)
        connection.close()


if __name__ == "__main__":
    unittest.main()
