"""unindexed_scans — queries on the UNINDEXED random_tag field.

Expected FTDC signal: query_targeting_ratio ↑ (scanned >> returned) and
metrics.queryExecutor.scanned ↑ (objs_scanned_ps), because each query forces a
collection scan.
"""
from __future__ import annotations

import random
import threading
import time

import config

from .base import Workload, throttle


class UnindexedScans(Workload):
    key = "unindexed_scans"
    label = "Unindexed collection scans"

    @staticmethod
    def default_params() -> dict:
        return {"threads": 2, "target_ops_per_sec": 0, "limit": 20}

    def worker_loop(self, client, db, params, counter, stop: threading.Event):
        coll = db[config.COLL_LARGE]
        target = float(params.get("target_ops_per_sec", 0)) / max(1, int(params.get("threads", 1)))
        limit = int(params.get("limit", 20))
        rng = random.Random()
        start = time.time()
        local = 0
        while not stop.is_set():
            tag = rng.randint(1, config.TAG_CARDINALITY)
            # random_tag is intentionally NOT indexed -> full collection scan.
            cursor = coll.find({"random_tag": tag}).limit(limit)
            _ = list(cursor)
            counter.inc()
            local += 1
            throttle(target, local, start)
