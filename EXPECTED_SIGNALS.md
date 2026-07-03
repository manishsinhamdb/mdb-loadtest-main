# EXPECTED_SIGNALS.md — workload → FTDC metric mapping

This is the static half of the validation oracle. Each load workload is designed
to move a **specific, known** set of MongoDB diagnostic (FTDC) metrics. When you
diff the target's FTDC output against a run's `manifest.json`, these are the
signals you should see move during the run's UTC window.

> Timezone discipline: every manifest records the run window in **both IST and
> UTC**. FTDC is UTC. Always correlate on UTC. A clock-skew preflight warns if
> OMEN and the target disagree by more than 2s (which would corrupt correlation).

| # | Workload | Key parameters | Expected FTDC signal(s) |
|---|----------|----------------|--------------------------|
| 1 | `connection_storm` | connection_count | `connections.current` ↑, `globalLock.activeClients.total` ↑, `network.numRequests` ↑ |
| 2 | `indexed_reads` | threads, target_ops_per_sec | `opcounters.query` ↑ (high), **query targeting ≈ 1** (`metrics.queryExecutor.scanned` ≈ docs returned) |
| 3 | `unindexed_scans` | threads, ops/sec | **query targeting ratio ↑** (`scanned` ≫ `returned`), `metrics.queryExecutor.scanned` ↑ (objs_scanned_ps) |
| 4 | `inmemory_sorts` | threads | `metrics.operation.scanAndOrder` ↑ (scan_and_order_ps) |
| 5 | `aggregation_pipelines` | complexity, threads | CPU ↑, `metrics.queryExecutor.scanned` ↑, WiredTiger `bytes read into cache` ↑ |
| 6 | `write_bursts` | batch_size, doc_kb, threads | `opcounters.insert` ↑, disk **write IOPS** ↑, WiredTiger `tracked dirty bytes` % ↑, **checkpoint** activity ↑ |
| 7 | `update_contention` | threads, hot_doc_count | `opcounters.update` ↑, `metrics.operation.writeConflicts` ↑ (write_conflicts_ps), WiredTiger **write ticket** utilization ↑ |
| 8 | `mixed_blend` | weights / seed | Composite — the union of the signals of whichever sub-workloads the blend selected (recorded per-run in the manifest) |

## How the harness proves load landed

Independently of FTDC, every run records `serverStatus.opcounters` **before** and
**after** the run and stores the delta in the manifest (`opcounters.delta`). A
non-trivial delta in `insert`/`query`/`update` etc. is direct proof from the
target server that the issued operations were actually executed there — a
ground truth you can line up against the FTDC curves.

## Notes on the seeded dataset (why each signal is reachable)

- `large_dataset` has an **indexed** `user_id` and an **unindexed** `random_tag`.
  - `indexed_reads` queries `user_id` → index hit → targeting ≈ 1.
  - `unindexed_scans` queries `random_tag` → collection scan → targeting ratio rises.
  - `inmemory_sorts` sorts on the unindexed `value` → forces `scanAndOrder`.
- `agg_dataset` carries arrays/subdocs (`items`, `tags`) so `$unwind`/`$group`
  pipelines do real per-document work.
- `hot_docs` is intentionally tiny; many threads updating few `_id`s maximises
  WiredTiger write conflicts.
- `append_target` is the insert sink for `write_bursts` (sized docs → cache &
  checkpoint pressure).
