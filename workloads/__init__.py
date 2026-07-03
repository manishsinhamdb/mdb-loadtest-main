"""Workload registry. Each workload class is one selectable item in the UI."""
from __future__ import annotations

from .aggregation_pipelines import AggregationPipelines
from .base import Workload, WorkloadResult
from .connection_storm import ConnectionStorm
from .indexed_reads import IndexedReads
from .inmemory_sorts import InMemorySorts
from .mixed_blend import MixedBlend
from .unindexed_scans import UnindexedScans
from .update_contention import UpdateContention
from .write_bursts import WriteBursts

# Order here = display order in the UI (matches the brief's catalog numbering).
_REGISTRY: dict[str, Workload] = {}
for cls in (
    ConnectionStorm,
    IndexedReads,
    UnindexedScans,
    InMemorySorts,
    AggregationPipelines,
    WriteBursts,
    UpdateContention,
    MixedBlend,
):
    _REGISTRY[cls.key] = cls()


def get_workload(key: str) -> Workload:
    if key not in _REGISTRY:
        raise KeyError(f"unknown workload: {key}")
    return _REGISTRY[key]


def all_workloads() -> dict[str, Workload]:
    return dict(_REGISTRY)


def catalog() -> list[dict]:
    """UI-facing catalog: key, label, default params."""
    return [
        {"key": k, "label": w.label, "default_params": w.default_params()}
        for k, w in _REGISTRY.items()
    ]


__all__ = ["Workload", "WorkloadResult", "get_workload", "all_workloads", "catalog"]
