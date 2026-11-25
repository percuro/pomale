"""Regenerate v0.4.0.sql: a database at schema 0003 (pomale 0.4.0) with sample data.

Run from backend/: ../.venv/bin/python -m tests.fixtures.make_v0_4_0
The dump is committed so the upgrade test always starts from the same old database.
"""

import sqlite3
import tempfile
from pathlib import Path

from tests.migration_support import alembic

TARGET = Path(__file__).with_name("v0.4.0.sql")
# Any valid scrypt hash; the test does not log in
PASSWORD_HASH = "scrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA==$ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGk="

SAMPLE_DATA = f"""
INSERT INTO users (id, username, password_hash, is_active, role, display_name, timezone, locale, last_seen_at,
                   created_at) VALUES
  (1, 'alex', '{PASSWORD_HASH}', 1, 'admin', 'Alex', 'Pacific/Kiritimati', 'de', '2026-11-24 20:00:00',
   '2026-11-01 08:00:00'),
  (2, 'sam', '{PASSWORD_HASH}', 1, 'user', NULL, NULL, NULL, NULL, '2026-11-02 09:30:00'),
  (3, 'kim', '{PASSWORD_HASH}', 0, 'user', 'Kim', NULL, 'en', NULL, '2026-11-03 10:00:00');
INSERT INTO user_sessions (id, user_id, token_hash, expires_at, created_at, last_seen_at, user_agent) VALUES
  (1, 1, '{"a" * 64}', '2026-12-24 08:00:00', '2026-11-24 08:00:00', '2026-11-24 20:00:00', 'Mozilla/5.0 (iPhone)'),
  (2, 2, '{"d" * 64}', '2026-12-24 09:00:00', '2026-11-24 09:00:00', NULL, NULL);
INSERT INTO habits (id, user_id, name, cue, sort_order, archived_on, created_at) VALUES
  (1, 1, 'Lesen', 'nach dem Frühstück', 1, NULL, '2026-11-01 08:05:00'),
  (2, 2, 'Laufen', NULL, 1, NULL, '2026-11-02 09:40:00');
INSERT INTO habit_schedules (id, habit_id, valid_from, weekdays) VALUES
  (1, 1, '2026-11-01', 127),
  (2, 2, '2026-11-02', 21);
INSERT INTO checkins (habit_id, local_date, done, version, last_op_id, updated_at) VALUES
  (1, '2026-11-24', 1, 1, 'op-1', '2026-11-24 19:00:00'),
  (2, '2026-11-23', 1, 1, NULL, '2026-11-23 18:00:00');
INSERT INTO shortcut_tokens (id, habit_id, label, token_hash, created_at, last_used_at, revoked_at) VALUES
  (1, 1, 'iPhone', '{"b" * 64}', '2026-11-10 10:00:00', '2026-11-24 19:00:00', NULL);
INSERT INTO invitations (id, token_hash, purpose, role, target_user_id, note, created_by_user_id, expires_at,
                         used_at, used_by_user_id, created_at) VALUES
  (1, '{"e" * 64}', 'signup', 'user', NULL, 'for Sam', 1, '2026-11-09 09:00:00', '2026-11-02 09:30:00', 2,
   '2026-11-02 09:00:00'),
  (2, '{"f" * 64}', 'signup', 'admin', NULL, NULL, 1, '2026-12-01 09:00:00', NULL, NULL, '2026-11-24 09:00:00'),
  (3, '{"0" * 64}', 'password_reset', NULL, 2, NULL, 1, '2026-11-25 09:00:00', NULL, NULL, '2026-11-24 09:00:00');
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "v0.4.0.db"
        alembic(path, "upgrade", "0003")
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
