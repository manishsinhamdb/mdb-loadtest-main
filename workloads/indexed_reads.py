"""indexed_reads — point queries on the INDEXED user_id field.

Expected FTDC signal: high opcounters.query with query_targeting_ratio ≈ 1
(docs scanned ≈ docs returned, because the index resolves the predicate).
"""
from __future__ import annotations

import random
import threading
import time

import config

from .base import Workload, throttle


class IndexedReads(Workload):
    key = "indexed_reads"
    label = "Indexed reads (targeted queries)"

    @staticmethod
    def default_params() -> dict:
        return {"threads": 4, "target_ops_per_sec": 0}  # 0 = unthrottled per thread

    def worker_loop(self, client, db, params, counter, stop: threading.Event):
        coll = db[config.COLL_LARGE]
        target = float(params.get("target_ops_per_sec", 0)) / max(1, int(params.get("threads", 1)))
        rng = random.Random()
        start = time.time()
        local = 0
        # Estimate the user_id range from seeded data.
        approx = coll.estimated_document_count() or 1
        hi = max(1, approx // 10)
        while not stop.is_set():
            uid = rng.randint(1, hi)
            _ = coll.find_one({"user_id": uid})
            counter.inc()
            local += 1
            throttle(target, local, start)
