# MongoDB Load Test Platform V2 - Quick Start Guide

**Version**: 2.0.0-alpha  
**Date**: 2026-07-03  
**Status**: Core Complete (54% implemented)

---

## 🚀 What's New in V2

### **Connection-First Workflow**
- **Profile Management**: Save connection URIs in encrypted profiles
- **Auto-Discovery**: System detects client hardware (CPU, RAM, storage) and server specs (version, topology, max connections)
- **No More Manual URI Entry**: Select a profile, run tests

### **Intent-Based Test Designer**
Choose your testing goal, system proposes optimal configuration:
- **Connection Stress** - Hammer connection pool
- **Read Performance** - Benchmark indexed and unindexed queries
- **Write Throughput** - Max out write capacity
- **Aggregation Pipeline** - Test complex pipelines
- **Concurrency Contention** - Find lock contention limits
- **Cache Pressure** - Overflow cache to test disk I/O
- **Mixed Production** - Realistic blend workload
- **Custom** - Full manual control

### **Hardware-Aware Configuration**
- System calculates safe limits based on your MacBook/server
- Formula engine: `threads = client_cpu_cores * intensity_multiplier * 8`
- Intensity levels: light → medium → heavy → extreme
- Hard limits with expert override

### **130+ Metric Catalog**
- All Atlas Monitoring API metrics documented
- Each metric mapped to workloads that spike it
- Future: Metric-driven mode (V2.1) - check metrics, system tunes test

### **Atlas API Integration** (Coming Soon)
- Real-time metric polling during tests
- Live graphs in Tab 4
- Compare predicted vs actual impact

---

## 📦 Installation

### **1. Dependencies**
```bash
pip install -r requirements.txt
```

**New V2 Dependencies:**
- `psutil>=6.0,<7` - Hardware discovery
- `cryptography>=43.0,<44` - Fernet encryption
- `httpx>=0.27,<1` - Atlas API client

### **2. Encryption Key**
Generate Fernet key for encrypting connection URIs:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Export it:
```bash
export LOADGEN_ENCRYPTION_KEY="<your-fernet-key>"
```

Add to `~/.zshrc` or `~/.bashrc` to persist.

### **3. Initialize Database**
```bash
python -c "from db.models import Base; from db import get_engine; Base.metadata.create_all(get_engine())"
```

Creates SQLite database at `./loadtest.db` with:
- `connection_profiles` - Encrypted URI storage
- `run_history` - Test run logs
- `atlas_metrics` - Metric catalog (future)
- `metric_workload_map` - Reverse mapping (future)

---

## 🎯 Quick Start: Your First V2 Test

### **Step 1: Create Connection Profile**

Start the server:
```bash
uvicorn app:app --reload --port 8001
```

Open browser: `http://localhost:8001`

**Tab 1: Connection Manager**
1. Click "Add New Profile"
2. Fill in:
   - **Name**: "My Atlas Cluster"
   - **URI**: `mongodb+srv://...`
   - **Database**: `loadtest`
3. Click "Test Connection"
   - ✅ Connection OK
   - ✅ Permissions verified
   - ✅ Client hardware detected (12 cores, 24 GB RAM)
   - ✅ Server specs fetched (MongoDB 8.0.3, M30 Atlas tier)
4. Click "Save"

Profile is now stored with **encrypted URI**.

### **Step 2: Choose Intent** (Tab 2 - Future)

**For Now (Alpha)**: Use API directly

```bash
curl -X POST http://localhost:8001/api/intent/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "intent_id": "read_performance",
    "intensity": "medium",
    "duration_seconds": 600,
    "concurrency_level": 10,
    "client_hardware": {
      "summary": {"cpu_cores": 12, "ram_gb": 24.0}
    },
    "server_hardware": {
      "vcpus": 16, "ram_gb": 40, "max_connections": 3200
    }
  }'
```

**Response:**
```json
{
  "intent_id": "read_performance",
  "intensity": "medium",
  "workloads": {
    "indexed_reads": {"threads": 48},
    "unindexed_scans": {"threads": 24}
  },
  "seeding": {
    "large_count": 1000000,
    "agg_count": 100000
  },
  "primary_metrics": ["OPCOUNTER_QUERY", "QUERY_EXECUTOR_SCANNED"],
  "validation": {
    "ok": true,
    "warnings": [],
    "resource_usage": {
      "total_threads": 72,
      "estimated_ram_gb": 3.6
    }
  }
}
```

### **Step 3: Run Test** (Tab 3/4 - Future)

**For Now**: Use existing V1 API with calculated config:

```bash
curl -X POST http://localhost:8001/api/run \
  -H "Content-Type: application/json" \
  -d '{
    "uri": "mongodb+srv://...",
    "duration_seconds": 600,
    "workloads": {
      "indexed_reads": {"threads": 48},
      "unindexed_scans": {"threads": 24}
    },
    "auto_seed": true,
    "seed_params": {
      "large_count": 1000000,
      "agg_count": 100000
    }
  }'
```

Monitor in Tab 4 (existing UI).

---

## 🏗️ Architecture Overview

### **Directory Structure**
```
/core/
  connection_manager.py      # Profile CRUD with encryption
  hardware_discovery.py      # Auto-detect CPU/RAM/storage
  intent_engine.py           # Intent → configuration mapping
  workload_optimizer.py      # Optimize threads, batch sizes
  resource_validator.py      # Hard limits + override warnings
  atlas_client.py            # Atlas Monitoring API client

/api/
  connections.py             # REST: profile management
  discovery.py               # REST: hardware discovery
  intent.py                  # REST: intent calculator

/db/
  models.py                  # SQLAlchemy ORM
  __init__.py                # Database session

/data/
  atlas_metrics.json         # 130 metrics catalog
  intent_templates.json      # 8 pre-configured intents
  metric_workload_map.json   # Metric → workload reverse map
  hardware_profiles.json     # MacBooks, Atlas tiers, servers

/static/components/
  connection-manager.js      # Profile UI component

/tests/
  test_data_structures.py    # 19 unit tests
```

### **Data Flow**

1. **Connection** → Encrypted profile stored in SQLite
2. **Hardware Discovery** → Client specs cached in profile
3. **Intent Selection** → Intent engine calculates config
4. **Optimization** → Workload optimizer tunes parameters
5. **Validation** → Resource validator checks limits
6. **Run** → Existing V1 runner executes workloads
7. **Monitoring** → (Future) Atlas API polls metrics

---

## 📊 Available Intents

### **1. Connection Stress**
**Goal**: Test connection pooling limits  
**Workloads**: `connection_storm`  
**Seeding**: Minimal (100K docs)  
**Primary Metrics**: `CONNECTIONS`, `NETWORK_BYTES_IN`

**Example**: 200 connections opened/closed per second

---

### **2. Read Performance**
**Goal**: Benchmark query throughput  
**Workloads**: `indexed_reads`, `unindexed_scans`  
**Seeding**: 1M docs in `large_dataset`  
**Primary Metrics**: `OPCOUNTER_QUERY`, `QUERY_EXECUTOR_SCANNED`

**Intensity Scaling**:
- Light: 4 threads per core
- Medium: 8 threads per core
- Heavy: 12 threads per core
- Extreme: 16 threads per core

---

### **3. Write Throughput**
**Goal**: Max out write capacity  
**Workloads**: `write_bursts`  
**Seeding**: Minimal  
**Primary Metrics**: `OPCOUNTER_INSERT`, `OPCOUNTER_UPDATE`

**Batch Size**: Auto-calculated based on RAM  
Formula: `available_ram_gb * 0.1 * 1024 / doc_size_kb`

---

### **4. Aggregation Pipeline**
**Goal**: Test complex pipelines (groupBy, unwind, etc.)  
**Workloads**: `aggregation_pipelines`  
**Seeding**: 500K docs with nested arrays  
**Primary Metrics**: `OPCOUNTER_COMMAND`, `QUERY_EXECUTOR_SCANNED`

---

### **5. Concurrency Contention**
**Goal**: Find lock contention limits  
**Workloads**: `update_contention` (hot document set)  
**Seeding**: 10K hot docs  
**Primary Metrics**: `TICKETS_AVAILABLE_WRITE`, `GLOBAL_LOCK_CURRENT_QUEUE_WRITERS`

---

### **6. Cache Pressure**
**Goal**: Overflow WiredTiger cache to test disk I/O  
**Workloads**: `indexed_reads`, `unindexed_scans`  
**Seeding**: **5x server RAM** (e.g., 200 GB for M30)  
**Primary Metrics**: `CACHE_BYTES_READ_INTO`, `CACHE_DIRTY_BYTES`

**Warning**: Seeding takes 10-60 minutes depending on cluster size.

---

### **7. Mixed Production**
**Goal**: Realistic blend (80% reads, 15% writes, 5% aggregations)  
**Workloads**: `mixed_blend` (composite workload)  
**Seeding**: 1M docs  
**Primary Metrics**: All categories

---

### **8. Custom**
**Goal**: Full manual control  
**Workloads**: User-selected  
**Seeding**: User-defined  
**Primary Metrics**: None pre-selected

Use this for experimenting with specific workload combinations.

---

## 🔒 Security Features

### **Encryption**
- **URIs**: Fernet symmetric encryption
- **Atlas API Keys**: Fernet encryption
- **Key Storage**: Environment variable (`LOADGEN_ENCRYPTION_KEY`)

### **UI**
- Passwords masked in connection form
- Credentials never logged
- Profile names shown, URIs hidden

### **Database**
- SQLite file at `./loadtest.db`
- Set file permissions: `chmod 600 loadtest.db`

---

## 🧪 Testing

### **Unit Tests**
```bash
python tests/test_data_structures.py
```

**19 tests covering:**
- Metric catalog structure
- Intent template validation
- Workload mapping consistency
- Hardware profile schema

### **Integration Test (Connection)**
```bash
# In Python REPL
from core.hardware_discovery import HardwareDiscovery
print(HardwareDiscovery.get_full_profile())
```

**Expected Output (macOS)**:
```json
{
  "cpu": {"cores": 12, "threads": 12, "model": "Apple M2"},
  "memory": {"total_gb": 24.0, "available_gb": 18.5},
  "disk": {"free_gb": 314, "total_gb": 460},
  "network": {"max_speed_mbps": 1000},
  "platform": {"system": "Darwin", "release": "25.5.0"}
}
```

---

## 📈 Monitoring

### **V1 Monitoring (Current)**
- **Tab 4**: Real-time log stream
- **Manifest**: JSON summary after run
- **Grafana**: (manual setup)

### **V2 Monitoring (Future)**
- **Tab 4 Enhanced**: Live Atlas metric graphs
- **Primary Metrics Panel**: Intent-specific metrics highlighted
- **Secondary Metrics**: Collapsible panel
- **Atlas API**: Real-time polling every 60 seconds

---

## 🛠️ Configuration

### **Environment Variables**
```bash
export LOADGEN_ENCRYPTION_KEY="<fernet-key>"    # Required
export LOADGEN_OUTPUT_DIR="./runs"             # Optional
export LOADGEN_DB="loadtest"                   # Optional
export ATLAS_PUBLIC_KEY="<your-key>"           # Optional (for Atlas API)
export ATLAS_PRIVATE_KEY="<your-secret>"       # Optional
export ATLAS_PROJECT_ID="<project-id>"         # Optional
```

### **Hardware Limits**
System calculates these automatically:

- **Max Threads**: `(cpu_cores - 2) * 10`
- **Max Connections**: `server_max_connections * 0.8`
- **Max Memory**: `ram_gb * 0.8`

**Override**: Set `allow_overrides: true` in API requests.

**Warning**: Overriding limits can cause:
- CPU oversubscription (thread starvation)
- Memory swapping (severe perf degradation)
- Connection pool exhaustion

---

## 🐛 Troubleshooting

### **"Encryption key not found"**
```bash
export LOADGEN_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

### **"No profile found"**
Check database:
```bash
sqlite3 loadtest.db "SELECT id, name FROM connection_profiles;"
```

If empty, create profile via UI or API.

### **Hardware discovery returns 0 cores**
macOS Sonoma+ may restrict `psutil`. Grant Terminal/iTerm full disk access:
`System Settings → Privacy & Security → Full Disk Access → +Terminal`

### **Connection test fails**
- Check URI format: `mongodb+srv://user:pass@cluster.mongodb.net/dbname`
- Verify network access in Atlas (IP whitelist)
- Check auth source (usually `admin` for Atlas)

---

## 📚 Resources

### **Documentation**
- [DESIGN_V2.md](DESIGN_V2.md) - Full 71-page architecture doc
- [PROGRESS_REPORT.md](PROGRESS_REPORT.md) - Implementation status
- [README.md](README.md) - Original V1 docs

### **Data Files**
- [data/atlas_metrics.json](data/atlas_metrics.json) - 130 metrics catalog
- [data/intent_templates.json](data/intent_templates.json) - Intent configs
- [data/hardware_profiles.json](data/hardware_profiles.json) - Hardware specs

### **MongoDB Docs**
- [Atlas Monitoring API](https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Monitoring-and-Logs)
- [serverStatus Reference](https://www.mongodb.com/docs/manual/reference/command/serverStatus/)
- [FTDC Metrics](https://www.mongodb.com/docs/manual/administration/analyzing-mongodb-performance/)

---

## 🗺️ Roadmap

### **Alpha (Current - 54% Complete)**
- ✅ Connection profiles with encryption
- ✅ Hardware auto-discovery
- ✅ Intent engine (8 intents)
- ✅ Workload optimizer + validator
- ✅ 130-metric catalog
- ⏳ Atlas API client (foundation ready)

### **Beta (Next)**
- Tab 2 UI: Intent Designer with knobs
- Tab 3 UI: Advanced configuration
- Tab 4 UI: Live Atlas metrics
- Metric-driven mode (V2.1)
- Atlas Search workload integration

### **v2.0.0 Release**
- Full UI integration
- Documentation
- macOS end-to-end tested
- Performance tuning
- UAT complete

### **v2.1+ (Future)**
- Metric checkbox mode (130+ metrics)
- Multi-cluster comparison
- Historical trend analysis
- Custom workload builder UI

---

## 💡 Tips & Best Practices

### **Seeding**
- **Connection Stress**: Minimal seeding (100K docs)
- **Read Performance**: 1M docs for realistic benchmarks
- **Cache Pressure**: 5x server RAM (WARNING: slow to seed)
- **Aggregation**: 500K docs with nested arrays

### **Intensity Levels**
- **Light**: Safe for production clusters (20-40% load)
- **Medium**: Standard benchmark (60-70% load)
- **Heavy**: Stress test (80-90% load)
- **Extreme**: Maximum capacity test (may cause alerts)

### **Duration**
- **Quick Test**: 60 seconds (connection validation)
- **Standard**: 600 seconds (10 min - captures steady state)
- **Endurance**: 3600+ seconds (1+ hour - stability test)

### **macOS Performance**
- Run on AC power (avoid throttling)
- Close heavy apps (browsers, IDEs)
- Monitor Activity Monitor during tests
- M1/M2/M3 chips: Use Efficiency + Performance cores

### **Atlas Clusters**
- **M0/M2/M5**: Light intensity only
- **M10-M30**: Medium intensity safe
- **M40+**: Heavy/extreme OK
- **Dedicated**: Full control

---

## 🎓 Examples

### **Example 1: Benchmark M30 Read Performance**
```bash
curl -X POST http://localhost:8001/api/intent/calculate \
  -d '{
    "intent_id": "read_performance",
    "intensity": "medium",
    "duration_seconds": 600,
    "client_hardware": {"summary": {"cpu_cores": 12, "ram_gb": 24}},
    "server_hardware": {"vcpus": 16, "ram_gb": 40, "max_connections": 3200}
  }'
```

**Result**: 48 indexed_reads threads, 24 unindexed_scans threads

---

### **Example 2: Stress Test Connection Pool**
```bash
curl -X POST http://localhost:8001/api/intent/calculate \
  -d '{
    "intent_id": "connection_stress",
    "intensity": "heavy",
    "duration_seconds": 300,
    "client_hardware": {"summary": {"cpu_cores": 12, "ram_gb": 24}},
    "server_hardware": {"max_connections": 3200}
  }'
```

**Result**: 2,560 connections (80% of max)

---

### **Example 3: Cache Pressure Test (Extreme)**
```bash
curl -X POST http://localhost:8001/api/intent/calculate \
  -d '{
    "intent_id": "cache_pressure",
    "intensity": "extreme",
    "duration_seconds": 1800,
    "client_hardware": {"summary": {"cpu_cores": 12, "ram_gb": 24}},
    "server_hardware": {"ram_gb": 40}
  }'
```

**Result**: 200 GB seeding (5x RAM), 96 threads reading

---

## 🤝 Contributing

V2 is under active development. Core features working, UI in progress.

**Current Focus**: Tab 2/3/4 UI components

**Next Sprint**: Atlas API live polling

---

## 📞 Support

- **Issues**: GitHub Issues
- **Docs**: This file + DESIGN_V2.md
- **Tests**: Run `python tests/test_data_structures.py`

---

**Generated**: 2026-07-03  
**Version**: 2.0.0-alpha  
**Status**: Core Complete (54%)
