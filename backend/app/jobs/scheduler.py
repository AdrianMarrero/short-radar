"""APScheduler setup. Runs the daily job once per day inside the FastAPI process.

Note: on Render free tier the web service sleeps after inactivity. For reliable
daily execution we ALSO ship a `cron` block in render.yaml that hits the
endpoint /api/jobs/run-daily-batch on a schedule. The in-process scheduler is
useful in dev and for paid plans.
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logging import get_logger
from app.jobs.daily import run_daily_job

log = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def _scheduled_run() -> None:
    try:
        run_daily_job(triggered_by="scheduler")
    except Exception as e:
        log.exception("scheduled job failed: %s", e)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    # 22:30 UTC ~ después del cierre US, suficiente margen
    _scheduler.add_job(
        _scheduled_run,
        CronTrigger(hour=22, minute=30),
        id="daily_pipeline",
        replace_existing=True,
    )
    _scheduler.start()
    log.info("scheduler started (daily 22:30 UTC)")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
