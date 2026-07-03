"""aggregation_pipelines — run grouping/unwinding pipelines.

Expected FTDC signal: CPU ↑, metrics.queryExecutor.scanned ↑, WiredTiger cache
bytes-read-into-cache ↑. Complexity scales the pipeline depth.
"""
from __future__ import annotations

import threading
import time

import config

from .base import Workload, throttle


def _pipeline(complexity: int) -> list:
    """Build a pipeline whose work grows with `complexity` (1..3+)."""
    pipe: list = [{"$match": {"amount": {"$gt": 100}}}]
    if complexity >= 1:
        pipe += [{"$group": {"_id": "$category", "total": {"$sum": "$amount"},
                             "n": {"$sum": 1}, "avg": {"$avg": "$amount"}}}]
    if complexity >= 2:
        pipe = [{"$match": {"amount": {"$gt": 50}}},
                {"$unwind": "$items"},
                {"$group": {"_id": "$category", "qty": {"$sum": "$items.qty"},
                            "total": {"$sum": "$amount"}}},
                {"$sort": {"total": -1}}]
    if complexity >= 3:
        pipe += [{"$unwind": "$_id"} if False else {"$limit": 100},
                 {"$project": {"category": "$_id", "qty": 1, "total": 1, "_id": 0}}]
    return pipe


class AggregationPipelines(Workload):
    key = "aggregation_pipelines"
    label = "Aggregation pipelines"

    @staticmethod
    def default_params() -> dict:
        return {"threads": 2, "complexity": 2, "target_ops_per_sec": 0}

    def worker_loop(self, client, db, params, counter, stop: threading.Event):
        coll = db[config.COLL_AGG]
        complexity = int(params.get("complexity", 2))
        target = float(params.get("target_ops_per_sec", 0)) / max(1, int(params.get("threads", 1)))
        pipe = _pipeline(complexity)
        start = time.time()
        local = 0
        while not stop.is_set():
            _ = list(coll.aggregate(pipe, allowDiskUse=True))
            counter.inc()
            local += 1
            throttle(target, local, start)
