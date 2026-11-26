"""Run Alembic programmatically against a given SQLite file (no alembic.ini logging setup)."""

import os
from pathlib import Path
from unittest import mock

from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic(path: Path, action: str, revision: str) -> None:
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    with mock.patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{path}"}):
        getattr(command, action)(config, revision)


# Migration 0008 moved the shortcut keys into api_tokens with the same ids; the upgrade tests of
# older releases still compare them in their old shape
SHORTCUT_TOKEN_COLUMNS = ("id", "habit_id", "label", "token_hash", "created_at", "last_used_at", "revoked_at")
MOVED_SHORTCUT_TOKENS = (
    "(SELECT t.id AS id, h.habit_id AS habit_id, t.label AS label, t.token_hash AS token_hash, "
    "t.created_at AS created_at, t.last_used_at AS last_used_at, t.revoked_at AS revoked_at "
    "FROM api_tokens t JOIN api_token_habits h ON h.token_id = t.id)"
)


def _has_table(connection, table: str) -> bool:
    query = "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?"
    return connection.execute(query, (table,)).fetchone() is not None


def table_columns(connection, table: str) -> list[str]:
    """The columns of a table; for shortcut_tokens after 0008, those of its old shape."""
    if table == "shortcut_tokens" and not _has_table(connection, table):
        return list(SHORTCUT_TOKEN_COLUMNS)
    return [row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')]


def table_source(connection, table: str) -> str:
    """What to select from: the table, or for shortcut_tokens after 0008 the moved rows."""
    if table == "shortcut_tokens" and not _has_table(connection, table):
        return MOVED_SHORTCUT_TOKENS
    return f'"{table}"'
