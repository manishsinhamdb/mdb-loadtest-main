"""
Intent-Based Testing API endpoints for V2.

Provides:
- /api/intent/types - List all 8 intent types with metadata
- /api/intent/calculate - Calculate config from intent + intensity
- /api/metrics/catalog - 130+ metric catalog
- /api/metrics/generate-test - Generate test from selected metrics (metric-driven mode)
"""
from __future__ import annotations

import math
import psutil
from typing import Dict, List, Any

# Intent definitions with metric mappings
INTENT_DEFINITIONS = {
    "connection_stress": {
        "id": "connection_stress",
        "name": "Connection Stress",
        "description": "Test connection pool limits and concurrent connection handling",
        "primary_metrics": [
            "CONNECTIONS",
            "CONNECTIONS_AVAILABLE",
            "NETWORK_BYTES_IN",
            "NETWORK_BYTES_OUT",
            "NETWORK_NUM_REQUESTS"
        ],
        "secondary_metrics": [
            "OPCOUNTER_COMMAND",
            "SYSTEM_CPU_USER",
            "SYSTEM_MEMORY_AVAILABLE_MB"
        ],
        "workload_keys": ["query", "update"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.3, "load_pct": 25},
            "medium": {"threads_multiplier": 0.6, "load_pct": 60},
            "heavy": {"threads_multiplier": 0.9, "load_pct": 85},
            "extreme": {"threads_multiplier": 1.2, "load_pct": 95}
        }
    },
    "read_performance": {
        "id": "read_performance",
        "name": "Read Performance",
        "description": "Benchmark query throughput (indexed + unindexed reads)",
        "primary_metrics": [
            "OPCOUNTER_QUERY",
            "OPCOUNTER_GETMORE",
            "QUERY_EXECUTOR_SCANNED",
            "QUERY_EXECUTOR_SCANNED_OBJECTS",
            "QUERY_TARGETING_SCANNED_PER_RETURNED"
        ],
        "secondary_metrics": [
            "CACHE_BYTES_READ",
            "TICKETS_AVAILABLE_READS",
            "CURSORS_TOTAL_OPEN",
            "NETWORK_BYTES_OUT"
        ],
        "workload_keys": ["query", "query_large"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.4, "load_pct": 30},
            "medium": {"threads_multiplier": 0.7, "load_pct": 65},
            "heavy": {"threads_multiplier": 1.0, "load_pct": 90},
            "extreme": {"threads_multiplier": 1.3, "load_pct": 98}
        }
    },
    "write_throughput": {
        "id": "write_throughput",
        "name": "Write Throughput",
        "description": "Max out write capacity with batch inserts",
        "primary_metrics": [
            "OPCOUNTER_INSERT",
            "OPCOUNTER_UPDATE",
            "OPCOUNTER_DELETE",
            "DOCUMENT_METRICS_INSERTED",
            "DOCUMENT_METRICS_UPDATED"
        ],
        "secondary_metrics": [
            "CACHE_BYTES_WRITTEN",
            "CACHE_DIRTY_BYTES",
            "TICKETS_AVAILABLE_WRITES",
            "OPLOG_RATE_GB_PER_HOUR",
            "NETWORK_BYTES_IN"
        ],
        "workload_keys": ["insert", "update", "bulk_insert"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.3, "load_pct": 20},
            "medium": {"threads_multiplier": 0.6, "load_pct": 55},
            "heavy": {"threads_multiplier": 0.9, "load_pct": 80},
            "extreme": {"threads_multiplier": 1.1, "load_pct": 95}
        }
    },
    "aggregation_pipeline": {
        "id": "aggregation_pipeline",
        "name": "Aggregation Pipeline",
        "description": "Test complex pipelines (groupBy, unwind, sorting)",
        "primary_metrics": [
            "OPCOUNTER_COMMAND",
            "QUERY_EXECUTOR_SCANNED",
            "SYSTEM_CPU_USER",
            "SYSTEM_CPU_IOWAIT"
        ],
        "secondary_metrics": [
            "SYSTEM_MEMORY_USED_MB",
            "CACHE_BYTES_READ",
            "TICKETS_AVAILABLE_READS",
            "CURSORS_TOTAL_OPEN"
        ],
        "workload_keys": ["aggregate"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.2, "load_pct": 30},
            "medium": {"threads_multiplier": 0.5, "load_pct": 60},
            "heavy": {"threads_multiplier": 0.8, "load_pct": 85},
            "extreme": {"threads_multiplier": 1.0, "load_pct": 95}
        }
    },
    "concurrency_contention": {
        "id": "concurrency_contention",
        "name": "Concurrency Contention",
        "description": "Find lock contention limits on hot documents",
        "primary_metrics": [
            "GLOBAL_LOCK_CURRENT_QUEUE_READERS",
            "GLOBAL_LOCK_CURRENT_QUEUE_WRITERS",
            "TICKETS_AVAILABLE_READS",
            "TICKETS_AVAILABLE_WRITES"
        ],
        "secondary_metrics": [
            "OPCOUNTER_UPDATE",
            "OPCOUNTER_QUERY",
            "CONNECTIONS",
            "SYSTEM_CPU_USER"
        ],
        "workload_keys": ["hot_update", "hot_query"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.5, "load_pct": 35},
            "medium": {"threads_multiplier": 1.0, "load_pct": 70},
            "heavy": {"threads_multiplier": 1.5, "load_pct": 90},
            "extreme": {"threads_multiplier": 2.0, "load_pct": 98}
        }
    },
    "cache_pressure": {
        "id": "cache_pressure",
        "name": "Cache Pressure",
        "description": "Overflow WiredTiger cache to test disk I/O fallback",
        "primary_metrics": [
            "CACHE_BYTES_READ",
            "CACHE_BYTES_WRITTEN",
            "CACHE_DIRTY_BYTES",
            "CACHE_USED_BYTES",
            "SYSTEM_MEMORY_USED_MB"
        ],
        "secondary_metrics": [
            "SYSTEM_DISK_IOPS_READS",
            "SYSTEM_DISK_IOPS_WRITES",
            "SYSTEM_CPU_IOWAIT",
            "OPCOUNTER_QUERY"
        ],
        "workload_keys": ["query_large", "scan"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.4, "load_pct": 40},
            "medium": {"threads_multiplier": 0.7, "load_pct": 70},
            "heavy": {"threads_multiplier": 1.0, "load_pct": 90},
            "extreme": {"threads_multiplier": 1.2, "load_pct": 98}
        }
    },
    "mixed_production": {
        "id": "mixed_production",
        "name": "Mixed Production Simulation",
        "description": "Realistic blend: 80% reads, 15% writes, 5% aggregations",
        "primary_metrics": [
            "OPCOUNTER_QUERY",
            "OPCOUNTER_INSERT",
            "OPCOUNTER_UPDATE",
            "OPCOUNTER_COMMAND"
        ],
        "secondary_metrics": [
            "CONNECTIONS",
            "CACHE_BYTES_READ",
            "CACHE_BYTES_WRITTEN",
            "NETWORK_BYTES_IN",
            "NETWORK_BYTES_OUT",
            "SYSTEM_CPU_USER"
        ],
        "workload_keys": ["query", "insert", "update", "aggregate"],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.5, "load_pct": 30},
            "medium": {"threads_multiplier": 0.8, "load_pct": 60},
            "heavy": {"threads_multiplier": 1.1, "load_pct": 85},
            "extreme": {"threads_multiplier": 1.4, "load_pct": 95}
        }
    },
    "custom": {
        "id": "custom",
        "name": "Custom Configuration",
        "description": "Full manual control over all workload parameters",
        "primary_metrics": [],
        "secondary_metrics": [],
        "workload_keys": [],
        "intensity_scaling": {
            "light": {"threads_multiplier": 0.3, "load_pct": 25},
            "medium": {"threads_multiplier": 0.6, "load_pct": 50},
            "heavy": {"threads_multiplier": 1.0, "load_pct": 75},
            "extreme": {"threads_multiplier": 1.5, "load_pct": 95}
        }
    }
}


def get_intent_types() -> Dict[str, Any]:
    """Return all intent type definitions."""
    return {
        "intents": list(INTENT_DEFINITIONS.values())
    }


def calculate_from_intent(
    intent_id: str,
    intensity: str,
    duration: int,
    concurrency_multiplier: float,
    client_hardware: Dict[str, Any] | None = None,
    server_hardware: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Calculate workload configuration from intent parameters.

    Args:
        intent_id: One of 8 intent IDs
        intensity: light, medium, heavy, extreme
        duration: Test duration in seconds
        concurrency_multiplier: User's concurrency slider (1-50)
        client_hardware: {"cpu_cores": int, "ram_gb": float} or None (auto-detect)
        server_hardware: {"max_connections": int, "ram_gb": float, "vcpus": int} or None

    Returns:
        Configuration dict with calculated thread counts, workload weights, warnings
    """
    if intent_id not in INTENT_DEFINITIONS:
        raise ValueError(f"Unknown intent_id: {intent_id}")

    intent = INTENT_DEFINITIONS[intent_id]
    scaling = intent["intensity_scaling"].get(intensity, intent["intensity_scaling"]["medium"])

    # Auto-detect hardware if not provided
    if client_hardware is None:
        client_hardware = {
            "cpu_cores": psutil.cpu_count(logical=True),
            "ram_gb": psutil.virtual_memory().total / (1024 ** 3)
        }

    if server_hardware is None:
        server_hardware = {
            "max_connections": 1000,  # Conservative default
            "ram_gb": 16,
            "vcpus": 4
        }

    # Calculate thread count
    base_threads = max(2, int(client_hardware["cpu_cores"] * scaling["threads_multiplier"]))
    thread_count = int(base_threads * concurrency_multiplier / 10.0)  # Normalize concurrency slider
    thread_count = max(1, min(thread_count, server_hardware["max_connections"] - 10))

    # Calculate estimated ops/sec (rough heuristic)
    estimated_ops_per_sec = thread_count * 50  # Assume 50 ops/sec per thread avg

    # Generate warnings
    warnings = []
    if thread_count > client_hardware["cpu_cores"] * 2:
        warnings.append(f"Thread count ({thread_count}) exceeds 2x client CPU cores. May cause context switching overhead.")

    if thread_count > server_hardware["max_connections"] * 0.8:
        warnings.append(f"Using {int(thread_count / server_hardware['max_connections'] * 100)}% of max connections. Risk of exhaustion.")

    if scaling["load_pct"] >= 90:
        warnings.append(f"Extreme intensity ({scaling['load_pct']}% load). May cause server instability. Monitor closely.")

    return {
        "intent_id": intent_id,
        "intent_name": intent["name"],
        "intensity": intensity,
        "duration": duration,
        "thread_count": thread_count,
        "estimated_load_pct": scaling["load_pct"],
        "estimated_ops_per_sec": estimated_ops_per_sec,
        "workload_keys": intent["workload_keys"],
        "primary_metrics": intent["primary_metrics"],
        "secondary_metrics": intent["secondary_metrics"],
        "warnings": warnings,
        "hardware_used": {
            "client": client_hardware,
            "server": server_hardware
        }
    }


def generate_test_from_metrics(metric_names: List[str]) -> Dict[str, Any]:
    """
    Generate test configuration from user-selected metrics (metric-driven mode).

    Analyzes which workloads will spike the selected metrics and creates optimal config.

    Args:
        metric_names: List of metric names user wants to spike

    Returns:
        Configuration with recommended workloads and intensity
    """
    # Simplified: map metrics to intents
    # In production, this would use the metric_workload_map table
    metric_to_intent = {
        "OPCOUNTER_QUERY": "read_performance",
        "OPCOUNTER_INSERT": "write_throughput",
        "OPCOUNTER_UPDATE": "write_throughput",
        "CONNECTIONS": "connection_stress",
        "CACHE_BYTES_READ": "cache_pressure",
        "GLOBAL_LOCK_CURRENT_QUEUE_READERS": "concurrency_contention"
    }

    # Find best matching intents
    intent_scores = {}
    for metric in metric_names:
        for intent_id, intent_def in INTENT_DEFINITIONS.items():
            if metric in intent_def["primary_metrics"]:
                intent_scores[intent_id] = intent_scores.get(intent_id, 0) + 3
            elif metric in intent_def["secondary_metrics"]:
                intent_scores[intent_id] = intent_scores.get(intent_id, 0) + 1

    # Rank intents by score
    ranked_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)

    if not ranked_intents:
        return {
            "error": "No intents match selected metrics",
            "workloads": [],
            "recommendations": ["Try selecting more common metrics like OPCOUNTER_* or CONNECTIONS"]
        }

    # Return top intent as recommendation
    top_intent_id = ranked_intents[0][0]
    top_intent = INTENT_DEFINITIONS[top_intent_id]

    return {
        "recommended_intent": top_intent_id,
        "intent_name": top_intent["name"],
        "workloads": top_intent["workload_keys"],
        "matched_metrics": [m for m in metric_names if m in top_intent["primary_metrics"] or m in top_intent["secondary_metrics"]],
        "coverage_pct": int(len([m for m in metric_names if m in top_intent["primary_metrics"]]) / len(metric_names) * 100) if metric_names else 0,
        "message": f"Intent '{top_intent['name']}' will spike {len([m for m in metric_names if m in top_intent['primary_metrics']])} of your selected metrics.",
        "all_ranked": [{"intent_id": iid, "score": score} for iid, score in ranked_intents[:3]]
    }
