"""APScheduler-backed scheduling with a persistent SQLite jobstore.

The UI schedules a recurring daily window (default 10:00-12:00 IST) over a date
range (default 7 days). Each scheduled day fires one run with a RANDOMIZED,
seeded blend (the seed is logged in that day's manifest, so the blend is
reproducible). The SQLite jobstore means schedules survive an app restart.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

import config
from logbus import BUS
from tz import dual, now_utc

_IST = ZoneInfo(config.OPERATOR_TZ)
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {"default": SQLAlchemyJobStore(url=f"sqlite:///{config.SCHEDULER_DB_PATH}")}
        executors = {"default": ThreadPoolExecutor(4)}
        # Run jobs on IST so the cron window matches the operator's intent.
        _scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, timezone=_IST)
        _scheduler.start()
        BUS.info(f"scheduler started (jobstore={config.SCHEDULER_DB_PATH}, tz=IST)")
    return _scheduler


# NOTE: APScheduler must be able to import the job target by reference, so the
# scheduled callable is a module-level function, not a closure.
def _scheduled_run(cfg: dict, base_seed: int):
    """Job target. Derives a per-day seed so each day's blend differs yet is
    reproducible from base_seed + the date."""
    from runner import execute_run  # local import to avoid heavy import at load

    today = now_utc().strftime("%Y%m%d")
    day_seed = (base_seed + int(today)) % (2 ** 31)
    run_cfg = dict(cfg)
    run_cfg["seed"] = day_seed
    # Force a mixed_blend driven by the day seed unless explicit workloads given.
    if not run_cfg.get("workloads"):
        run_cfg["workloads"] = {"mixed_blend": {"seed": day_seed, "total_threads":
                                                run_cfg.get("blend_threads", 12)}}
    BUS.info(f"scheduled job firing: date={today} day_seed={day_seed}")
    execute_run(run_cfg, mode="scheduled")


def add_daily_window(
    cfg: dict,
    *,
    start_ist: str = config.DEFAULT_WINDOW_START_IST,
    end_ist: str | None = None,   # informational; duration drives the actual stop
    days: int = config.DEFAULT_SCHEDULE_DAYS,
    base_seed: int = 1234,
    job_id: str | None = None,
) -> dict:
    """Schedule a daily run at start_ist for `days` days from today (IST)."""
    sched = get_scheduler()
    hour, minute = (int(x) for x in start_ist.split(":"))
    start_date = now_utc().astimezone(_IST)
    end_date = start_date + timedelta(days=days)
    job_id = job_id or f"loadgen_daily_{start_date.strftime('%Y%m%dT%H%M%S')}"

    trigger = CronTrigger(hour=hour, minute=minute, start_date=start_date,
                          end_date=end_date, timezone=_IST)
    sched.add_job(
        _scheduled_run, trigger=trigger, args=[cfg, base_seed],
        id=job_id, replace_existing=True, misfire_grace_time=3600,
        coalesce=True, max_instances=1,
        name=f"loadgen daily {start_ist} IST x{days}d",
    )
    BUS.info(f"scheduled daily window job '{job_id}' at {start_ist} IST for {days} days "
             f"(end {end_date.date()} IST)")
    return {
        "job_id": job_id,
        "start_ist": start_ist,
        "end_ist": end_ist,
        "days": days,
        "base_seed": base_seed,
        "window_start": dual(start_date),
        "window_end": dual(end_date),
    }


def list_jobs() -> list[dict]:
    sched = get_scheduler()
    out = []
    for job in sched.get_jobs():
        nrt = job.next_run_time
        out.append({
            "job_id": job.id,
            "name": job.name,
            "next_run_time": dual(nrt) if nrt else None,
            "trigger": str(job.trigger),
        })
    return out


def remove_job(job_id: str) -> bool:
    sched = get_scheduler()
    try:
        sched.remove_job(job_id)
        BUS.info(f"removed scheduled job '{job_id}'")
        return True
    except Exception as exc:  # noqa: BLE001
        BUS.warn(f"could not remove job '{job_id}': {exc}")
        return False


def remove_all_jobs() -> int:
    sched = get_scheduler()
    jobs = sched.get_jobs()
    for job in jobs:
        sched.remove_job(job.id)
    BUS.info(f"removed all {len(jobs)} scheduled job(s)")
    return len(jobs)
