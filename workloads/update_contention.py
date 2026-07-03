"""update_contention — many threads updating a small hot set of documents.

Expected FTDC signal: opcounters.update ↑, metrics.operation.writeConflicts ↑
(write_conflicts_ps), WiredTiger write-ticket utilization ↑. Fewer hot docs +
more threads = more contention.
"""
from __future__ import annotations

import random
import threading
import time

import config

from .base import Workload, throttle


class UpdateContention(Workload):
    key = "update_contention"
    label = "Update contention (hot docs)"

    @staticmethod
    def default_params() -> dict:
        return {"threads": 8, "hot_doc_count": 20, "target_ops_per_sec": 0}

    def worker_loop(self, client, db, params, counter, stop: threading.Event):
        coll = db[config.COLL_HOT]
        hot = int(params.get("hot_doc_count", 20))
        target = float(params.get("target_ops_per_sec", 0)) / max(1, int(params.get("threads", 1)))
        rng = random.Random()
        start = time.time()
        local = 0
        while not stop.is_set():
            doc_id = rng.randint(0, max(0, hot - 1))
            coll.update_one({"_id": doc_id}, {"$inc": {"counter": 1},
                                              "$set": {"owner": threading.get_ident()}})
            counter.inc()
            local += 1
            throttle(target, local, start)
