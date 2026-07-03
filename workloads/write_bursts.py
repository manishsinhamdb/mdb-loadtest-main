"""write_bursts — batched inserts of sized documents.

Expected FTDC signal: opcounters.insert ↑, disk write IOPS ↑, WiredTiger cache
dirty-bytes % ↑, checkpoint activity ↑. Each "op" counted is one insert_many
batch; ops_issued * batch_size ≈ documents written.
"""
from __future__ import annotations

import os
import threading
import time

import config

from .base import Workload, throttle


class WriteBursts(Workload):
    key = "write_bursts"
    label = "Write bursts (batched inserts)"

    @staticmethod
    def default_params() -> dict:
        return {"threads": 2, "batch_size": 500, "doc_kb": 1, "target_batches_per_sec": 0}

    def worker_loop(self, client, db, params, counter, stop: threading.Event):
        coll = db[config.COLL_APPEND]
        batch_size = int(params.get("batch_size", 500))
        doc_kb = int(params.get("doc_kb", 1))
        target = float(params.get("target_batches_per_sec", 0)) / max(1, int(params.get("threads", 1)))
        filler = "x" * (doc_kb * 1024)
        start = time.time()
        local = 0
        seq = 0
        while not stop.is_set():
            docs = [{"burst": True, "seq": seq + j, "payload": filler,
                     "ts": time.time()} for j in range(batch_size)]
            seq += batch_size
            coll.insert_many(docs, ordered=False)
            counter.inc()  # one batch issued
            local += 1
            throttle(target, local, start)
