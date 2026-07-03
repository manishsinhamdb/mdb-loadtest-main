"""mixed_blend — a weighted/random blend of the other workload classes.

Either supply explicit per-type weights, or supply a random seed and let the
blend pick weights deterministically (logged to the manifest so the run is
reproducible). Runs each chosen sub-workload concurrently for the duration and
aggregates their results.

Expected FTDC signal: composite — the union of the signals of whatever
sub-workloads end up in the blend.
"""
from __future__ import annotations

import random
import threading

from tz import dual, now_utc

from .base import Workload, WorkloadResult


# Sub-workloads eligible for blending (connection_storm excluded: it manages
# its own connections rather than issuing an op loop, so weighting it by thread
# count is meaningless).
BLENDABLE = ["indexed_reads", "unindexed_scans", "inmemory_sorts",
             "aggregation_pipelines", "write_bursts", "update_contention"]


class MixedBlend(Workload):
    key = "mixed_blend"
    label = "Mixed blend"

    @staticmethod
    def default_params() -> dict:
        return {"total_threads": 12, "weights": None, "seed": None}

    def run(self, client, db_name, params, duration_seconds, stop_event, log) -> WorkloadResult:
        from . import get_workload  # late import to avoid cycle

        params = {**self.default_params(), **(params or {})}
        total_threads = int(params.get("total_threads", 12))
        seed = params.get("seed")
        rng = random.Random(seed)

        weights = params.get("weights")
        if not weights:
            # Random but seeded: pick a weight in [1,5] for each blendable type.
            weights = {w: rng.randint(1, 5) for w in BLENDABLE}
        # Normalise weights -> integer thread allocation summing to total_threads.
        active = {k: v for k, v in weights.items() if v and k in BLENDABLE}
        total_w = sum(active.values()) or 1
        alloc = {k: max(1, round(total_threads * v / total_w)) for k, v in active.items()}
        log.info(f"mixed_blend: seed={seed} weights={active} -> thread alloc={alloc}")

        started = dual(now_utc())
        results: dict[str, WorkloadResult] = {}
        threads: list[threading.Thread] = []

        def _run_sub(key, nthreads):
            wl = get_workload(key)
            sub_params = {**wl.default_params(), "threads": nthreads}
            results[key] = wl.run(client, db_name, sub_params, duration_seconds, stop_event, log)

        for key, nthreads in alloc.items():
            t = threading.Thread(target=_run_sub, args=(key, nthreads), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=duration_seconds + 30)

        ops = sum(r.ops_issued for r in results.values())
        errs = sum(r.errors for r in results.values())
        dur = max((r.duration_seconds for r in results.values()), default=0.0)
        res = WorkloadResult(
            name=self.key,
            params={**params, "weights": active, "thread_alloc": alloc},
            started=started,
            ended=dual(now_utc()),
            ops_issued=ops,
            errors=errs,
            duration_seconds=dur,
            achieved_ops_per_sec=(ops / dur if dur > 0 else 0.0),
            extra={"sub_results": {k: r.to_dict() for k, r in results.items()}},
        )
        log.info(f"mixed_blend: done total_ops={ops} errors={errs}")
        return res
