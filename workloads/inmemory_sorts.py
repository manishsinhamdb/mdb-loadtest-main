"""inmemory_sorts — sort on an unindexed field, forcing in-memory sort stages.

Expected FTDC signal: metrics.operation.scanAndOrder ↑ (scan_and_order_ps),
because the server must scan-and-order rather than walk an index in sort order.
"""
from __future__ import annotations

import threading
import time

import config

from .base import Workload, throttle


class InMemorySorts(Workload):
    key = "inmemory_sorts"
    label = "In-memory sorts (scanAndOrder)"

    @staticmethod
    def default_params() -> dict:
        return {"threads": 2, "target_ops_per_sec": 0, "limit": 50}

    def worker_loop(self, client, db, params, counter, stop: threading.Event):
        coll = db[config.COLL_LARGE]
        target = float(params.get("target_ops_per_sec", 0)) / max(1, int(params.get("threads", 1)))
        limit = int(params.get("limit", 50))
        start = time.time()
        local = 0
        while not stop.is_set():
            # Sort on 'value' (unindexed) -> scanAndOrder; small limit keeps it
            # from spilling to disk but still moves the in-memory sort metric.
            cursor = coll.find({}, {"value": 1}).sort("value", 1).limit(limit)
            _ = list(cursor)
            counter.inc()
            local += 1
            throttle(target, local, start)
