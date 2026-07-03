"""Workload plugin base + shared helpers.

Each workload runs in its own thread pool so its intensity is independently
dialable. Every workload reports ops-issued, achieved ops/sec and errors to the
manifest. pymongo is synchronous; the GIL is released during network I/O, so
threads give real concurrency for DB-bound work.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from tz import dual, now_utc


class Counter:
    """Thread-safe ops/error counter."""

    def __init__(self):
        self._lock = threading.Lock()
        self.ops = 0
        self.errors = 0

    def inc(self, n: int = 1):
        with self._lock:
            self.ops += n

    def err(self, n: int = 1):
        with self._lock:
            self.errors += n

    def snapshot(self) -> tuple[int, int]:
        with self._lock:
            return self.ops, self.errors


@dataclass
class WorkloadResult:
    name: str
    params: dict
    started: dict = field(default_factory=dual)
    ended: dict | None = None
    ops_issued: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    achieved_ops_per_sec: float = 0.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "params": self.params,
            "started": self.started,
            "ended": self.ended,
            "ops_issued": self.ops_issued,
            "errors": self.errors,
            "duration_seconds": round(self.duration_seconds, 3),
            "achieved_ops_per_sec": round(self.achieved_ops_per_sec, 2),
            "extra": self.extra,
        }


class Workload:
    """Base class. Subclasses implement `worker_loop` (one thread's loop) OR
    override `run` entirely (e.g. connection_storm holds connections instead of
    issuing ops in a tight loop)."""

    key: str = "base"
    label: str = "Base workload"

    @staticmethod
    def default_params() -> dict:
        return {}

    def worker_loop(self, client, db, params, counter: Counter, stop: threading.Event):
        raise NotImplementedError

    def run(self, client, db_name, params, duration_seconds, stop_event, log) -> WorkloadResult:
        """Default driver: spawn `threads` workers, run for the duration."""
        params = {**self.default_params(), **(params or {})}
        threads_n = int(params.get("threads", 1))
        counter = Counter()
        db = client[db_name]
        log.info(f"workload '{self.key}': starting {threads_n} thread(s) params={params}")
        start = time.time()
        started = dual(now_utc())

        workers: list[threading.Thread] = []
        for _ in range(threads_n):
            t = threading.Thread(
                target=self._guarded_loop,
                args=(client, db, params, counter, stop_event, log),
                daemon=True,
            )
            t.start()
            workers.append(t)

        # Let the run controller manage timing; we just wait for stop.
        stop_event.wait(duration_seconds)
        stop_event.set()
        for t in workers:
            t.join(timeout=10)

        elapsed = time.time() - start
        ops, errs = counter.snapshot()
        res = WorkloadResult(
            name=self.key,
            params=params,
            started=started,
            ended=dual(now_utc()),
            ops_issued=ops,
            errors=errs,
            duration_seconds=elapsed,
            achieved_ops_per_sec=(ops / elapsed if elapsed > 0 else 0.0),
        )
        log.info(f"workload '{self.key}': done ops={ops} errors={errs} "
                 f"achieved={res.achieved_ops_per_sec:.1f} ops/s over {elapsed:.1f}s")
        return res

    def _guarded_loop(self, client, db, params, counter, stop, log):
        try:
            self.worker_loop(client, db, params, counter, stop)
        except Exception as exc:  # noqa: BLE001
            counter.err()
            log.error(f"workload '{self.key}': worker crashed: {exc}")


def throttle(target_ops_per_sec: float | None, ops_done: int, start_time: float):
    """Sleep just enough to hold a per-thread ops/sec target. No-op if None/<=0."""
    if not target_ops_per_sec or target_ops_per_sec <= 0:
        return
    expected = ops_done / target_ops_per_sec
    actual = time.time() - start_time
    if expected > actual:
        time.sleep(expected - actual)
