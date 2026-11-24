import io
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from app.cli import dump_sql, restore_sql


class BackupCliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.source = os.path.join(self.dir.name, "habits.db")
        db = sqlite3.connect(self.source)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE checkins (habit_id INTEGER, local_date TEXT, done BOOLEAN)")
        db.executemany("INSERT INTO checkins VALUES (?, ?, ?)", [(1, "2026-11-24", 1), (1, "2026-11-23", 0)])
        db.commit()
        self.open_connection = db  # stays open like the running app

    def tearDown(self):
        self.open_connection.close()
        self.dir.cleanup()

    def dump(self) -> str:
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"DATABASE_URL": f"sqlite:///{self.source}"}), redirect_stdout(out):
            dump_sql.main()
        return out.getvalue()

    def test_dump_and_restore_roundtrip(self):
        script = self.dump()
        self.assertIn("CREATE TABLE checkins", script)
        target = os.path.join(self.dir.name, "restored.db")
        with (
            mock.patch("sys.argv", ["restore", "--target", target]),
            mock.patch("sys.stdin", io.StringIO(script)),
            redirect_stderr(io.StringIO()),
        ):
            restore_sql.main()
        restored = sqlite3.connect(target)
        rows = restored.execute("SELECT * FROM checkins ORDER BY local_date").fetchall()
        restored.close()
        self.assertEqual(rows, [(1, "2026-11-23", 0), (1, "2026-11-24", 1)])

    def test_restore_never_overwrites(self):
        with (
            mock.patch("sys.argv", ["restore", "--target", self.source]),
            mock.patch("sys.stdin", io.StringIO(self.dump())),
        ):
            with self.assertRaises(SystemExit):
                restore_sql.main()


if __name__ == "__main__":
    unittest.main()
