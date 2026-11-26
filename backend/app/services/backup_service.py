"""Built-in backups: a compressed SQL dump of the whole database in BACKUP_DIR, once a day.

The dump comes from a consistent snapshot (SQLite backup API), also while the app writes. Files are
named pomale-YYYYMMDD-HHMM.sql.gz (UTC) and deleted after BACKUP_KEEP_DAYS; the newest one is
always kept. Other files in the directory are never touched. Restore with
`python -m app.cli.restore_sql --from <file>`.

The backups lie on the same volume as the database: they help against mistakes and a broken
database file, not against a lost disk. Copy them somewhere else as well.
"""

import gzip
import logging
import os
import re
import sqlite3
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TextIO

from app.config import get_database_url

BACKUP_NAME = re.compile(r"^pomale-(\d{8}-\d{4})\.sql\.gz$")

logger = logging.getLogger(__name__)
# A scheduled and a manual backup never run at the same time
_lock = threading.Lock()


@dataclass(frozen=True)
class BackupFile:
    name: str
    path: Path
    size: int
    created_at: datetime  # UTC, from the name


@dataclass
class BackupState:
    """What the last attempt did; kept in memory for the admin page."""

    last_error: str | None = None
    last_error_at: datetime | None = None


state = BackupState()


def database_path() -> str:
    url = get_database_url()
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise SystemExit("Only SQLite databases are supported")
    return url[len(prefix) :]


def snapshot(path: str | None = None) -> sqlite3.Connection:
    """A consistent in-memory copy of the database, also while the app is writing."""
    source = sqlite3.connect(f"file:{path or database_path()}?mode=ro", uri=True, timeout=30)
    copy = sqlite3.connect(":memory:")
    try:
        source.backup(copy)
    finally:
        source.close()
    return copy


def dump_lines(connection: sqlite3.Connection) -> Iterator[str]:
    for line in connection.iterdump():
        yield line + "\n"


def write_dump(out: TextIO, path: str | None = None) -> None:
    copy = snapshot(path)
    try:
        for line in dump_lines(copy):
            out.write(line)
    finally:
        copy.close()


def list_backups(directory: Path) -> list[BackupFile]:
    """Backups in the directory, newest first."""
    if not directory.is_dir():
        return []
    files = []
    for entry in directory.iterdir():
        match = BACKUP_NAME.match(entry.name)
        if match is None or not entry.is_file():
            continue
        created = datetime.strptime(match.group(1), "%Y%m%d-%H%M").replace(tzinfo=UTC)
        files.append(BackupFile(entry.name, entry, entry.stat().st_size, created))
    return sorted(files, key=lambda f: f.created_at, reverse=True)


def prune(directory: Path, now: datetime, keep_days: int) -> list[str]:
    """Delete backups older than keep_days; the newest one stays whatever its age."""
    removed = []
    cutoff = now.astimezone(UTC) - timedelta(days=keep_days)
    for backup in list_backups(directory)[1:]:
        if backup.created_at < cutoff:
            backup.path.unlink(missing_ok=True)
            removed.append(backup.name)
    return removed


def create_backup(directory: Path, now: datetime, keep_days: int, path: str | None = None) -> BackupFile:
    """Write a backup now, then prune old ones. Raises on failure (and records it in `state`)."""
    with _lock:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            name = f"pomale-{now.astimezone(UTC):%Y%m%d-%H%M}.sql.gz"
            target = directory / name
            partial = directory / f".{name}.partial"
            with gzip.open(partial, "wt", encoding="utf-8", compresslevel=6) as out:
                write_dump(out, path)
            os.replace(partial, target)
            removed = prune(directory, now, keep_days)
        except Exception as exc:
            state.last_error = f"{type(exc).__name__}: {exc}"[:300]
            state.last_error_at = now.astimezone(UTC)
            logger.exception("Backup failed")
            raise
        state.last_error = None
        state.last_error_at = None
    backup = BackupFile(name, target, target.stat().st_size, now.astimezone(UTC).replace(second=0, microsecond=0))
    logger.info(
        "Backup written: %s (%d bytes)%s", name, backup.size, f", removed {len(removed)} old" if removed else ""
    )
    return backup
