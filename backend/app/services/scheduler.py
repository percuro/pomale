"""The reminder loop: wakes up shortly after every full minute and sends what is due.

Runs inside the single app process (see "Limits" in docs/configuration.md); two instances on the
same database would not send twice (last_sent_on), but nothing coordinates them either.
"""

import asyncio
import contextlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import get_push_contact
from app.services.background import ThreadRuns
from app.services.reminder_service import ReminderService
from app.services.webpush.keys import ensure_vapid_keys
from app.services.webpush.sender import PushSender
from app.services.webpush.vapid import Vapid

# Seconds after the full minute, so a reminder at 07:30 is evaluated at 07:30:02
OFFSET_SECONDS = 2

logger = logging.getLogger(__name__)


def seconds_until_next_run(now: datetime) -> float:
    return 60 - now.second - now.microsecond / 1_000_000 + OFFSET_SECONDS


class ReminderScheduler:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        sender: PushSender | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.session_factory = session_factory
        self.clock = clock
        self._sender = sender
        self._task: asyncio.Task | None = None
        self._runs = ThreadRuns("reminder")

    def _make_sender(self) -> PushSender:
        db = self.session_factory()
        try:
            return PushSender(Vapid(ensure_vapid_keys(db), get_push_contact()))
        finally:
            db.close()

    def start(self) -> None:
        if self._sender is None:
            self._sender = self._make_sender()
        self._task = asyncio.create_task(self._loop(), name="reminders")
        logger.info("Reminders are on")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        # The sender is still in use by a run that is busy sending
        await self._runs.wait()
        if self._sender is not None:
            self._sender.close()

    def tick(self) -> int:
        assert self._sender is not None
        return ReminderService(self.session_factory, self._sender).run_due(self.clock())

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(seconds_until_next_run(self.clock()))
            try:
                sent = await self._runs.run(self.tick)
                if sent:
                    logger.info("Sent %d reminder notification(s)", sent)
            except Exception:
                # One bad minute (e.g. database locked) must not end the loop
                logger.exception("Reminder run failed")
