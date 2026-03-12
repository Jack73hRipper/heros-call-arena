"""
Scheduler — APScheduler-based turn tick system.

Manages per-match tick jobs that fire every TICK_RATE_SECONDS.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings


class SchedulerManager:
    """Wraps APScheduler for match tick management."""

    def __init__(self):
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            print("[Scheduler] Started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            print("[Scheduler] Shut down")

    def add_match_tick(self, match_id: str, tick_callback, tick_rate: float | None = None) -> None:
        """Schedule a recurring tick for a match."""
        rate = tick_rate or settings.TICK_RATE_SECONDS
        self._scheduler.add_job(
            tick_callback,
            "interval",
            seconds=rate,
            id=f"match_tick_{match_id}",
            args=[match_id],
            replace_existing=True,
        )
        print(f"[Scheduler] Tick added for match {match_id} (every {rate}s)")

    def remove_match_tick(self, match_id: str) -> None:
        """Remove a match's tick job."""
        job_id = f"match_tick_{match_id}"
        job = self._scheduler.get_job(job_id)
        if job:
            job.remove()
            print(f"[Scheduler] Tick removed for match {match_id}")

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._scheduler


scheduler_manager = SchedulerManager()
