"""Failure-notification hook (stub).

Logs prominently for now. TODO: wire a real channel (email / Slack / webhook).
Centralised so every preflight failure or run error routes through one place.
"""
from __future__ import annotations

from logbus import BUS


def notify_failure(subject: str, detail: str, *, run_id: str | None = None) -> None:
    banner = "!" * 60
    BUS.error(f"{banner}")
    BUS.error(f"FAILURE NOTIFICATION: {subject}" + (f" (run {run_id})" if run_id else ""))
    BUS.error(f"  detail: {detail}")
    BUS.error(f"{banner}")
    # TODO: dispatch to a real notification channel here, e.g.:
    #   requests.post(WEBHOOK_URL, json={"text": f"{subject}\n{detail}"})
