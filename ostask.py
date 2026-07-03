"""OS-scheduler dispatcher for the UI's "permanent" schedule.

Picks the right durable backend for the host:
  * Windows -> wintask.py   (Task Scheduler)
  * macOS   -> mactask.py   (launchd LaunchAgent)
  * Linux   -> not wired to the UI button; use the systemd timer (systemd/).

The UI calls these three functions; they delegate to the platform module.
"""
from __future__ import annotations

import platform

_SYS = platform.system()

if _SYS == "Windows":
    import wintask as _impl
    BACKEND = "Windows Task Scheduler"
elif _SYS == "Darwin":
    import mactask as _impl
    BACKEND = "macOS launchd"
else:
    _impl = None
    BACKEND = "unsupported"

_LINUX_MSG = (
    "Permanent scheduling from the UI is supported on Windows (Task Scheduler) and "
    "macOS (launchd). On Linux, install the systemd timer (systemd/loadgen.timer) "
    "or add a cron entry calling run_window.py — see README."
)


def backend_name() -> str:
    return BACKEND


def create_persistent_task(cfg: dict) -> dict:
    if _impl is None:
        return {"ok": False, "task_name": "loadgen-daily", "error": _LINUX_MSG}
    return _impl.create_persistent_task(cfg)


def list_persistent_tasks() -> dict:
    if _impl is None:
        return {"tasks": [], "note": _LINUX_MSG}
    return _impl.list_persistent_tasks()


def remove_persistent_task() -> dict:
    if _impl is None:
        return {"ok": False, "detail": _LINUX_MSG}
    return _impl.remove_persistent_task()
