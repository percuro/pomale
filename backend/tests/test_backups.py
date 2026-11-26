"""Built-in backups: files, pruning, restore from a file, the daily schedule and the admin API."""

import asyncio
import gzip
import io
import os
import sqlite3
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from time import sleep
from unittest import mock
from zoneinfo import ZoneInfo

from app import config
from app.cli import restore_sql
from app.models.audit_event import AuditEvent
from app.services import backup_service
from app.services.backup_scheduler import BackupScheduler, next_backup_at
from tests.support import ApiTestEnvironment

NOW = datetime(2026, 11, 24, 2, 0, tzinfo=UTC)
VIENNA = ZoneInfo("Europe/Vienna")


class BackupFilesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.db_path = str(self.root / "habits.db")
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE checkins (habit_id INTEGER, local_date TEXT, done BOOLEAN)")
        db.executemany("INSERT INTO checkins VALUES (?, ?, ?)", [(1, "2026-11-24", 1), (1, "2026-11-23", 0)])
        db.commit()
        self.addCleanup(db.close)  # stays open like the running app
        self.backups = self.root / "backups"
        backup_service.state.last_error = None

    def test_backup_and_restore_from_the_file(self):
        backup = backup_service.create_backup(self.backups, NOW, 14, self.db_path)
        self.assertEqual(backup.name, "pomale-20261124-0200.sql.gz")
        with gzip.open(backup.path, "rt", encoding="utf-8") as dump:
            self.assertIn("CREATE TABLE checkins", dump.read())
        target = str(self.root / "restored.db")
        with mock.patch("sys.argv", ["restore", "--from", str(backup.path), "--target", target]):
            with redirect_stderr(io.StringIO()):
                restore_sql.main()
        restored = sqlite3.connect(target)
        self.assertEqual(restored.execute("SELECT count(*) FROM checkins").fetchone(), (2,))
        restored.close()
        self.assertEqual([b.name for b in backup_service.list_backups(self.backups)], [backup.name])
        self.assertEqual(os.listdir(self.backups), [backup.name])

    def test_old_backups_are_pruned_but_never_the_newest_or_other_files(self):
        self.backups.mkdir()
        for name in ("pomale-20261101-0300.sql.gz", "pomale-20261110-0300.sql.gz", "pomale-20261111-0300.sql.gz"):
            (self.backups / name).write_bytes(b"x")
        (self.backups / "my-notes.txt").write_text("keep me")
        removed = backup_service.prune(self.backups, NOW, 14)
        self.assertEqual(removed, ["pomale-20261101-0300.sql.gz"])
        # Only old backups left: the newest one stays
        self.assertEqual(
            backup_service.prune(self.backups, NOW + timedelta(days=100), 14), ["pomale-20261110-0300.sql.gz"]
        )
        self.assertEqual(sorted(os.listdir(self.backups)), ["my-notes.txt", "pomale-20261111-0300.sql.gz"])

    def test_failure_leaves_no_file_and_is_remembered(self):
        with (
            mock.patch("app.services.backup_service.write_dump", side_effect=OSError("disk full")),
            self.assertLogs("app.services.backup_service", "ERROR"),
            self.assertRaises(OSError),
        ):
            backup_service.create_backup(self.backups, NOW, 14, self.db_path)
        self.assertEqual(backup_service.list_backups(self.backups), [])
        self.assertEqual(os.listdir(self.backups), [], "no half-written file stays behind")
        self.assertIn("disk full", backup_service.state.last_error)
        backup_service.create_backup(self.backups, NOW, 14, self.db_path)
        self.assertIsNone(backup_service.state.last_error)


class ScheduleTest(unittest.TestCase):
    def test_next_backup(self):
        at = time(3, 0)
        # 02:00 UTC = 03:00 in Vienna: due now, so tomorrow
        self.assertEqual(next_backup_at(NOW, at, VIENNA, NOW, False), datetime(2026, 11, 25, 2, 0, tzinfo=UTC))
        earlier = NOW - timedelta(hours=1)
        self.assertEqual(next_backup_at(earlier, at, VIENNA, NOW, False), NOW)
        # On start without a recent backup: one minute later
        self.assertEqual(next_backup_at(NOW, at, VIENNA, None, True), NOW + timedelta(minutes=1))
        self.assertEqual(next_backup_at(NOW, at, VIENNA, NOW - timedelta(hours=26), True), NOW + timedelta(minutes=1))
        self.assertEqual(next_backup_at(earlier, at, VIENNA, NOW - timedelta(hours=20), True), NOW)

    def test_clock_change(self):
        # 29 Mar 2026: 02:30 does not exist in Vienna and becomes 03:30 CEST (01:30 UTC)
        night = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)
        self.assertEqual(
            next_backup_at(night, time(2, 30), VIENNA, night, False), datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
        )

    def test_loop_backs_up_and_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            scheduler = BackupScheduler(Path(directory), 14, time(3, 0), VIENNA, clock=lambda: NOW)
            calls = []

            async def scenario():
                with (
                    mock.patch("app.services.backup_scheduler.next_backup_at", return_value=NOW - timedelta(seconds=1)),
                    mock.patch.object(scheduler, "run_once", side_effect=lambda: calls.append(1)),
                    mock.patch("app.services.backup_scheduler.asyncio.sleep", new=_no_sleep),
                ):
                    scheduler.start()
                    while len(calls) < 2:
                        await _real_sleep(0.01)
                    await scheduler.stop()

            asyncio.run(scenario())
            self.assertGreaterEqual(len(calls), 2)

    def test_loop_survives_an_unreadable_directory(self):
        scheduler = BackupScheduler(Path("/nonexistent"), 14, time(3, 0), VIENNA, clock=lambda: NOW)
        calls = []

        async def scenario():
            with (
                mock.patch("app.services.backup_scheduler.list_backups", side_effect=PermissionError("denied")),
                mock.patch.object(scheduler, "run_once", side_effect=lambda: calls.append(1)),
                mock.patch("app.services.backup_scheduler.asyncio.sleep", new=_no_sleep),
                self.assertLogs("app.services.backup_scheduler", "ERROR"),
            ):
                scheduler.start()
                while len(calls) < 2:
                    await _real_sleep(0.01)
                await scheduler.stop()

        asyncio.run(scenario())
        self.assertGreaterEqual(len(calls), 2)

    def test_stop_waits_for_a_running_backup(self):
        scheduler = BackupScheduler(Path("/nonexistent"), 14, time(3, 0), VIENNA, clock=lambda: NOW)
        started, finished = threading.Event(), []

        def slow_backup():
            started.set()
            sleep(0.3)
            finished.append(1)

        async def scenario():
            with (
                mock.patch("app.services.backup_scheduler.list_backups", return_value=[]),
                mock.patch("app.services.backup_scheduler.next_backup_at", return_value=NOW),
                mock.patch.object(scheduler, "run_once", side_effect=slow_backup),
                mock.patch("app.services.backup_scheduler.asyncio.sleep", new=_no_sleep),
            ):
                scheduler.start()
                await asyncio.to_thread(started.wait, 5)
                await scheduler.stop()
                self.assertEqual(finished, [1])

        asyncio.run(scenario())


_real_sleep = asyncio.sleep


async def _no_sleep(_seconds):
    await _real_sleep(0)


class ConfigTest(unittest.TestCase):
    def test_settings(self):
        with mock.patch.dict(os.environ, {"BACKUP_TIME": "", "BACKUP_KEEP_DAYS": "", "BACKUP_DIR": ""}):
            with mock.patch.dict(os.environ, {"DATABASE_URL": "sqlite:////data/habits.db"}):
                self.assertEqual(config.get_backup_dir(), Path("/data/backups"))
            self.assertEqual((config.get_backup_time(), config.get_backup_keep_days()), (time(3, 0), 14))
        for name, value in (
            ("BACKUP_TIME", "3am"),
            ("BACKUP_TIME", "25:00"),
            ("BACKUP_KEEP_DAYS", "0"),
            ("BACKUP_KEEP_DAYS", "x"),
        ):
            with mock.patch.dict(os.environ, {name: value}), self.assertRaises(config.ConfigError):
                config.get_backup_time() if name == "BACKUP_TIME" else config.get_backup_keep_days()


class AdminBackupApiTest(unittest.TestCase):
    def setUp(self):
        self.env = ApiTestEnvironment()
        self.addCleanup(self.env.close)
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        db_path = Path(self.dir.name) / "habits.db"
        sqlite3.connect(db_path).execute("CREATE TABLE t (x)").connection.close()
        patcher = mock.patch.dict(
            os.environ, {"DATABASE_URL": f"sqlite:///{db_path}", "BACKUP_DIR": str(Path(self.dir.name) / "b")}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env.create_user("admin", role="admin")
        self.env.create_user("sam")
        self.admin = self.env.client("admin")
        backup_service.state.last_error = None

    def test_status_and_backup_now(self):
        status = self.admin.get("/v1/admin/backups").json()
        self.assertEqual(
            (status["enabled"], status["count"], status["latest"], status["keep_days"]), (False, 0, None, 14)
        )
        created = self.admin.post("/v1/admin/backups")
        self.assertEqual(created.status_code, 201, created.text)
        status = self.admin.get("/v1/admin/backups").json()
        self.assertEqual((status["count"], status["latest"]["name"]), (1, created.json()["name"]))
        db = self.env.SessionLocal()
        try:
            self.assertEqual(db.query(AuditEvent).filter_by(event="backup.created").count(), 1)
        finally:
            db.close()

    def test_failure_and_access(self):
        with (
            mock.patch("app.services.backup_service.write_dump", side_effect=OSError("disk full")),
            self.assertLogs("app.services.backup_service", "ERROR"),
        ):
            failed = self.admin.post("/v1/admin/backups")
        self.assertEqual((failed.status_code, failed.json()["code"]), (500, "backup.failed"))
        self.assertIn("disk full", self.admin.get("/v1/admin/backups").json()["last_error"])
        sam = self.env.client("sam")
        self.assertEqual(sam.get("/v1/admin/backups").status_code, 403)
        self.assertEqual(sam.post("/v1/admin/backups").status_code, 403)


if __name__ == "__main__":
    unittest.main()
