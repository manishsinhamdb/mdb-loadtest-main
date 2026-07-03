"""Ground-truth manifest — the validation oracle.

Per run we record: run_id; start/end in IST AND UTC; random seed; which
workloads ran with every parameter; per-workload ops issued / achieved ops/sec /
errors; target version / topology / edition; REDACTED connection target (host +
db, NO credentials); serverStatus opcounter deltas; and an 'expected FTDC
signals' section mapping active workloads to the metrics they should move.
"""
from __future__ import annotations

import json
import os

import config
from tz import dual, stamp_for_path

# Workload -> FTDC metrics it is expected to move. Mirrors EXPECTED_SIGNALS.md.
EXPECTED_SIGNALS = {
    "connection_storm": ["connections.current", "globalLock.activeClients", "network.numRequests"],
    "indexed_reads": ["opcounters.query", "metrics.queryExecutor.scanned (~= returned)",
                       "query_targeting_ratio ≈ 1"],
    "unindexed_scans": ["query_targeting_ratio ↑ (scanned >> returned)",
                        "metrics.queryExecutor.scanned ↑ (objs_scanned_ps)"],
    "inmemory_sorts": ["metrics.operation.scanAndOrder ↑ (scan_and_order_ps)"],
    "aggregation_pipelines": ["CPU ↑", "metrics.queryExecutor.scanned ↑",
                              "wiredTiger.cache bytes read into cache ↑"],
    "write_bursts": ["opcounters.insert ↑", "disk write IOPS ↑",
                     "wiredTiger.cache tracked dirty bytes % ↑", "checkpoint activity ↑"],
    "update_contention": ["opcounters.update ↑", "metrics.operation.writeConflicts ↑ (write_conflicts_ps)",
                          "wiredTiger write ticket utilization ↑"],
    "mixed_blend": ["composite — see the individual workloads selected in the blend"],
}


def expected_signals_for(active_workloads: list[str]) -> dict:
    return {w: EXPECTED_SIGNALS.get(w, ["(no mapping)"]) for w in active_workloads}


class Manifest:
    """Accumulates run facts, then serialises to JSON under the run folder."""

    def __init__(self, run_id: str, output_dir: str, *, mode: str = "manual"):
        self.run_id = run_id
        self.output_dir = os.path.abspath(output_dir)
        self.run_dir = os.path.join(self.output_dir, f"run_{stamp_for_path()}_{run_id}")
        self.data: dict = {
            "schema": "loadgen.manifest/v1",
            "app_version": config.APP_VERSION,
            "run_id": run_id,
            "mode": mode,                 # manual | scheduled
            "created": dual(),
            "started": None,
            "ended": None,
            "random_seed": None,
            "driver_host": "OMEN",
            "target": None,               # redacted host+db, version, topology, edition
            "clock_skew": None,
            "seeder": None,
            "workloads": [],              # per-workload result dicts
            "opcounters": {"before": None, "after": None, "delta": None},
            "expected_ftdc_signals": {},
            "errors": [],
        }

    # --- builders ---------------------------------------------------------
    def set_started(self, dt=None):
        self.data["started"] = dual(dt)

    def set_ended(self, dt=None):
        self.data["ended"] = dual(dt)

    def set_seed(self, seed):
        self.data["random_seed"] = seed

    def set_target(self, target: dict):
        self.data["target"] = target

    def set_clock_skew(self, skew: dict):
        self.data["clock_skew"] = skew

    def set_seeder(self, seeder: dict):
        self.data["seeder"] = seeder

    def add_workload_result(self, result: dict):
        self.data["workloads"].append(result)

    def set_opcounters(self, before: dict | None, after: dict | None):
        self.data["opcounters"]["before"] = before
        self.data["opcounters"]["after"] = after
        if before and after:
            delta = {}
            for k in set(before) | set(after):
                try:
                    delta[k] = int(after.get(k, 0)) - int(before.get(k, 0))
                except (TypeError, ValueError):
                    pass
            self.data["opcounters"]["delta"] = delta

    def finalize_expected_signals(self):
        active = [w["name"] for w in self.data["workloads"]]
        self.data["expected_ftdc_signals"] = expected_signals_for(active)

    def add_error(self, msg: str):
        self.data["errors"].append({"at": dual(), "msg": msg})

    # --- output -----------------------------------------------------------
    def ensure_run_dir(self) -> str:
        os.makedirs(self.run_dir, exist_ok=True)
        return self.run_dir

    @property
    def manifest_path(self) -> str:
        return os.path.join(self.run_dir, "manifest.json")

    @property
    def log_path(self) -> str:
        return os.path.join(self.run_dir, "run.log")

    def write(self) -> str:
        self.ensure_run_dir()
        self.finalize_expected_signals()
        with open(self.manifest_path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, default=str)
        return self.manifest_path
