"""Regenerate v0.9.0.sql: a database at schema 0007 (pomale 0.9.0) with sample data.

Run from backend/: ../.venv/bin/python -m tests.fixtures.make_v0_9_0
The dump is committed so the upgrade test always starts from the same old database.
"""

import sqlite3
import tempfile
from pathlib import Path

from tests.migration_support import alembic

TARGET = Path(__file__).with_name("v0.9.0.sql")
# Any valid scrypt hash; the test does not log in
PASSWORD_HASH = "scrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA==$ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGk="

SAMPLE_DATA = f"""
INSERT INTO users (id, username, password_hash, is_active, role, display_name, timezone, locale, last_seen_at,
                   created_at, day_end_hour) VALUES
  (1, 'alex', '{PASSWORD_HASH}', 1, 'admin', 'Alex', 'Pacific/Kiritimati', 'de', '2026-11-24 20:00:00',
   '2026-11-01 08:00:00', 2),
  (2, 'sam', NULL, 1, 'user', NULL, NULL, 'en', NULL, '2026-11-02 09:30:00', 0);
INSERT INTO user_sessions (id, user_id, token_hash, expires_at, created_at, last_seen_at, user_agent, auth_method,
                           authenticated_at) VALUES
  (1, 1, '{"a" * 64}', '2026-12-24 08:00:00', '2026-11-24 08:00:00', '2026-11-24 20:00:00', 'Mozilla/5.0 (iPhone)',
   'password', '2026-11-24 08:00:00'),
  (2, 2, '{"d" * 64}', '2026-12-24 09:00:00', '2026-11-24 09:00:00', NULL, NULL, 'oidc', '2026-11-24 09:00:00');
INSERT INTO oidc_identities (id, user_id, issuer, subject, email, preferred_username, created_at, last_login_at)
  VALUES (1, 2, 'https://auth.example.org', 'sub-sam', 'sam@example.org', 'sam', '2026-11-02 09:30:00',
          '2026-11-24 09:00:00');
INSERT INTO habit_groups (id, user_id, name, sort_order) VALUES
  (1, 1, 'Morgens', 1);
INSERT INTO habits (id, user_id, name, cue, sort_order, archived_on, unit, color, group_id, created_at) VALUES
  (1, 1, 'Lesen', 'nach dem Frühstück', 1, NULL, NULL, 'teal', 1, '2026-11-01 08:05:00'),
  (2, 1, 'Dehnen', NULL, 2, '2026-11-20', NULL, NULL, NULL, '2026-11-01 08:06:00'),
  (3, 2, 'Running', NULL, 1, NULL, NULL, 'blue', NULL, '2026-11-02 09:40:00'),
  (4, 1, 'Wasser', NULL, 3, NULL, 'Gläser', NULL, 1, '2026-11-25 08:00:00');
INSERT INTO habit_schedules (id, habit_id, valid_from, weekdays, goal_type, target) VALUES
  (1, 1, '2026-11-01', 127, 'days', NULL),
  (2, 1, '2026-11-16', 31, 'days', NULL),
  (3, 2, '2026-11-01', 127, 'days', NULL),
  (4, 2, '2026-11-21', 0, 'days', NULL),
  (5, 3, '2026-11-02', 21, 'days', NULL),
  (6, 3, '2026-11-23', 127, 'weekly_count', 3),
  (7, 4, '2026-11-25', 127, 'quantity', 8);
INSERT INTO checkins (habit_id, local_date, done, value, note, version, last_op_id, updated_at) VALUES
  (1, '2026-11-23', 1, NULL, 'Kapitel 3', 1, 'op-1', '2026-11-23 19:00:00'),
  (1, '2026-11-24', 0, NULL, NULL, 2, 'op-2', '2026-11-24 19:00:00'),
  (2, '2026-11-19', 1, NULL, NULL, 1, NULL, '2026-11-19 18:00:00'),
  (3, '2026-11-23', 1, NULL, NULL, 1, NULL, '2026-11-23 18:00:00'),
  (4, '2026-11-25', 1, 5, NULL, 3, 'op-3', '2026-11-25 12:00:00');
INSERT INTO habit_pauses (id, user_id, habit_id, start_on, end_on, reason, created_at) VALUES
  (1, 1, NULL, '2026-11-10', '2026-11-12', 'krank', '2026-11-12 08:00:00'),
  (2, 2, 3, '2026-12-20', '2026-12-31', NULL, '2026-11-24 09:00:00');
INSERT INTO shortcut_tokens (id, habit_id, label, token_hash, created_at, last_used_at, revoked_at) VALUES
  (1, 1, 'iPhone', '{"b" * 64}', '2026-11-10 10:00:00', '2026-11-24 19:00:00', NULL),
  (2, 3, 'Watch', '{"c" * 64}', '2026-11-11 10:00:00', NULL, NULL),
  (5, 1, 'old phone', '{"e" * 64}', '2026-11-05 10:00:00', '2026-11-06 07:00:00', '2026-11-09 12:00:00');
INSERT INTO audit_events (id, created_at, event, actor_user_id, actor_username, target_user_id, target_username,
                          ip_prefix, details) VALUES
  (1, '2026-11-24 08:00:00', 'auth.login', 1, 'alex', NULL, NULL, NULL, '{{"method": "password"}}');
INSERT INTO instance_secrets (name, value, created_at) VALUES
  ('vapid_private_key', 'not-a-real-key', '2026-11-25 14:00:00');
INSERT INTO push_subscriptions (id, user_id, session_id, endpoint, p256dh, auth, user_agent, created_at,
                                last_success_at, last_error) VALUES
  (1, 1, 1, 'https://fcm.googleapis.com/fcm/send/alex', 'key', 'auth', 'Mozilla/5.0 (iPhone)',
   '2026-11-25 14:00:00', '2026-11-25 19:30:02', NULL);
INSERT INTO habit_reminders (id, habit_id, time, last_sent_on) VALUES
  (1, 1, '07:30:00.000000', '2026-11-25'),
  (2, 1, '20:00:00.000000', NULL),
  (3, 4, '00:30:00.000000', NULL);
"""


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "v0.9.0.db"
        alembic(path, "upgrade", "0007")
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
