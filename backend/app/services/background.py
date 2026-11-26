"""Blocking work of the background loops (reminders, backups), run in a thread.

Cancelling a task does not stop a thread, so on shutdown the loops wait for a run that is
still busy (at most SHUTDOWN_GRACE_SECONDS) instead of leaving it behind half done.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import TypeVar

SHUTDOWN_GRACE_SECONDS = 10.0

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ThreadRuns:
    def __init__(self, name: str):
        self.name = name
        self._current: asyncio.Future | None = None

    async def run(self, work: Callable[[], T]) -> T:
        current = asyncio.ensure_future(asyncio.to_thread(work))
        # Fetch a late result so that a run outliving its loop does not log "exception never retrieved"
        current.add_done_callback(lambda done: done.cancelled() or done.exception())
        self._current = current
        # Shielded: cancelling the loop must not abandon the thread's result while it still runs
        return await asyncio.shield(current)

    async def wait(self, timeout: float = SHUTDOWN_GRACE_SECONDS) -> None:
        current = self._current
        if current is None or current.done():
            return
        logger.info("Waiting for the running %s run to finish", self.name)
        done, _ = await asyncio.wait({current}, timeout=timeout)
        if not done:
            logger.warning("Stopped while a %s run was still busy", self.name)
