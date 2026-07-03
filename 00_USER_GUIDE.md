# MongoDB Load Test Platform V2 - User Guide

**Version**: 2.0.0  
**Last Updated**: 2026-07-03

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [UI Walkthrough](#ui-walkthrough)
5. [Intent-Based Testing](#intent-based-testing)
6. [Advanced Features](#advanced-features)
7. [Atlas API Integration](#atlas-api-integration)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [FAQ](#faq)

---

## Introduction

The MongoDB Load Test Platform V2 is a **hardware-aware, intent-based load testing tool** designed to help you:

- **Benchmark MongoDB performance** under realistic workloads
- **Stress test Atlas clusters** to find capacity limits
- **Validate infrastructure changes** before production
- **Generate reproducible test results** with detailed metrics

### What's New in V2?

- ✨ **Connection-First Workflow**: Save encrypted profiles, no more manual URI entry
- 🧠 **Intent-Based Designer**: Choose your goal (e.g., "Read Performance"), system configures optimal workload
- 🖥️ **Auto-Discovery**: Detects client hardware (CPU, RAM, storage) and server specs
- 📊 **130 Metrics Cataloged**: All Atlas Monitoring API metrics documented
- 🔒 **Encrypted Storage**: Fernet encryption for URIs and API keys
- ⚡ **Hardware-Aware Limits**: Safe defaults with expert override

---

## Installation

### Prerequisites

- **Python**: 3.10 or higher
- **MongoDB**: Connection to MongoDB 4.4+ or Atlas M10+
- **OS**: macOS, Linux, or Windows (WSL2)

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd mdb-loadtest-main
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

**New V2 Dependencies**:
- `psutil` - Hardware discovery
- `cryptography` - Fernet encryption
- `httpx` - Atlas API client

### Step 3: Generate Encryption Key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output (e.g., `gAAAAAB...`) and export it:

```bash
export LOADGEN_ENCRYPTION_KEY="<your-key-here>"
```

**Persist it** in your shell profile:

```bash
echo 'export LOADGEN_ENCRYPTION_KEY="<your-key>"' >> ~/.zshrc  # or ~/.bashrc
source ~/.zshrc
```

### Step 4: Initialize Database

```bash
python3 -c "from db.models import Base; from db import get_engine; Base.metadata.create_all(get_engine())"
```

Creates `./loadtest.db` (SQLite) with:
- `connection_profiles` table
- `run_history` table
- Encrypted storage ready

### Step 5: Start Server

```bash
uvicorn app:app --reload --port 8001
```

Open browser: `http://localhost:8001`

---

## Quick Start

### 1. Create Connection Profile (Tab 1)

1. **Click "Add New Profile"**
2. **Fill in details**:
   - **Name**: "My Atlas Cluster"
   - **URI**: `mongodb+srv://user:pass@cluster.mongodb.net/`
   - **Database**: `loadtest`
   - **Auth Source**: `admin` (default)

3. **Click "Test Connection"**
   - ✅ Connection verified
   - ✅ Permissions checked (read/write)
   - ✅ Client hardware detected (12 cores, 24 GB RAM)
   - ✅ Server specs fetched (MongoDB 8.0.3, M30 tier)

4. **Click "Save"**

Profile is now **encrypted and stored** in SQLite.

### 2. Choose Intent (Tab 2)

1. **Select an intent card** (e.g., "Read Performance")
2. **Adjust parameters**:
   - **Intensity**: Medium (60-70% load)
   - **Duration**: 600 seconds (10 minutes)
   - **Concurrency**: 10

3. **Click "Calculate Configuration"**

System calculates:
- **Workloads**: indexed_reads (48 threads), unindexed_scans (24 threads)
- **Seeding**: 1M docs in `large_dataset`
- **Validation**: ✅ Within limits (72 threads < 100 max)

4. **Click "Run Test"**

Test starts, switches to Tab 4 for monitoring.

### 3. Monitor Run (Tab 4)

- **Real-time logs** stream to UI
- **Run status**: queued → seeding → running → done
- **Manifest**: Download JSON results when complete

---

## UI Walkthrough

### Tab 1: Connection Manager

**Purpose**: Manage connection profiles and view discovery results.

**Components**:

1. **Profile Selector**
   - List of saved profiles
   - Radio button selection
   - Click profile to view details

2. **Profile Form**
   - Add new profile
   - Edit existing profile
   - Delete profile

3. **Discovery Results**
   - **Client**: CPU cores, RAM, storage, network
   - **Server**: Version, topology, max connections
   - **Capabilities**: Recommended limits (max threads, max connections)

**Actions**:
- **Add Profile**: Click "Add New Profile"
- **Test**: Click "Test Connection" to verify + auto-discover
- **Edit**: Select profile, click "Edit"
- **Delete**: Select profile, click "Delete" (confirmation required)

---

### Tab 2: Intent Designer

**Purpose**: Choose testing goal and configure parameters.

**Components**:

1. **Intent Grid**
   - 8 pre-configured intents
   - Visual cards with icons
   - Click to select

2. **Knobs Panel** (appears after selection)
   - **Intensity**: light | medium | heavy | extreme
   - **Duration**: 60-7200 seconds
   - **Concurrency**: 1-50 (slider)

3. **Configuration Preview**
   - JSON configuration displayed
   - Validation warnings shown
   - Resource usage summary

**Actions**:
- **Select Intent**: Click intent card
- **Adjust Knobs**: Change intensity, duration, concurrency
- **Calculate**: Click "Calculate Configuration"
- **Run**: Click "Run Test" (after calculation)

---

### Tab 3: Advanced Configuration (Legacy V1)

**Purpose**: Manual workload selection and configuration.

**Use this when**:
- You need full control over every parameter
- Custom workload combinations
- Expert mode

---

### Tab 4: Run Monitoring

**Purpose**: Monitor live test runs and view results.

**Components**:

1. **Run Status**
   - Run ID
   - Status (queued | seeding | running | done | failed)
   - Phase details

2. **Real-Time Logs**
   - Auto-scrolling log stream
   - Color-coded (info | success | warning | error)

3. **Results** (after completion)
   - Manifest link
   - Opcounter deltas
   - Workload summaries

---

## Intent-Based Testing

### Available Intents

#### 1. Connection Stress 🔌
**Goal**: Test connection pool limits

**Workloads**:
- `connection_storm`: Rapid open/close connections

**Best For**:
- Connection pooling issues
- Max connections tuning
- Network throughput testing

**Recommended**:
- Duration: 300 seconds (5 min)
- Intensity: medium → heavy

**Metrics to Watch**:
- `CONNECTIONS`
- `CONNECTIONS_AVAILABLE`
- `NETWORK_NUM_REQUESTS`

---

#### 2. Read Performance 📖
**Goal**: Benchmark query throughput

**Workloads**:
- `indexed_reads`: Query with indexed fields
- `unindexed_scans`: Full collection scans

**Best For**:
- Index effectiveness testing
- Query optimization
- Read scalability

**Recommended**:
- Duration: 600 seconds (10 min)
- Intensity: medium
- Seeding: 1M docs

**Metrics to Watch**:
- `OPCOUNTER_QUERY`
- `QUERY_EXECUTOR_SCANNED`
- `QUERY_TARGETING_SCANNED_PER_RETURNED`

---

#### 3. Write Throughput ✍️
**Goal**: Max out write capacity

**Workloads**:
- `write_bursts`: Batch inserts

**Best For**:
- Write capacity planning
- Checkpoint tuning
- Disk I/O testing

**Recommended**:
- Duration: 600 seconds (10 min)
- Intensity: heavy
- Batch size: Auto-calculated (based on RAM)

**Metrics to Watch**:
- `OPCOUNTER_INSERT`
- `DISK_PARTITION_IOPS_WRITE`
- `CACHE_DIRTY_BYTES`

---

#### 4. Aggregation Pipeline 🔄
**Goal**: Test complex aggregations

**Workloads**:
- `aggregation_pipelines`: groupBy, unwind, sort

**Best For**:
- Analytics workload testing
- CPU-heavy operations
- Memory usage profiling

**Recommended**:
- Duration: 600 seconds (10 min)
- Intensity: medium
- Seeding: 500K docs with nested arrays

**Metrics to Watch**:
- `SYSTEM_CPU_USER`
- `QUERY_EXECUTOR_SCANNED`
- `CACHE_BYTES_READ_INTO`

---

#### 5. Concurrency Contention 🔒
**Goal**: Find lock contention limits

**Workloads**:
- `update_contention`: Hammer hot documents

**Best For**:
- Write conflict testing
- Lock contention profiling
- Ticket utilization

**Recommended**:
- Duration: 600 seconds (10 min)
- Intensity: heavy
- Hot docs: 10K

**Metrics to Watch**:
- `OPERATIONS_WRITE_CONFLICTS`
- `TICKETS_AVAILABLE_WRITES`
- `GLOBAL_LOCK_CURRENT_QUEUE_WRITERS`

---

#### 6. Cache Pressure 💾
**Goal**: Test behavior when cache overflows

**Workloads**:
- `indexed_reads` + `unindexed_scans` (heavy threads)

**Best For**:
- Disk I/O fallback testing
- Eviction behavior profiling
- Out-of-RAM scenarios

**Recommended**:
- Duration: 900 seconds (15 min)
- Intensity: extreme
- Seeding: **5x server RAM** (e.g., 200 GB for M30)

**WARNING**: Seeding takes 10-60 minutes!

**Metrics to Watch**:
- `CACHE_USED_PERCENT`
- `CACHE_EVICTED_UNMODIFIED`
- `EXTRA_INFO_PAGE_FAULTS`

---

#### 7. Mixed Production 🎯
**Goal**: Realistic blend of all workload types

**Workloads**:
- `mixed_blend`: 80% reads, 15% writes, 5% agg

**Best For**:
- Production simulation
- Capacity planning
- Pre-production validation

**Recommended**:
- Duration: 1200 seconds (20 min)
- Intensity: medium
- Seeding: 1M docs

**Metrics to Watch**:
- All categories (composite view)

---

#### 8. Custom ⚙️
**Goal**: Full manual control

**Workloads**:
- User-selected

**Best For**:
- Advanced users
- Specific test scenarios
- Research

---

## Advanced Features

### Hardware Discovery

**Automatic Detection**:
- CPU: Cores, threads, model
- RAM: Total, available
- Disk: Free space, total capacity, usage %
- Network: Max speed (Mbps)

**Use Cases**:
- Calculate safe thread limits
- Optimize batch sizes
- Recommend configurations

**API**:
```bash
curl http://localhost:8001/api/discovery/hardware
```

**Response**:
```json
{
  "summary": {
    "cpu_cores": 12,
    "cpu_threads": 12,
    "ram_gb": 24.0,
    "storage_gb": 314,
    "network_speed_mbps": 1000
  },
  "recommended_limits": {
    "max_threads": 100,
    "max_connections": 1200,
    "max_concurrent_ops": 240000
  }
}
```

---

### Resource Validation

**Hard Limits**:
- **Max Threads**: `(cpu_cores - 2) * 10`
- **Max Connections**: `server_max_connections * 0.8`
- **Max Memory**: `ram_gb * 0.8`

**Override Mode**:
Set `allow_overrides: true` in API requests to bypass limits.

**Warnings**:
```
⚠️  Total threads (120) exceeds recommended limit (100)
⚠️  Risk: CPU oversubscription may cause thread starvation
⚠️  OVERRIDE: User explicitly allowed exceeding limits
```

---

### Workload Optimizer

**Per-Workload Multipliers**:
- `indexed_reads`: 1.2 (CPU-efficient, can oversubscribe)
- `unindexed_scans`: 0.9 (I/O bound)
- `inmemory_sorts`: 0.8 (memory-intensive)
- `update_contention`: 1.1 (benefits from contention)

**Batch Size Optimization**:
Formula: `available_ram_gb * 0.1 * 1024 / doc_size_kb`

**Target Ops Calculation**:
Only throttles specific workloads (e.g., connection_storm to avoid overwhelming server).

---

## Atlas API Integration

**Setup**:

1. **Get Atlas API Keys**:
   - Go to Atlas → Access Manager → API Keys
   - Create key with "Project Read Only" role
   - Copy public key + private key

2. **Add to Profile**:
   - Edit profile in Tab 1
   - Click "Atlas API Settings"
   - Paste public key, private key, group ID
   - Keys stored **encrypted**

3. **Enable Live Monitoring**:
   - During test run, Atlas metrics polled every 60 seconds
   - Displayed in Tab 4 (future feature)

**API Client**:
```python
from core.atlas_client import AtlasClient

client = AtlasClient(
    public_key="<your-public-key>",
    private_key="<your-private-key>",
    group_id="<project-id>"
)

metrics = client.get_process_metrics(
    cluster_name="MyCluster",
    host="cluster0-shard-00-00.mongodb.net",
    port=27017,
    metrics=["CONNECTIONS", "OPCOUNTER_QUERY"],
    granularity="PT1M",
    period="PT10M"
)
```

---

## Troubleshooting

### "Encryption key not found"

**Symptom**: App crashes on startup with `InvalidToken` error

**Fix**:
```bash
export LOADGEN_ENCRYPTION_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

Add to `~/.zshrc` to persist.

---

### "No profile found"

**Symptom**: Profile list empty after restart

**Fix**: Check database:
```bash
sqlite3 loadtest.db "SELECT id, name FROM connection_profiles;"
```

If empty, create profile via UI.

---

### Hardware discovery returns 0 cores

**Symptom**: Discovery shows 0 cores or fails

**Fix (macOS Sonoma+)**:
Grant Full Disk Access:
1. System Settings → Privacy & Security → Full Disk Access
2. Add Terminal/iTerm
3. Restart terminal

---

### Connection test fails

**Symptom**: "Connection failed" in UI

**Fixes**:
1. **Check URI format**: `mongodb+srv://user:pass@cluster.mongodb.net/dbname`
2. **Verify IP whitelist** in Atlas (Network Access)
3. **Check auth source** (usually `admin` for Atlas)
4. **Test with mongo shell**:
   ```bash
   mongosh "mongodb+srv://..."
   ```

---

### Seeding takes too long

**Symptom**: Seeding stuck for > 30 minutes

**Fixes**:
1. **Reduce seeding size**: 1M docs = ~5-10 minutes
2. **Check network speed**: Slow uplink delays seeding
3. **Use auto-seed during run**: Faster than separate seeding step

---

## Best Practices

### Seeding

- **Connection Stress**: 100K docs (minimal)
- **Read Performance**: 1M docs
- **Write Throughput**: Minimal (workload generates data)
- **Aggregation**: 500K docs with nested arrays
- **Cache Pressure**: 5x server RAM (WARNING: slow!)

### Intensity Levels

- **Light** (20-40% load): Safe for production clusters, UAT
- **Medium** (60-70% load): Standard benchmarking
- **Heavy** (80-90% load): Stress testing, capacity planning
- **Extreme** (max capacity): Find breaking point (may trigger alerts)

### Duration

- **Quick Test** (60s): Connection validation, smoke test
- **Standard** (600s / 10 min): Captures steady state, typical benchmark
- **Endurance** (3600s+ / 1 hour+): Stability testing, leak detection

### macOS Performance

- **AC Power**: Run on AC (avoid CPU throttling)
- **Close Apps**: Free up RAM and CPU
- **Monitor**: Use Activity Monitor to watch resource usage
- **M1/M2/M3**: Leverage both Efficiency + Performance cores

### Atlas Clusters

- **M0/M2/M5**: Light intensity only (free/shared tier limits)
- **M10-M30**: Medium intensity safe
- **M40+**: Heavy/extreme OK
- **Dedicated**: Full control

---

## FAQ

### Q: Can I test against replica sets?

**A**: Yes! Provide replica set URI:
```
mongodb://host1:27017,host2:27017,host3:27017/?replicaSet=rs0
```

Discovery will detect topology automatically.

---

### Q: Does this work with MongoDB 4.4?

**A**: Yes, compatible with MongoDB 4.4+. Some metrics require 5.0+.

---

### Q: Can I run multiple tests concurrently?

**A**: Yes, each test runs in background thread. Multiple tests can run simultaneously.

---

### Q: How do I export results?

**A**: After test completes:
1. Go to `./runs/run_<timestamp>_<id>/`
2. Download `manifest.json`
3. Contains full config, results, opcounter deltas

---

### Q: Can I schedule recurring tests?

**A**: Yes, use V1 scheduler feature (Tab 3 → Schedule).

---

### Q: Does this support sharded clusters?

**A**: Yes, discovery detects sharded topology. Workloads run against mongos.

---

### Q: Can I test Atlas Search?

**A**: Partial support. Atlas Search metrics documented, but workload generators for Search not yet implemented (roadmap: v2.2).

---

### Q: How do I compare results between runs?

**A**: Compare `manifest.json` files:
- Opcounter deltas
- Ops/sec per workload
- Resource usage

Future: Built-in comparison tool (v2.1).

---

### Q: Is this safe for production?

**A**: Depends:
- **Light intensity**: Generally safe
- **Medium+**: Only on pre-production or during maintenance windows
- **Extreme**: Never on production

---

### Q: Can I contribute workloads?

**A**: Yes! Workloads are Python functions. See `workloads/` directory for examples.

---

## Next Steps

- **Read DESIGN_V2.md**: Full architecture documentation
- **Check CHANGELOG_V2.md**: Release notes and features
- **Run integration tests**: `python3 tests/test_integration.py`
- **Explore APIs**: See V2_QUICKSTART.md for API examples

---

**Need Help?**  
- GitHub Issues: <repository-url>/issues
- Documentation: DESIGN_V2.md, V2_QUICKSTART.md

**Generated**: 2026-07-03  
**Version**: 2.0.0
