"""The daily backup: sleeps until BACKUP_TIME (DEFAULT_TIMEZONE) and writes one, inside the app process.

If the newest backup is older than a day when the app starts (it was down at backup time, or
it is a new instance), one is written a minute after the start.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from app.services.background import ThreadRuns
from app.services.backup_service import BackupFile, create_backup, list_backups
from app.services.reminder_service import reminder_moment

STARTUP_DELAY = timedelta(minutes=1)
MISSING_AFTER = timedelta(hours=25)

logger = logging.getLogger(__name__)


def next_backup_at(now: datetime, at: time, zone: ZoneInfo, newest: datetime | None, starting: bool) -> datetime:
    """The UTC instant of the next backup. Clock changes are handled like reminder times."""
    now = now.astimezone(UTC)
    if starting and (newest is None or now - newest > MISSING_AFTER):
        return now + STARTUP_DELAY
    day = now.astimezone(zone).date()
    moment = reminder_moment(day, at, zone)
    if moment <= now:
        moment = reminder_moment(day + timedelta(days=1), at, zone)
    return moment


class BackupScheduler:
    def __init__(
        self,
        directory: Path,
        keep_days: int,
        at: time,
        zone: ZoneInfo,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.directory = directory
        self.keep_days = keep_days
        self.at = at
        self.zone = zone
        self.clock = clock
        self._task: asyncio.Task | None = None
        self._runs = ThreadRuns("backup")

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="backups")
        logger.info("Daily backups at %s (%s) into %s", self.at.strftime("%H:%M"), self.zone.key, self.directory)

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        await self._runs.wait()

    def run_once(self) -> None:
        try:
            create_backup(self.directory, self.clock(), self.keep_days)
        except Exception:  # noqa: BLE001 - logged and kept for the admin page; tomorrow is another try
            pass

    async def _loop(self) -> None:
        starting = True
        while True:
            now = self.clock()
            backups = await self._runs.run(self._list)
            when = next_backup_at(now, self.at, self.zone, backups[0].created_at if backups else None, starting)
            starting = False
            # One second late on purpose: never wake just before the time and back up twice
            await asyncio.sleep(max(0.0, (when - now).total_seconds()) + 1)
            await self._runs.run(self.run_once)

    def _list(self) -> list[BackupFile]:
        try:
            return list_backups(self.directory)
        except Exception:  # noqa: BLE001 - e.g. an unreadable directory: plan as if there were none, never end the loop
            logger.exception("Could not list the backups in %s", self.directory)
            return []
