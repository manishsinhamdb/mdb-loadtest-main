# MongoDB Load Test Platform V2 - Comprehensive Design Document

**Version**: 2.0.0  
**Date**: 2026-07-03  
**Status**: Architecture Design  
**Target**: MongoDB 8.x + Atlas (2025-2026 features)

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Atlas Metrics Catalog](#atlas-metrics-catalog)
4. [UI/UX Flow](#uiux-flow)
5. [Backend Modules](#backend-modules)
6. [Database Schema](#database-schema)
7. [Implementation Phases](#implementation-phases)
8. [API Specifications](#api-specifications)

---

## Executive Summary

Transform the MongoDB load generator from a manual workload selector into an **intelligent, intent-driven load testing platform** that:

1. **Guides users** through connection setup with auto-discovery
2. **Recommends optimal test configurations** based on testing intent
3. **Maps load patterns to Atlas metrics** with clear impact visualization
4. **Provides comprehensive metric targeting** with 100+ Atlas/FTDC metrics
5. **Supports MongoDB 8.x latest features** including new serverStatus fields

### Key Principles
- **Modular architecture** - Each component is independently testable
- **Hard limits with override capability** - System enforces safe defaults but allows expert override
- **Comprehensive metric coverage** - Support all Atlas UI metrics + FTDC diagnostics
- **Atlas API integration** - Optional real-time metric validation

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Connection   │  │ Intent       │  │ Advanced     │          │
│  │ Manager UI   │  │ Designer UI  │  │ Config UI    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                  │                  │                   │
│         └──────────────────┴──────────────────┘                  │
│                            │                                      │
└────────────────────────────┼──────────────────────────────────────┘
                             │ REST API
┌────────────────────────────┼──────────────────────────────────────┐
│                     API GATEWAY (FastAPI)                         │
│  ┌─────────────┬─────────────┬─────────────┬─────────────┐      │
│  │ Connection  │ Discovery   │ Intent      │ Metric      │      │
│  │ API         │ API         │ Engine API  │ Builder API │      │
│  └──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┘      │
└─────────┼─────────────┼─────────────┼─────────────┼─────────────┘
          │             │             │             │
┌─────────┼─────────────┼─────────────┼─────────────┼─────────────┐
│                     BUSINESS LOGIC LAYER                          │
│  ┌──────▼──────┐  ┌──▼─────────┐  ┌▼───────────┐  ┌▼──────────┐ │
│  │ Connection  │  │ Hardware   │  │ Intent     │  │ Metric    │ │
│  │ Manager     │  │ Discovery  │  │ Engine     │  │ Mapper    │ │
│  └─────────────┘  └────────────┘  └────────────┘  └───────────┘ │
│                                                                   │
│  ┌─────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────┐ │
│  │ Workload    │  │ Parameter  │  │ Resource   │  │ Atlas     │ │
│  │ Optimizer   │  │ Calculator │  │ Validator  │  │ API Client│ │
│  └─────────────┘  └────────────┘  └────────────┘  └───────────┘ │
└───────────────────────────────────────────────────────────────────┘
          │             │             │             │
┌─────────┼─────────────┼─────────────┼─────────────┼─────────────┐
│                       DATA LAYER                                  │
│  ┌──────▼──────┐  ┌──▼─────────┐  ┌▼───────────┐  ┌▼──────────┐ │
│  │ Connection  │  │ Intent     │  │ Metric     │  │ Run       │ │
│  │ Profiles DB │  │ Templates  │  │ Catalog    │  │ History   │ │
│  │ (SQLite)    │  │ (JSON)     │  │ (JSON)     │  │ (SQLite)  │ │
│  └─────────────┘  └────────────┘  └────────────┘  └───────────┘ │
└───────────────────────────────────────────────────────────────────┘
```

---

## Atlas Metrics Catalog

### Complete Metrics List (100+ Metrics)

Based on research of MongoDB 8.x and Atlas 2025-2026 features:

#### **Category 1: Hardware & System (22 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `SYSTEM_CPU_USER` | % | User CPU usage | All workloads |
| `SYSTEM_CPU_KERNEL` | % | Kernel CPU usage | I/O heavy workloads |
| `SYSTEM_CPU_IOWAIT` | % | CPU waiting for I/O | write_bursts, disk operations |
| `SYSTEM_CPU_STEAL` | % | Stolen CPU (virtualized) | Resource contention |
| `SYSTEM_CPU_GUEST` | % | Guest VM CPU | Virtualized environments |
| `SYSTEM_MEMORY_AVAILABLE` | bytes | Available RAM | Cache pressure tests |
| `SYSTEM_MEMORY_USED` | bytes | Used RAM | inmemory_sorts, aggregation |
| `SYSTEM_MEMORY_FREE` | bytes | Free RAM | Baseline monitoring |
| `SYSTEM_MEMORY_BUFFERS` | bytes | Buffer cache | Disk I/O operations |
| `SYSTEM_MEMORY_CACHED` | bytes | Page cache | Read-heavy workloads |
| `SWAP_USAGE_USED` | bytes | Swap used | Memory pressure |
| `SWAP_USAGE_FREE` | bytes | Swap available | System health |
| `MAX_SYSTEM_MEMORY_PERCENT` | % | Peak memory % | Spike detection |
| `MAX_SYSTEM_CPU_PERCENT` | % | Peak CPU % | Spike detection |
| `DISK_PARTITION_UTILIZATION` | % | Disk space used | write_bursts |
| `DISK_PARTITION_IOPS_READ` | ops/s | Read IOPS | indexed_reads, scans |
| `DISK_PARTITION_IOPS_WRITE` | ops/s | Write IOPS | write_bursts, updates |
| `DISK_PARTITION_LATENCY_READ` | ms | Read latency | Query performance |
| `DISK_PARTITION_LATENCY_WRITE` | ms | Write latency | Write performance |
| `DISK_PARTITION_SPACE_FREE` | bytes | Free disk space | Capacity planning |
| `DISK_PARTITION_SPACE_USED` | bytes | Used disk space | Storage growth |
| `DISK_PARTITION_SPACE_PERCENT` | % | Disk usage % | Threshold alerts |

#### **Category 2: Connections & Network (15 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `CONNECTIONS` | count | Current connections | connection_storm |
| `CONNECTIONS_AVAILABLE` | count | Available connections | Connection pool limits |
| `MAX_CONNECTIONS` | count | Max configured connections | Configuration baseline |
| `NETWORK_BYTES_IN` | bytes/s | Inbound network | All workloads |
| `NETWORK_BYTES_OUT` | bytes/s | Outbound network | Query results |
| `NETWORK_NUM_REQUESTS` | count/s | Network requests | Connection activity |
| `NETWORK_PHYSICAL_BYTES_IN` | bytes/s | Physical NIC bytes in | True network load |
| `NETWORK_PHYSICAL_BYTES_OUT` | bytes/s | Physical NIC bytes out | True network load |
| `CONNECTIONS_ACTIVE` | count | Active client connections | Concurrent operations |
| `CONNECTIONS_LOAD_BALANCED` | count | Load balanced connections | Atlas load balancing |
| `CONNECTIONS_QUEUED_FOR_ESTABLISHMENT` | count | Queued connections (8.2+) | Connection pressure |
| `CONNECTIONS_REJECTED` | count | Rejected connections (6.3+) | Rate limiting |
| `CONNECTIONS_RATE_LIMIT_REJECTED` | count | Rate limited connections (8.2+) | Connection storms |
| `CONNECTIONS_TOTAL_CREATED` | count | Lifetime connection count | Connection churn |
| `NETWORK_REQUESTS_TIMED_OUT` | count | Timed out requests | Network issues |

#### **Category 3: Operations & OpCounters (16 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `OPCOUNTER_CMD` | ops/s | Commands executed | All workloads |
| `OPCOUNTER_QUERY` | ops/s | Query operations | indexed_reads, unindexed_scans |
| `OPCOUNTER_INSERT` | ops/s | Insert operations | write_bursts |
| `OPCOUNTER_UPDATE` | ops/s | Update operations | update_contention |
| `OPCOUNTER_DELETE` | ops/s | Delete operations | Data cleanup workloads |
| `OPCOUNTER_GETMORE` | ops/s | Getmore (cursor) ops | Large result sets |
| `OPCOUNTER_REPL_CMD` | ops/s | Replicated commands | Replication load |
| `OPCOUNTER_REPL_INSERT` | ops/s | Replicated inserts | Write replication |
| `OPCOUNTER_REPL_UPDATE` | ops/s | Replicated updates | Update replication |
| `OPCOUNTER_REPL_DELETE` | ops/s | Replicated deletes | Delete replication |
| `OPERATIONS_SCAN_AND_ORDER` | ops/s | In-memory sorts | inmemory_sorts |
| `OPERATIONS_WRITE_CONFLICTS` | count/s | Write conflicts | update_contention |
| `GLOBAL_LOCK_CURRENT_QUEUE_TOTAL` | count | Queued operations | Lock contention |
| `GLOBAL_LOCK_CURRENT_QUEUE_READERS` | count | Queued readers | Read contention |
| `GLOBAL_LOCK_CURRENT_QUEUE_WRITERS` | count | Queued writers | Write contention |
| `GLOBAL_ACCESSES_NOT_IN_MEMORY` | count/s | Page faults | Working set > RAM |

#### **Category 4: Query Performance (12 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `QUERY_EXECUTOR_SCANNED` | count/s | Index items scanned | indexed_reads |
| `QUERY_EXECUTOR_SCANNED_OBJECTS` | count/s | Documents examined | unindexed_scans |
| `QUERY_TARGETING_SCANNED_PER_RETURNED` | ratio | Scan efficiency (index) | Query optimization |
| `QUERY_TARGETING_SCANNED_OBJECTS_PER_RETURNED` | ratio | Scan efficiency (docs) | Collection scans |
| `DOCUMENT_METRICS_RETURNED` | docs/s | Documents returned | Query throughput |
| `DOCUMENT_METRICS_INSERTED` | docs/s | Documents inserted | Insert throughput |
| `DOCUMENT_METRICS_UPDATED` | docs/s | Documents updated | Update throughput |
| `DOCUMENT_METRICS_DELETED` | docs/s | Documents deleted | Delete throughput |
| `CURSORS_TOTAL_OPEN` | count | Open cursors | Cursor leaks |
| `CURSORS_TOTAL_TIMED_OUT` | count | Timed out cursors | Long-running queries |
| `QUERIES_OVER_THRESHOLD` | count | Slow queries | Performance issues |
| `AVG_QUERY_EXECUTION_TIME` | ms | Average query time | Query performance |

#### **Category 5: Cache & WiredTiger (20 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `CACHE_BYTES_READ_INTO` | bytes/s | Cache read rate | Read workloads |
| `CACHE_BYTES_WRITTEN_FROM` | bytes/s | Cache write rate | Write workloads |
| `CACHE_DIRTY_BYTES` | bytes | Dirty cache bytes | Write pressure |
| `CACHE_USED_BYTES` | bytes | Total cache usage | Working set |
| `CACHE_DIRTY_BYTES_PERCENT` | % | Dirty % of cache | Checkpoint pressure |
| `CACHE_USED_PERCENT` | % | Cache utilization % | Memory efficiency |
| `CACHE_EVICTED_UNMODIFIED` | pages/s | Clean evictions | Cache churn |
| `CACHE_EVICTED_MODIFIED` | pages/s | Dirty evictions | Write-heavy |
| `TICKETS_AVAILABLE_READS` | count | Read tickets available | Read concurrency |
| `TICKETS_AVAILABLE_WRITES` | count | Write tickets available | Write concurrency |
| `TICKETS_AVAILABLE_READS_PERCENT` | % | Read ticket % | Read throttling |
| `TICKETS_AVAILABLE_WRITES_PERCENT` | % | Write ticket % | Write throttling |
| `WIREDTIGER_TRANSACTIONS_CHECKPOINT_MS` | ms | Checkpoint duration | Write bursts impact |
| `WIREDTIGER_TRANSACTIONS_COMMITTED` | count/s | Transactions committed | Transaction rate |
| `WIREDTIGER_TRANSACTIONS_ROLLEDBACK` | count/s | Transactions rolled back | Conflicts |
| `WIREDTIGER_CACHE_PAGES_HELD` | pages | Pages held in cache | Cache state |
| `WIREDTIGER_CACHE_MAX_PAGE_SIZE` | bytes | Max page size | Storage details |
| `WIREDTIGER_BLOCK_MANAGER_BLOCKS_READ` | blocks/s | Blocks read from disk | Disk reads |
| `WIREDTIGER_BLOCK_MANAGER_BLOCKS_WRITTEN` | blocks/s | Blocks written to disk | Disk writes |
| `WIREDTIGER_BLOCK_MANAGER_BYTES_READ` | bytes/s | Bytes read from disk | I/O throughput |

#### **Category 6: Replication (12 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `OPLOG_MASTER_TIME` | seconds | Oplog window | Replication capacity |
| `OPLOG_MASTER_LAG_TIME_DIFF` | seconds | Replication lag | Secondary latency |
| `OPLOG_RATE_GB_PER_HOUR` | GB/hr | Oplog growth rate | Write intensity |
| `OPLOG_SLAVE_LAG_MASTER_TIME` | seconds | Slave lag | Replication health |
| `REPL_NETWORK_BYTES` | bytes/s | Replication network | Network usage |
| `REPL_NETWORK_GETMORES_NUM` | ops/s | Replication getmores | Oplog tailing |
| `REPL_NETWORK_GETMORES_TOTAL_MILLIS` | ms | Getmore total time | Replication efficiency |
| `REPL_BUFFER_COUNT` | count | Replication buffer count | Buffer pressure |
| `REPL_BUFFER_SIZE_BYTES` | bytes | Replication buffer size | Memory usage |
| `REPL_APPLY_BATCHES_NUM` | batches/s | Apply batch rate | Application rate |
| `REPL_APPLY_OPS` | ops/s | Operations applied | Replication throughput |
| `REPL_EXECUTOR_QUEUES` | count | Executor queue depth | Replication backlog |

#### **Category 7: Database & Storage (10 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `DATABASE_STORAGE_SIZE` | bytes | Total storage size | Dataset growth |
| `DATABASE_DATA_SIZE` | bytes | Actual data size | Data volume |
| `DATABASE_INDEX_SIZE` | bytes | Total index size | Index efficiency |
| `DATABASE_AVERAGE_OBJECT_SIZE` | bytes | Average doc size | Document design |
| `DATABASE_COLLECTION_COUNT` | count | Number of collections | Schema complexity |
| `DATABASE_VIEW_COUNT` | count | Number of views | View usage |
| `DATABASE_INDEX_COUNT` | count | Total indexes | Index management |
| `DATABASE_EXTENT_FREE_LIST_NUM` | count | Free extents | Storage fragmentation |
| `DATABASE_DATAFILE_SIZE` | bytes | Datafile size | Pre-allocation |
| `DATABASE_NS_SIZE_MB` | MB | Namespace size | Metadata size |

#### **Category 8: Asserts & Errors (6 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `ASSERT_REGULAR` | count | Regular asserts | Server issues |
| `ASSERT_WARNING` | count | Warning asserts | Warning conditions |
| `ASSERT_MSG` | count | Message asserts | Error messages |
| `ASSERT_USER` | count | User asserts | Application errors |
| `ASSERT_ROLLOVERS` | count | Counter rollovers | Stat resets |
| `EXTRA_INFO_PAGE_FAULTS` | faults/s | Page faults | Memory pressure |

#### **Category 9: Atlas Search (8 metrics) - NEW**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `SEARCH_INDEX_SIZE` | bytes | Search index size | Index storage |
| `SEARCH_QUERY_COUNT` | queries/s | Search queries executed | Search load |
| `SEARCH_QUERY_EXECUTION_TIME` | ms | Avg search query time | Search performance |
| `SEARCH_INDEXING_OPERATIONS` | ops/s | Indexing operations | Index updates |
| `SEARCH_MEMORY_USAGE` | bytes | Search memory consumption | Memory overhead |
| `SEARCH_CPU_USAGE` | % | Search CPU usage | CPU overhead |
| `SEARCH_DISK_USAGE` | bytes | Search disk usage | Storage overhead |
| `SEARCH_REPLICATION_LAG` | seconds | Search index lag | Index freshness |

#### **Category 10: Process & Server Metrics (9 metrics)**

| Metric Name | Unit | Description | Workload Impact |
|------------|------|-------------|-----------------|
| `PROCESS_CPU_USER` | % | Process user CPU | All workloads |
| `PROCESS_CPU_KERNEL` | % | Process kernel CPU | I/O operations |
| `PROCESS_NORMALIZED_CPU_USER` | % | Normalized user CPU | Standardized metric |
| `PROCESS_NORMALIZED_CPU_KERNEL` | % | Normalized kernel CPU | Standardized metric |
| `PROCESS_RESIDENT_MEMORY` | bytes | Resident set size | Memory usage |
| `PROCESS_VIRTUAL_MEMORY` | bytes | Virtual memory | Memory allocation |
| `PROCESS_SHARED_MEMORY` | bytes | Shared memory | IPC usage |
| `SERVER_UPTIME` | seconds | Server uptime | Availability |
| `SERVER_RESTART_COUNT` | count | Restart counter | Stability |

---

## UI/UX Flow

### **Tab Structure (5 Tabs)**

```
┌─────────────────────────────────────────────────────────────────┐
│  [1 Connections] [2 Test Designer] [3 Advanced] [4 Run] [5 Schedule] │
└─────────────────────────────────────────────────────────────────┘
```

---

### **Tab 1: Connection Manager**

#### **Layout Sections:**

**A. Connection Profile Selector**
```
┌─────────────────────────────────────────────────────────────┐
│ Select Connection Profile:                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [•] Production Cluster (M40, us-east-1)                 │ │
│ │ [ ] Staging Cluster (M10, us-west-2)                    │ │
│ │ [ ] Local Dev Replica Set                               │ │
│ │ [+] Add New Connection Profile                          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                               │
│ [Edit] [Delete] [Test Connection]                            │
└─────────────────────────────────────────────────────────────┘
```

**B. Connection Details (When "Add New" clicked)**
```
┌─────────────────────────────────────────────────────────────┐
│ Profile Name: [_______________________________]              │
│ Connection URI: [password field with show/hide]             │
│ Database Name: [loadtest________________]                   │
│ Auth Source: [admin____________________]                    │
│                                                               │
│ [ Save Profile ]  [ Cancel ]                                 │
└─────────────────────────────────────────────────────────────┘
```

**C. Auto-Discovery Results (Post-Connection Test)**
```
┌──────────────────────────────────────────────────────────────┐
│ ✓ CONNECTION SUCCESSFUL                                       │
│                                                               │
│ CLIENT MACHINE (Driver Host)              [Edit Override]    │
│ ├─ CPU Cores: 12 physical / 12 logical                       │
│ ├─ RAM: 24.00 GB total / 18.5 GB available                  │
│ ├─ Storage: 460 GB total / 314 GB free                       │
│ └─ Network: Estimated 1 Gbps                                 │
│                                                               │
│ MONGODB TARGET                                                │
│ ├─ Version: MongoDB 8.2.11 Enterprise                       │
│ ├─ Topology: Atlas Replica Set (3 nodes)                    │
│ ├─ Cluster Tier: M40 (40 GB RAM, 16 vCPUs)                  │
│ ├─ Region: us-east-1                                         │
│ ├─ Storage Engine: WiredTiger                                │
│ ├─ Current Connections: 45 / 3200 available                 │
│ └─ Current Load: CPU 12%, RAM 38%, Disk 15%                 │
│                                                               │
│ PERMISSION CHECK                          ✓ ALL PASSED      │
│ ├─ createCollection ✓   ├─ aggregate ✓                      │
│ ├─ insert ✓            ├─ find ✓                            │
│ ├─ createIndex ✓       └─ drop ✓                            │
│                                                               │
│ CLOCK SKEW CHECK                         ✓ 0.18s (OK)       │
│                                                               │
│ [ Continue to Test Designer → ]                              │
└──────────────────────────────────────────────────────────────┘
```

---

### **Tab 2: Test Designer (Intent-Driven Mode)**

#### **Mode Selector**
```
┌─────────────────────────────────────────────────────────────┐
│ Select Design Mode:                                          │
│ [●] Guided - Intent Based    [ ] Metric-Driven (V2)         │
└─────────────────────────────────────────────────────────────┘
```

#### **Intent Selection**
```
┌─────────────────────────────────────────────────────────────┐
│ What do you want to test?                                    │
│                                                               │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│ │ 🔌          │  │ 📖          │  │ ✍️           │       │
│ │ Connection  │  │ Read        │  │ Write       │       │
│ │ Stress      │  │ Performance │  │ Throughput  │       │
│ └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                               │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│ │ 🔄          │  │ 🔒          │  │ 💾          │       │
│ │ Aggregation │  │ Concurrency │  │ Cache       │       │
│ │ Pipeline    │  │ & Contention│  │ Pressure    │       │
│ └──────────────┘  └──────────────┘  └──────────────┘       │
│                                                               │
│ ┌──────────────┐  ┌──────────────┐                          │
│ │ 🎯          │  │ ⚙️           │                          │
│ │ Mixed       │  │ Custom       │                          │
│ │ Production  │  │ Advanced     │                          │
│ └──────────────┘  └──────────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

#### **Intent Configuration (Example: "Read Performance" selected)**
```
┌─────────────────────────────────────────────────────────────┐
│ INTENT: Read Performance Testing                             │
│                                                               │
│ Test Intensity:                                              │
│ ├─ Light ──●── Medium ──── Heavy ──── Extreme               │
│ └─ Current: Medium (Recommended for M40)                     │
│                                                               │
│ Test Duration:                                               │
│ ├─ 1min ──── 10min ──●── 1hr ──── 24hr                      │
│ └─ Selected: 10 minutes                                      │
│                                                               │
│ Dataset Size:                                                │
│ ├─ 10K ──── 100K ──── 1M ──●── 10M docs                     │
│ └─ Selected: 1 Million documents                             │
│                                                               │
│ Concurrency Level:                                           │
│ ├─ 1x ──── 10x ──●── 50x ──── 100x                          │
│ └─ Selected: 10x (120 total threads)                         │
│                                                               │
│ ⚠️ RESOURCE ESTIMATE                                          │
│ ├─ Client CPU: ~70% (8/12 cores)                            │
│ ├─ Client RAM: ~4.5 GB                                       │
│ ├─ Server CPU: ~45-60% estimated                            │
│ └─ Server RAM: ~12 GB working set                            │
│                                                               │
│ 📊 PRIMARY IMPACT (Will spike these metrics)                 │
│ ├─ OPCOUNTER_QUERY ⬆️ HIGH                                   │
│ ├─ QUERY_EXECUTOR_SCANNED ⬆️ HIGH                            │
│ ├─ CACHE_BYTES_READ_INTO ⬆️ MEDIUM                           │
│ └─ NETWORK_BYTES_OUT ⬆️ MEDIUM                               │
│                                                               │
│ 📈 SECONDARY IMPACT (Will also see movement in)              │
│ ├─ CONNECTIONS ⬆️ LOW (+120 connections)                     │
│ ├─ SYSTEM_CPU_USER ⬆️ MEDIUM                                 │
│ ├─ DOCUMENT_METRICS_RETURNED ⬆️ HIGH                         │
│ └─ CURSORS_TOTAL_OPEN ⬆️ LOW                                 │
│                                                               │
│ 🔧 PROPOSED CONFIGURATION                                     │
│ ├─ Workloads: indexed_reads, unindexed_scans               │
│ ├─ Seeding: 1M docs in large_dataset collection             │
│ ├─ Threads: indexed_reads=80, unindexed_scans=40            │
│ ├─ Target ops/sec: 5000 indexed, 500 unindexed              │
│ └─ Estimated test time: 12 minutes (incl. seeding)          │
│                                                               │
│ [ ◄ Back ]  [ Customize Parameters ]  [ Start Test ► ]      │
└─────────────────────────────────────────────────────────────┘
```

#### **Atlas Graph Preview Modal (Shown on hover/click)**
```
┌─────────────────────────────────────────────────────────────┐
│ Atlas Graph: OPCOUNTER_QUERY                                 │
│                                                               │
│  [Screenshot/Mock of Atlas UI graph]                         │
│   ↑                                                           │
│   │         ╱⎺⎺⎺⎺⎺╲  ← EXPECT SPIKE HERE                      │
│   │        ╱       ╲        (10:00-10:10 UTC)              │
│   │_______╱         ╲________________________________         │
│              Time →                                           │
│                                                               │
│ During your test window (10 minutes), this metric will      │
│ increase from baseline ~100 ops/s to ~5000 ops/s.           │
│                                                               │
│ [ View in Atlas Dashboard (opens browser) ]  [ Close ]       │
└─────────────────────────────────────────────────────────────┘
```

---

### **Tab 3: Advanced Configuration (Collapsible Sections)**

```
┌─────────────────────────────────────────────────────────────┐
│ ▼ Seeder Overrides                                           │
│   ├─ large_dataset docs: [1000000_____]                     │
│   ├─ agg_dataset docs: [50000______]                        │
│   ├─ hot_docs: [100___]                                     │
│   └─ Random seed: [_________] (blank = random)              │
│                                                               │
│ ▼ Per-Workload Fine-Tuning                                   │
│   indexed_reads:                                             │
│   ├─ threads: [80____] (hard limit: 120)                    │
│   ├─ target_ops_per_sec: [5000__] (0 = unlimited)           │
│   └─ duration_override: [___] (blank = use global)          │
│                                                               │
│   unindexed_scans:                                           │
│   ├─ threads: [40____]                                      │
│   └─ target_ops_per_sec: [500___]                           │
│                                                               │
│ ▼ Output & Logging                                           │
│   ├─ Output folder: [./runs_______________] [Validate]      │
│   ├─ Log level: [INFO ▾] (DEBUG, INFO, WARN, ERROR)         │
│   └─ Enable verbose FTDC logging: [✓]                       │
│                                                               │
│ ▼ Safety Overrides                                           │
│   [ ] Ignore clock skew > 2s warning                        │
│   [ ] Override CPU limit (allow >100% utilization)           │
│   [ ] Override connection limit (allow >max_connections)     │
│                                                               │
│ [ Reset to Recommended ]  [ Save Configuration ]             │
└─────────────────────────────────────────────────────────────┘
```

---

### **Tab 4: Run & Monitor**

```
┌─────────────────────────────────────────────────────────────┐
│ RUN STATUS: ⚡ RUNNING                                        │
│                                                               │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Test: Read Performance (Medium Intensity)               │ │
│ │ Started: 2026-07-03 10:00:00 IST / 04:30:00 UTC        │ │
│ │ Duration: 10 minutes                                     │ │
│ │ Progress: ▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░ 45% (4:30 remaining)     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                               │
│ 📊 REAL-TIME METRICS (If Atlas API connected)                │
│ ┌───────────────────┬───────────────────────────────────┐   │
│ │ Metric            │ Current    Baseline    Delta      │   │
│ ├───────────────────┼───────────────────────────────────┤   │
│ │ OPCOUNTER_QUERY   │ 4,823/s    120/s       +4,703    │   │
│ │ CONNECTIONS       │ 165        45          +120       │   │
│ │ CPU (User)        │ 68%        12%         +56%       │   │
│ │ CACHE_READ        │ 125 MB/s   8 MB/s      +117 MB/s  │   │
│ └───────────────────┴───────────────────────────────────┘   │
│                                                               │
│ 📝 LIVE LOG (Dual Timezone)                                  │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ [10:04:32 IST] INFO workload 'indexed_reads': 4820 ops│ │
│ │ [10:04:30 IST] INFO opcounters DELTA: query=28,940    │ │
│ │ [10:04:15 IST] INFO seeding complete: 1,000,000 docs  │ │
│ │ [10:00:05 IST] INFO RUN abc123 starting (mode=manual) │ │
│ │                                            [Auto-scroll]│ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                               │
│ [ Stop Test ]  [ Download Manifest ]  [ View in Atlas → ]   │
└─────────────────────────────────────────────────────────────┘
```

---

### **Tab 5: Schedule (Largely Unchanged)**

Current scheduling UI with minor enhancements for new intent-based configurations.

---

## Backend Modules

### **Module Structure**

```
mdb-loadtest-v2/
├── app.py                      # FastAPI app (enhanced)
├── config.py                   # Configuration (enhanced)
├── requirements.txt            # Dependencies (add new: psutil, cryptography)
│
├── core/                       # Core business logic (NEW)
│   ├── __init__.py
│   ├── connection_manager.py  # Connection profile CRUD + encryption
│   ├── hardware_discovery.py  # Auto-detect client/server specs
│   ├── intent_engine.py       # Intent → configuration mapper
│   ├── metric_mapper.py       # Metric → workload reverse mapping
│   ├── workload_optimizer.py  # Parameter optimization
│   ├── resource_validator.py  # Hard limits + override logic
│   └── atlas_client.py        # Atlas API integration
│
├── data/                       # Static data files (NEW)
│   ├── atlas_metrics.json     # Complete metric catalog (130+ metrics)
│   ├── intent_templates.json  # Pre-calculated intent configs
│   ├── metric_workload_map.json # Metric → workload mappings
│   └── hardware_profiles.json # Common hardware profiles
│
├── db/                         # Database layer (NEW)
│   ├── __init__.py
│   ├── models.py              # SQLAlchemy models
│   ├── connection_profiles.py # Connection profile storage
│   └── run_history.py         # Run history storage
│
├── api/                        # API routes (NEW - modular)
│   ├── __init__.py
│   ├── connections.py         # /api/connections/* endpoints
│   ├── discovery.py           # /api/discovery/* endpoints
│   ├── intent.py              # /api/intent/* endpoints
│   ├── metrics.py             # /api/metrics/* endpoints
│   └── runs.py                # /api/runs/* endpoints (existing logic)
│
├── static/                     # Frontend (ENHANCED)
│   ├── index.html             # New 5-tab structure
│   ├── style.css              # Enhanced styling
│   ├── app.js                 # Refactored modular JS
│   ├── components/            # NEW: Modular UI components
│   │   ├── connection-manager.js
│   │   ├── intent-designer.js
│   │   ├── metric-selector.js
│   │   ├── knobs-panel.js
│   │   └── live-monitor.js
│   └── assets/                # NEW: Atlas graph screenshots
│       ├── graph_opcounter_query.png
│       ├── graph_connections.png
│       └── ... (130+ preview images)
│
├── workloads/                  # Existing workload modules (unchanged)
│   └── ...
│
├── tests/                      # Test suite (NEW)
│   ├── test_intent_engine.py
│   ├── test_metric_mapper.py
│   ├── test_hardware_discovery.py
│   └── test_workload_optimizer.py
│
├── DESIGN_V2.md               # This document
└── MIGRATION_GUIDE.md         # V1 → V2 migration (NEW)
```

---

## Database Schema

### **SQLite Schema (connection_profiles.db)**

```sql
-- Connection profiles
CREATE TABLE connection_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    uri_encrypted BLOB NOT NULL,           -- Encrypted connection URI
    database_name TEXT NOT NULL,
    auth_source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    last_test_success BOOLEAN,
    last_test_at TIMESTAMP,
    
    -- Cached discovery data
    client_cpu_cores INTEGER,
    client_ram_gb REAL,
    client_storage_gb REAL,
    server_version TEXT,
    server_topology TEXT,
    server_cluster_tier TEXT,
    server_ram_gb REAL,
    server_vcpus INTEGER,
    
    -- User overrides
    override_cpu_cores INTEGER,
    override_ram_gb REAL,
    
    CONSTRAINT name_unique UNIQUE (name)
);

-- Run history (enhanced)
CREATE TABLE run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    connection_profile_id INTEGER,
    intent_type TEXT,                      -- NEW: connection_stress, read_performance, etc.
    intensity TEXT,                        -- NEW: light, medium, heavy, extreme
    mode TEXT,                             -- manual, scheduled
    started_utc TIMESTAMP,
    ended_utc TIMESTAMP,
    status TEXT,                           -- done, failed
    manifest_path TEXT,
    
    -- Configuration snapshot
    config_json TEXT,                      -- Full JSON of test config
    
    -- Results summary
    ops_total INTEGER,
    errors_total INTEGER,
    duration_seconds REAL,
    
    FOREIGN KEY (connection_profile_id) REFERENCES connection_profiles(id)
);

-- Intent configuration cache
CREATE TABLE intent_cache (
    intent_type TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,             -- Pre-calculated configuration
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Atlas metric definitions (for UI rendering)
CREATE TABLE atlas_metrics (
    metric_name TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    unit TEXT,
    description TEXT,
    atlas_graph_available BOOLEAN DEFAULT 1,
    ftdc_available BOOLEAN DEFAULT 1,
    preview_image_path TEXT                -- Screenshot of Atlas graph
);

-- Metric → Workload mapping
CREATE TABLE metric_workload_map (
    metric_name TEXT NOT NULL,
    workload_key TEXT NOT NULL,
    impact_level TEXT,                     -- primary, secondary, tertiary
    confidence REAL,                       -- 0.0 to 1.0
    PRIMARY KEY (metric_name, workload_key),
    FOREIGN KEY (metric_name) REFERENCES atlas_metrics(metric_name)
);

CREATE INDEX idx_run_history_profile ON run_history(connection_profile_id);
CREATE INDEX idx_run_history_intent ON run_history(intent_type);
CREATE INDEX idx_metric_map_metric ON metric_workload_map(metric_name);
```

---

## Implementation Phases

### **Phase 1: Foundation (Week 1-2)**
- [x] Research completed
- [ ] Setup new module structure
- [ ] Create `atlas_metrics.json` with 130+ metrics
- [ ] Create `intent_templates.json` with 8 intent types
- [ ] Build `metric_workload_map.json` (reverse of EXPECTED_SIGNALS.md)
- [ ] Database schema + migrations
- [ ] Unit tests for data structures

**Deliverable**: Data foundation ready for business logic

### **Phase 2: Connection Manager (Week 3)**
- [ ] `core/connection_manager.py` - CRUD operations
- [ ] URI encryption/decryption with `cryptography` library
- [ ] `api/connections.py` - REST endpoints
- [ ] Frontend `components/connection-manager.js`
- [ ] Tab 1 UI implementation
- [ ] Integration tests

**Deliverable**: Working connection profile management

### **Phase 3: Hardware Discovery (Week 4)**
- [ ] `core/hardware_discovery.py` - Client discovery (psutil)
- [ ] MongoDB server introspection (enhanced preflight.py)
- [ ] Atlas cluster tier detection (API integration)
- [ ] `api/discovery.py` - Discovery endpoints
- [ ] Auto-discovery UI in Tab 1
- [ ] Resource override UI

**Deliverable**: Auto-discovery working end-to-end

### **Phase 4: Intent Engine (Week 5-6)**
- [ ] `core/intent_engine.py` - Intent → config logic
- [ ] `core/workload_optimizer.py` - Parameter calculations
- [ ] `core/resource_validator.py` - Limits + overrides
- [ ] `api/intent.py` - Intent endpoints
- [ ] Frontend `components/intent-designer.js`
- [ ] Tab 2 UI (intent mode) implementation
- [ ] Knobs panel with real-time calculation
- [ ] Impact preview system

**Deliverable**: Guided intent-based test designer working

### **Phase 5: Metric Catalog & Visualization (Week 7)**
- [ ] `core/metric_mapper.py` - Metric → workload mapper
- [ ] Load atlas_metrics.json into SQLite
- [ ] Generate/collect Atlas graph screenshots (130+ images)
- [ ] Frontend `components/metric-selector.js`
- [ ] Graph preview modal implementation
- [ ] Primary/secondary impact calculation

**Deliverable**: Metric catalog with visual impact preview

### **Phase 6: Atlas API Integration (Week 8)**
- [ ] `core/atlas_client.py` - Atlas Monitoring API client
- [ ] Real-time metric polling during runs
- [ ] Baseline vs. current metric comparison
- [ ] `api/metrics.py` - Metric endpoints
- [ ] Frontend `components/live-monitor.js`
- [ ] Tab 4 real-time metrics display

**Deliverable**: Optional live Atlas metric monitoring

### **Phase 7: Advanced Configuration & Run (Week 9)**
- [ ] Tab 3 UI - Advanced overrides
- [ ] Enhanced runner.py integration with intent configs
- [ ] Per-workload parameter override UI
- [ ] Safety override warnings
- [ ] Tab 4 enhanced run monitoring
- [ ] Manifest enhancements (include intent metadata)

**Deliverable**: Full run flow with advanced config

### **Phase 8: Testing & UAT (Week 10-11)**
- [ ] End-to-end integration tests
- [ ] Load testing the load tester (meta!)
- [ ] macOS compatibility verification
- [ ] Performance optimization
- [ ] Documentation (user guide + API docs)
- [ ] UAT with sample workloads
- [ ] Bug fixes

**Deliverable**: Production-ready V2

### **Phase 9: Metric-Driven Mode (Future - V2.1)**
- [ ] Full metric checkbox UI (130+ metrics)
- [ ] Multi-metric solver algorithm
- [ ] Confidence scoring system
- [ ] A/B comparison mode (predicted vs. actual)

**Deliverable**: V2.1 with metric-driven mode

---

## API Specifications

### **New Endpoints**

#### **Connection Profiles**

```
POST   /api/connections                  Create new profile
GET    /api/connections                  List all profiles
GET    /api/connections/{id}             Get profile by ID
PUT    /api/connections/{id}             Update profile
DELETE /api/connections/{id}             Delete profile
POST   /api/connections/{id}/test        Test connection (auto-discovery)
```

#### **Hardware Discovery**

```
GET    /api/discovery/client             Get client machine specs
POST   /api/discovery/server             Discover server specs (requires URI)
POST   /api/discovery/override           Save user overrides
```

#### **Intent Engine**

```
GET    /api/intent/types                 List available intent types
POST   /api/intent/calculate             Calculate config from intent + params
GET    /api/intent/preview               Preview impact for given config
```

#### **Metrics**

```
GET    /api/metrics/catalog              Get all 130+ metrics
GET    /api/metrics/categories           Get metric categories
GET    /api/metrics/{name}               Get metric details
GET    /api/metrics/{name}/preview       Get Atlas graph preview image
POST   /api/metrics/map                  Map selected metrics → workloads
POST   /api/metrics/live                 Get live Atlas metrics (requires API key)
```

#### **Runs (Enhanced)**

```
POST   /api/runs                         Create run (now accepts intent_config)
GET    /api/runs/{run_id}/metrics/live   Get live metrics during run
GET    /api/runs/history                 Get run history with filtering
```

---

## Atlas API Integration Details

### **Configuration**

User can optionally provide Atlas API credentials:

```json
{
  "atlas_public_key": "abcd1234",
  "atlas_private_key": "xyz789...",
  "atlas_group_id": "60a5c...",
  "atlas_cluster_name": "Cluster0"
}
```

### **Features Enabled with Atlas API**

1. **Cluster Tier Detection**: Auto-detect M10, M40, etc.
2. **Current Load Baseline**: Fetch current metrics before test
3. **Live Monitoring**: Poll metrics every 10-60s during test
4. **Post-Test Validation**: Compare predicted vs. actual spikes
5. **Historical Comparison**: Compare against past runs

### **API Calls Made**

```bash
# Get cluster details
GET /api/atlas/v2/groups/{groupId}/clusters/{clusterName}

# Get current metrics (baseline)
GET /api/atlas/v2/groups/{groupId}/processes/{host}:{port}/measurements
  ?granularity=PT1M
  &period=PT1H
  &m=OPCOUNTER_QUERY
  &m=CONNECTIONS
  &m=SYSTEM_CPU_USER
  ...

# Poll during test (every 60s)
GET /api/atlas/v2/groups/{groupId}/processes/{host}:{port}/measurements
  ?granularity=PT1M
  &start={test_start_time}
  &end={now}
  &m=...
```

### **Fallback Behavior**

- **Without Atlas API**: All features work, but no live metrics
- **With Connection URI Only**: Auto-discovery via serverStatus, no Atlas-specific tier info
- **With Atlas API**: Full feature set

---

## Metric → Workload Mapping Logic

### **Reverse Engineering EXPECTED_SIGNALS.md**

```json
{
  "OPCOUNTER_QUERY": [
    {"workload": "indexed_reads", "impact": "primary", "confidence": 1.0},
    {"workload": "unindexed_scans", "impact": "primary", "confidence": 1.0},
    {"workload": "mixed_blend", "impact": "secondary", "confidence": 0.8}
  ],
  "OPCOUNTER_INSERT": [
    {"workload": "write_bursts", "impact": "primary", "confidence": 1.0},
    {"workload": "mixed_blend", "impact": "secondary", "confidence": 0.7}
  ],
  "OPCOUNTER_UPDATE": [
    {"workload": "update_contention", "impact": "primary", "confidence": 1.0}
  ],
  "OPERATIONS_WRITE_CONFLICTS": [
    {"workload": "update_contention", "impact": "primary", "confidence": 1.0}
  ],
  "QUERY_TARGETING_SCANNED_PER_RETURNED": [
    {"workload": "unindexed_scans", "impact": "primary", "confidence": 0.9},
    {"workload": "indexed_reads", "impact": "inverse", "confidence": 0.8}
  ],
  "CONNECTIONS": [
    {"workload": "connection_storm", "impact": "primary", "confidence": 1.0}
  ],
  "OPERATIONS_SCAN_AND_ORDER": [
    {"workload": "inmemory_sorts", "impact": "primary", "confidence": 1.0}
  ],
  "CACHE_DIRTY_BYTES": [
    {"workload": "write_bursts", "impact": "primary", "confidence": 0.9},
    {"workload": "update_contention", "impact": "secondary", "confidence": 0.7}
  ],
  "DISK_PARTITION_IOPS_WRITE": [
    {"workload": "write_bursts", "impact": "primary", "confidence": 0.9}
  ],
  "SYSTEM_CPU_USER": [
    {"workload": "aggregation_pipelines", "impact": "primary", "confidence": 0.8},
    {"workload": "all", "impact": "secondary", "confidence": 0.5}
  ]
}
```

### **Solver Algorithm (for Metric-Driven Mode)**

Given user-selected metrics, find minimal workload set:

```python
def solve_metric_coverage(selected_metrics: list[str]) -> dict:
    """
    Find optimal workload configuration to spike selected metrics.
    
    Returns:
        {
            "workloads": {workload_key: params},
            "coverage": {metric_name: confidence_score},
            "uncovered": [metric_names],
            "overall_confidence": float
        }
    """
    # Greedy set cover algorithm
    # 1. For each metric, get workloads with primary impact
    # 2. Select workload covering most uncovered metrics
    # 3. Repeat until all covered or no more workloads
    # 4. Calculate optimal parameters for selected workloads
```

---

## Hardware Limits & Validation

### **Hard Limits**

```python
# core/resource_validator.py

class ResourceLimits:
    """Calculate safe limits based on hardware."""
    
    @staticmethod
    def max_threads(cpu_cores: int) -> int:
        """Max threads = 10 × CPU cores (leave 2 cores free)."""
        return max(1, (cpu_cores - 2) * 10)
    
    @staticmethod
    def max_concurrent_ops(ram_gb: float) -> int:
        """Estimate max ops based on RAM (1GB RAM = ~10K ops/s)."""
        return int(ram_gb * 10_000)
    
    @staticmethod
    def max_connection_count(server_max_connections: int) -> int:
        """Use 80% of server max connections."""
        return int(server_max_connections * 0.8)
    
    @staticmethod
    def validate_config(config: dict, hardware: dict) -> list[str]:
        """
        Validate configuration against hardware.
        
        Returns list of warnings/errors.
        """
        warnings = []
        
        total_threads = sum(
            params.get("threads", 0) 
            for params in config["workloads"].values()
        )
        
        max_t = ResourceLimits.max_threads(hardware["cpu_cores"])
        if total_threads > max_t:
            warnings.append(
                f"Total threads ({total_threads}) exceeds "
                f"recommended limit ({max_t})"
            )
        
        # Check RAM for seeding
        seed_size_gb = config.get("seed_large_count", 0) * 1024 / 1e9
        if seed_size_gb > hardware["ram_gb"] * 0.5:
            warnings.append(
                f"Seeding {seed_size_gb:.1f}GB may exceed "
                f"available RAM ({hardware['ram_gb']:.1f}GB)"
            )
        
        return warnings
```

### **Override UI**

When user tries to exceed limits:

```
┌─────────────────────────────────────────────────────────────┐
│ ⚠️ WARNING: Resource Limit Exceeded                          │
│                                                               │
│ You have configured 480 total threads, which exceeds the    │
│ recommended limit of 120 threads for your system.           │
│                                                               │
│ Your machine: 12 CPU cores, 24 GB RAM                        │
│ Recommended max: 120 threads (10× per core, leaving 2 free) │
│ Your configuration: 480 threads (40× per core)              │
│                                                               │
│ Risks:                                                        │
│ • CPU oversubscription may cause thread starvation          │
│ • Context switching overhead will reduce throughput         │
│ • System may become unresponsive                            │
│                                                               │
│ [ Adjust to Recommended ]  [ Override (I know what I'm doing) ] │
└─────────────────────────────────────────────────────────────┘
```

---

## Intent Templates

### **Pre-calculated Configurations**

```json
{
  "connection_stress": {
    "name": "Connection Stress",
    "description": "Test connection pool limits and concurrent connection handling",
    "workloads": {
      "connection_storm": {
        "connection_count": "{calculated}",
        "hold_seconds": 300
      }
    },
    "seeding": "minimal",
    "primary_metrics": ["CONNECTIONS", "CONNECTIONS_AVAILABLE", "GLOBAL_LOCK_CURRENT_QUEUE_TOTAL"],
    "secondary_metrics": ["NETWORK_NUM_REQUESTS", "NETWORK_BYTES_IN"],
    "calculation_formula": {
      "connection_count": "min(server_max_connections * 0.5, client_cpu_cores * 100)"
    },
    "intensity_multipliers": {
      "light": 0.25,
      "medium": 0.5,
      "heavy": 0.75,
      "extreme": 1.0
    }
  },
  
  "read_performance": {
    "name": "Read Performance",
    "description": "Evaluate indexed and unindexed query performance",
    "workloads": {
      "indexed_reads": {
        "threads": "{calculated}",
        "target_ops_per_sec": 0
      },
      "unindexed_scans": {
        "threads": "{calculated}",
        "target_ops_per_sec": 0
      }
    },
    "seeding": {
      "large_count": "{data_size}",
      "agg_count": 50000,
      "hot_docs": 100
    },
    "primary_metrics": [
      "OPCOUNTER_QUERY",
      "QUERY_EXECUTOR_SCANNED",
      "QUERY_EXECUTOR_SCANNED_OBJECTS",
      "QUERY_TARGETING_SCANNED_PER_RETURNED"
    ],
    "secondary_metrics": [
      "CACHE_BYTES_READ_INTO",
      "NETWORK_BYTES_OUT",
      "DOCUMENT_METRICS_RETURNED"
    ],
    "calculation_formula": {
      "indexed_reads_threads": "client_cpu_cores * intensity * 8",
      "unindexed_scans_threads": "client_cpu_cores * intensity * 4"
    },
    "intensity_multipliers": {
      "light": 0.25,
      "medium": 0.5,
      "heavy": 0.75,
      "extreme": 1.0
    },
    "data_size_map": {
      "10k": 10000,
      "100k": 100000,
      "1m": 1000000,
      "10m": 10000000
    }
  },
  
  "write_throughput": {
    "name": "Write Throughput",
    "description": "Stress test insert capacity and checkpoint behavior",
    "workloads": {
      "write_bursts": {
        "threads": "{calculated}",
        "batch_size": 100,
        "doc_kb": 10
      }
    },
    "seeding": "minimal",
    "primary_metrics": [
      "OPCOUNTER_INSERT",
      "DISK_PARTITION_IOPS_WRITE",
      "CACHE_DIRTY_BYTES",
      "CACHE_DIRTY_BYTES_PERCENT",
      "WIREDTIGER_TRANSACTIONS_CHECKPOINT_MS"
    ],
    "secondary_metrics": [
      "DISK_PARTITION_LATENCY_WRITE",
      "TICKETS_AVAILABLE_WRITES",
      "SYSTEM_CPU_KERNEL"
    ],
    "calculation_formula": {
      "threads": "min(client_cpu_cores * intensity * 5, server_vcpus * 2)"
    }
  },
  
  "aggregation_pipeline": {
    "name": "Aggregation Pipeline",
    "description": "Test complex aggregation query performance",
    "workloads": {
      "aggregation_pipelines": {
        "threads": "{calculated}",
        "complexity": "high"
      }
    },
    "seeding": {
      "large_count": 500000,
      "agg_count": "{data_size}",
      "hot_docs": 100
    },
    "primary_metrics": [
      "SYSTEM_CPU_USER",
      "QUERY_EXECUTOR_SCANNED",
      "CACHE_BYTES_READ_INTO"
    ],
    "secondary_metrics": [
      "DOCUMENT_METRICS_RETURNED",
      "CURSORS_TOTAL_OPEN"
    ],
    "calculation_formula": {
      "threads": "client_cpu_cores * intensity * 4"
    }
  },
  
  "concurrency_contention": {
    "name": "Concurrency & Contention",
    "description": "Test write conflicts and lock contention with hot documents",
    "workloads": {
      "update_contention": {
        "threads": "{calculated}",
        "hot_doc_count": 50
      }
    },
    "seeding": {
      "large_count": 100000,
      "agg_count": 50000,
      "hot_docs": 50
    },
    "primary_metrics": [
      "OPCOUNTER_UPDATE",
      "OPERATIONS_WRITE_CONFLICTS",
      "TICKETS_AVAILABLE_WRITES",
      "TICKETS_AVAILABLE_WRITES_PERCENT"
    ],
    "secondary_metrics": [
      "GLOBAL_LOCK_CURRENT_QUEUE_WRITERS",
      "WIREDTIGER_TRANSACTIONS_ROLLEDBACK"
    ],
    "calculation_formula": {
      "threads": "min(100, client_cpu_cores * intensity * 10)"
    }
  },
  
  "cache_pressure": {
    "name": "Cache Pressure",
    "description": "Test behavior when working set exceeds available cache",
    "workloads": {
      "unindexed_scans": {
        "threads": "{calculated}",
        "target_ops_per_sec": 0
      },
      "aggregation_pipelines": {
        "threads": "{calculated}",
        "complexity": "high"
      }
    },
    "seeding": {
      "large_count": "{calculated_for_ram_overflow}",
      "agg_count": "{calculated_for_ram_overflow}",
      "hot_docs": 100
    },
    "primary_metrics": [
      "CACHE_USED_PERCENT",
      "CACHE_EVICTED_UNMODIFIED",
      "CACHE_EVICTED_MODIFIED",
      "EXTRA_INFO_PAGE_FAULTS"
    ],
    "secondary_metrics": [
      "DISK_PARTITION_IOPS_READ",
      "SYSTEM_CPU_IOWAIT"
    ],
    "calculation_formula": {
      "large_count": "int(server_ram_gb * 1.5 * 1e6 / 1024)",  # 1.5× RAM
      "threads": "client_cpu_cores * intensity * 6"
    }
  },
  
  "mixed_production": {
    "name": "Mixed Production Simulation",
    "description": "Realistic blend of all workload types",
    "workloads": {
      "mixed_blend": {
        "threads": "{calculated}",
        "seed": "{random}"
      }
    },
    "seeding": {
      "large_count": 1000000,
      "agg_count": 50000,
      "hot_docs": 100
    },
    "primary_metrics": [
      "OPCOUNTER_CMD",
      "OPCOUNTER_QUERY",
      "OPCOUNTER_INSERT",
      "OPCOUNTER_UPDATE"
    ],
    "secondary_metrics": [
      "SYSTEM_CPU_USER",
      "CACHE_USED_BYTES",
      "CONNECTIONS"
    ],
    "calculation_formula": {
      "threads": "client_cpu_cores * intensity * 6"
    }
  }
}
```

---

## Frontend Architecture (Modular JS)

### **Component Structure**

```javascript
// static/components/connection-manager.js
class ConnectionManager {
    constructor(apiClient) {
        this.api = apiClient;
        this.profiles = [];
        this.selectedProfile = null;
    }
    
    async loadProfiles() { /* ... */ }
    async createProfile(data) { /* ... */ }
    async testConnection(profileId) { /* ... */ }
    render() { /* ... */ }
}

// static/components/intent-designer.js
class IntentDesigner {
    constructor(apiClient) {
        this.api = apiClient;
        this.selectedIntent = null;
        this.intensity = 'medium';
        this.duration = 600;
        this.dataSize = '1m';
        this.concurrency = 10;
    }
    
    async calculateConfig() { /* ... */ }
    async previewImpact() { /* ... */ }
    renderKnobs() { /* ... */ }
    renderImpactPreview() { /* ... */ }
}

// static/components/knobs-panel.js
class KnobsPanel {
    constructor(config) {
        this.config = config;
        this.knobs = {
            intensity: { min: 0, max: 3, value: 1, labels: ['Light', 'Medium', 'Heavy', 'Extreme'] },
            duration: { min: 60, max: 86400, value: 600, log: true },
            dataSize: { min: 10000, max: 10000000, value: 1000000, log: true },
            concurrency: { min: 1, max: 100, value: 10 }
        };
    }
    
    render() { /* Visual slider rendering */ }
    onChange(callback) { /* Event handling */ }
    calculate() { /* Real-time impact calculation */ }
}

// static/components/metric-selector.js
class MetricSelector {
    constructor(apiClient) {
        this.api = apiClient;
        this.metrics = [];
        this.selected = [];
    }
    
    async loadMetrics() { /* ... */ }
    renderCheckboxList() { /* Grouped by category */ }
    async mapToWorkloads() { /* Call metric mapper API */ }
}

// static/components/live-monitor.js
class LiveMonitor {
    constructor(apiClient, runId) {
        this.api = apiClient;
        this.runId = runId;
        this.pollInterval = 10000; // 10s
    }
    
    async startPolling() { /* ... */ }
    async fetchMetrics() { /* Call Atlas API via backend */ }
    renderMetricTable() { /* Current vs baseline */ }
    renderProgress() { /* Progress bar */ }
}

// static/app.js (main orchestrator)
class App {
    constructor() {
        this.api = new APIClient('/api');
        this.connectionManager = new ConnectionManager(this.api);
        this.intentDesigner = new IntentDesigner(this.api);
        this.currentTab = 'connection';
    }
    
    async boot() {
        await this.connectionManager.loadProfiles();
        this.setupTabs();
        this.setupTheme();
        this.startLogPolling();
    }
}

const app = new App();
app.boot();
```

---

## Security Considerations

### **Connection URI Encryption**

```python
# core/connection_manager.py

from cryptography.fernet import Fernet
import os

class ConnectionManager:
    def __init__(self):
        # Generate key once, store in environment
        key = os.environ.get('LOADGEN_ENCRYPTION_KEY')
        if not key:
            key = Fernet.generate_key().decode()
            print(f"⚠️  Set LOADGEN_ENCRYPTION_KEY={key}")
        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
    
    def encrypt_uri(self, uri: str) -> bytes:
        return self.cipher.encrypt(uri.encode())
    
    def decrypt_uri(self, encrypted: bytes) -> str:
        return self.cipher.decrypt(encrypted).decode()
```

### **Atlas API Key Storage**

- Store in environment variables, NOT database
- Never log API keys
- Use separate read-only API user for monitoring

---

## Migration Path (V1 → V2)

### **Backward Compatibility**

V2 maintains full backward compatibility:

1. **Existing API endpoints** remain unchanged
2. **Old 3-tab UI** accessible at `/legacy`
3. **Manifest format** compatible (adds new fields)
4. **Workload modules** unchanged

### **Migration Steps**

1. **Data Migration**: No existing data to migrate (fresh install)
2. **Configuration**: Add new env vars (encryption key, Atlas API)
3. **Dependencies**: `pip install -r requirements.txt` (adds psutil, cryptography)
4. **Database Init**: Auto-create SQLite tables on first run
5. **UI**: New UI loads by default, old UI at `/legacy`

---

## Testing Strategy

### **Unit Tests**

```python
# tests/test_intent_engine.py
def test_read_performance_medium_intensity():
    engine = IntentEngine()
    hardware = {"cpu_cores": 12, "ram_gb": 24}
    server = {"max_connections": 3200, "ram_gb": 40, "vcpus": 16}
    
    config = engine.calculate(
        intent="read_performance",
        intensity="medium",
        duration=600,
        data_size="1m",
        hardware=hardware,
        server=server
    )
    
    assert config["workloads"]["indexed_reads"]["threads"] == 48  # 12 * 0.5 * 8
    assert config["seeding"]["large_count"] == 1000000
    assert "OPCOUNTER_QUERY" in config["primary_metrics"]
```

### **Integration Tests**

```python
# tests/test_e2e_intent_flow.py
async def test_full_intent_flow(test_client):
    # 1. Create connection profile
    resp = await test_client.post("/api/connections", json={
        "name": "Test",
        "uri": "mongodb://localhost:27017",
        "database_name": "test"
    })
    assert resp.status_code == 201
    profile_id = resp.json()["id"]
    
    # 2. Test connection (triggers discovery)
    resp = await test_client.post(f"/api/connections/{profile_id}/test")
    assert resp.json()["connection"]["ok"] == True
    
    # 3. Calculate intent config
    resp = await test_client.post("/api/intent/calculate", json={
        "intent": "read_performance",
        "intensity": "medium",
        "duration": 60
    })
    config = resp.json()["config"]
    assert "indexed_reads" in config["workloads"]
    
    # 4. Start run
    resp = await test_client.post("/api/runs", json={
        "connection_profile_id": profile_id,
        "intent_config": config
    })
    run_id = resp.json()["run_id"]
    
    # 5. Poll until done
    # ...
```

---

## Documentation Plan

### **User Documentation**

1. **Quick Start Guide** - 5-minute walkthrough
2. **Intent Types Explained** - Each intent with examples
3. **Metric Catalog Reference** - All 130+ metrics documented
4. **Atlas API Setup** - How to get API keys
5. **Troubleshooting Guide** - Common issues

### **Developer Documentation**

1. **Architecture Overview** - This document
2. **Module API Reference** - Autodoc from docstrings
3. **Adding New Intents** - Template + guide
4. **Adding New Metrics** - How to extend catalog
5. **Contributing Guide** - PR process

---

## Open Questions / Future Enhancements

### **Deferred to V2.1+**

1. **Metric-Driven Mode** - Full checkbox UI (Phase 9)
2. **Multi-Cluster Comparison** - Run same test on multiple clusters
3. **Historical Trend Analysis** - Compare runs over time
4. **Custom Workload Builder** - UI to create new workload types
5. **Export to JMeter/Gatling** - Convert test config to other formats
6. **Slack/PagerDuty Integration** - Alert on test failures
7. **CI/CD Integration** - GitHub Actions / Jenkins plugins
8. **Kubernetes Deployment** - Helm chart for distributed load testing

### **Research Needed**

1. **Atlas Vector Search Metrics** - If vector search is available
2. **Time Series Collections Metrics** - Time series specific metrics
3. **MongoDB 9.x Features** - Stay current with releases
4. **Queryable Encryption Overhead** - Test encrypted fields

---

## Summary

This design provides:

✅ **Modular architecture** for independent testing  
✅ **Intent-driven UX** for guided test creation  
✅ **Comprehensive metric catalog** (130+ metrics)  
✅ **Hard limits with overrides** for safety  
✅ **Atlas API integration** for live monitoring  
✅ **macOS compatibility** (already verified)  
✅ **Backward compatibility** with V1  
✅ **Clear implementation phases** (10-11 weeks)  
✅ **Extensive test coverage** strategy  
✅ **Future extensibility** (metric-driven mode ready)

**Next Step**: Approve design → Begin Phase 1 implementation.
