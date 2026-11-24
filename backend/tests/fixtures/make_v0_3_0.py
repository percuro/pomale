"""Regenerate v0.3.0.sql: a database at schema 0002 (pomale 0.3.0) with sample data.

Run from backend/: ../.venv/bin/python -m tests.fixtures.make_v0_3_0
The dump is committed so the upgrade test always starts from the same old database.
"""

import sqlite3
import tempfile
from pathlib import Path

from tests.migration_support import alembic

TARGET = Path(__file__).with_name("v0.3.0.sql")
# Any valid scrypt hash; the test does not log in
PASSWORD_HASH = "scrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA==$ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGk="

SAMPLE_DATA = f"""
INSERT INTO users (id, username, password_hash, is_active, created_at) VALUES
  (1, 'alex', '{PASSWORD_HASH}', 1, '2026-11-01 08:00:00'),
  (2, 'sam', '{PASSWORD_HASH}', 0, '2026-11-02 09:30:00');
INSERT INTO user_sessions (id, user_id, token_hash, expires_at, created_at) VALUES
  (1, 1, '{"a" * 64}', '2026-12-24 08:00:00', '2026-11-24 08:00:00');
INSERT INTO habits (id, user_id, name, cue, sort_order, archived_on, created_at) VALUES
  (1, 1, 'Lesen', 'nach dem Frühstück', 1, NULL, '2026-11-01 08:05:00'),
  (2, 1, 'Laufen', NULL, 2, '2026-11-20', '2026-11-01 08:06:00'),
  (3, 2, 'Gitarre', NULL, 1, NULL, '2026-11-02 09:40:00');
INSERT INTO habit_schedules (id, habit_id, valid_from, weekdays) VALUES
  (1, 1, '2026-11-01', 127),
  (2, 2, '2026-11-01', 21),
  (3, 2, '2026-11-21', 0),
  (4, 3, '2026-11-02', 96);
INSERT INTO checkins (habit_id, local_date, done, version, last_op_id, updated_at) VALUES
  (1, '2026-11-23', 1, 1, 'op-1', '2026-11-23 19:00:00'),
  (1, '2026-11-24', 0, 2, 'op-2', '2026-11-24 07:00:00'),
  (2, '2026-11-18', 1, 1, NULL, '2026-11-18 06:30:00'),
  (3, '2026-11-22', 1, 1, NULL, '2026-11-22 18:00:00');
INSERT INTO shortcut_tokens (id, habit_id, label, token_hash, created_at, last_used_at, revoked_at) VALUES
  (1, 1, 'iPhone', '{"b" * 64}', '2026-11-10 10:00:00', '2026-11-23 19:00:00', NULL),
  (2, 1, 'old iPad', '{"c" * 64}', '2026-11-05 10:00:00', NULL, '2026-11-09 10:00:00');
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "v0.3.0.db"
        alembic(path, "upgrade", "0002")
        connection = sqlite3.connect(path)
        try:
            connection.executescript(SAMPLE_DATA)
            connection.commit()
            TARGET.write_text("\n".join(connection.iterdump()) + "\n", encoding="utf-8")
        finally:
            connection.close()
    print(f"Wrote {TARGET}")


if __name__ == "__main__":
    main()
