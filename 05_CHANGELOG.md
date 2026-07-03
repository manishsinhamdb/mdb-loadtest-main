# V2 Changelog

## [2.0.0-alpha] - 2026-07-03

### 🎉 Major Features

#### Connection Management
- **Profile-based workflow**: Save connection URIs in encrypted profiles
- **Auto-discovery**: Detect client hardware (CPU, RAM, storage, network) and server specs (version, topology, max connections)
- **Fernet encryption**: URIs and Atlas API keys stored encrypted in SQLite
- **CRUD API**: REST endpoints for profile management
- **UI Component**: Reusable connection-manager.js with neon theme

#### Intent-Based Configuration
- **8 pre-configured intents**:
  - Connection Stress
  - Read Performance
  - Write Throughput
  - Aggregation Pipeline
  - Concurrency Contention
  - Cache Pressure
  - Mixed Production
  - Custom
- **Formula evaluation engine**: Dynamic parameter calculation (e.g., `threads = cpu_cores * intensity_multiplier * 8`)
- **Intensity levels**: light → medium → heavy → extreme
- **Hardware-aware**: Adapts to detected client/server specs

#### Resource Management
- **Workload Optimizer**: Tunes threads, batch sizes, target ops per workload
- **Resource Validator**: Hard limits with override warnings
  - Max threads: `(cpu_cores - 2) * 10`
  - Max connections: `server_max_connections * 0.8`
  - Max memory: `ram_gb * 0.8`
- **Safety overrides**: Expert mode with clear risk warnings

#### Metric Catalog
- **130 metrics documented** across 10 categories:
  - Hardware System (CPU, RAM, disk)
  - Connections & Network
  - Operations (opcounters)
  - Query Performance
  - Cache (WiredTiger)
  - Replication
  - Database Storage
  - Asserts & Errors
  - Atlas Search
  - Process & Server
- **Reverse mapping**: metric → workload (for future metric-driven mode)
- **Baseline + thresholds**: Each metric has alert thresholds and impact levels

#### Atlas API Integration (Foundation)
- **Atlas API Client**: Poll real-time metrics during test runs
- **Digest authentication**: Support for Atlas public/private keys
- **Process metrics**: Fetch per-process metrics
- **Cluster metrics**: Aggregate metrics across cluster
- **Search metrics**: Atlas Search index metrics
- **Polling callback**: Real-time metric streaming during tests

#### Hardware Discovery
- **Cross-platform**: macOS, Linux, Windows via psutil
- **Auto-detects**:
  - CPU cores, threads, model
  - RAM (total, available)
  - Disk (free, total, usage %)
  - Network (max speed)
  - Platform info (OS, version)
- **Recommended limits**: Calculates safe limits per machine
- **Tested on macOS**: Verified on M2 MacBook (12 cores, 24 GB RAM)

### 📦 New Dependencies
- `psutil>=6.0,<7` - Hardware discovery
- `cryptography>=43.0,<44` - Fernet encryption
- `httpx>=0.27,<1` - Atlas API client

### 🗂️ New Files

#### Core Modules
- `core/connection_manager.py` - Profile CRUD with encryption
- `core/hardware_discovery.py` - Auto-detect client hardware
- `core/intent_engine.py` - Intent → configuration mapping
- `core/workload_optimizer.py` - Optimize threads, batch sizes
- `core/resource_validator.py` - Hard limits + override warnings
- `core/atlas_client.py` - Atlas Monitoring API client

#### API Endpoints
- `api/connections.py` - REST: profile management
- `api/discovery.py` - REST: hardware discovery
- `api/intent.py` - REST: intent calculator

#### Database
- `db/models.py` - SQLAlchemy ORM (ConnectionProfile, RunHistory, AtlasMetric, MetricWorkloadMap)
- `db/__init__.py` - Database session and engine

#### Data Catalogs
- `data/atlas_metrics.json` - 130 metrics catalog
- `data/intent_templates.json` - 8 pre-configured intents
- `data/metric_workload_map.json` - Metric → workload reverse map
- `data/hardware_profiles.json` - MacBooks, Atlas tiers, servers

#### Frontend Components
- `static/components/connection-manager.js` - Profile UI component

#### Tests
- `tests/test_data_structures.py` - 19 unit tests (all passing)

#### Documentation
- `DESIGN_V2.md` - 71-page architecture document
- `V2_QUICKSTART.md` - Quick start guide
- `PROGRESS_REPORT.md` - Implementation status
- `CHANGELOG_V2.md` - This file

### 🔧 Modified Files

#### Backend
- `app.py` - Added V2 routers (connections, discovery, intent)
- `requirements.txt` - Added psutil, cryptography, httpx

#### Frontend
- `static/index.html` - Replaced Tab 1 with connection profile manager
- `static/app.js` - Added ConnectionManager initialization
- `static/style.css` - Added profile UI styles (neon theme)

### ✅ Testing
- **19 unit tests** covering:
  - Metric catalog structure
  - Intent template validation
  - Workload mapping consistency
  - Hardware profile schema
  - Cross-file consistency
- **Integration tested** on macOS (M2 MacBook)
- **All tests passing**: `pytest tests/test_data_structures.py`

### 🔒 Security
- **URI encryption**: Fernet symmetric encryption
- **API key encryption**: Atlas credentials encrypted
- **Password masking**: UI never shows sensitive data
- **Key storage**: Environment variable (`LOADGEN_ENCRYPTION_KEY`)
- **Database permissions**: Recommended `chmod 600 loadtest.db`

### 🎨 UI/UX
- **Neon theme consistency**: All V2 components match existing style
- **Profile selector**: Radio buttons with visual feedback
- **Discovery results**: Client + server specs displayed with capability grid
- **Backward compatible**: V1 features still accessible via legacy mode
- **Tab 1 redesigned**: Connection-first workflow

### 📊 Performance
- **Hardware-aware limits**: Prevents CPU oversubscription
- **Workload-specific multipliers**: Optimizes per-workload characteristics
- **Batch size optimization**: Based on available RAM
- **Connection pooling**: Respects server limits

### 🚀 API Enhancements

#### New Endpoints
```
GET  /api/connections          - List all connection profiles
POST /api/connections          - Create new profile
GET  /api/connections/:id      - Get profile by ID
PUT  /api/connections/:id      - Update profile
DELETE /api/connections/:id    - Delete profile
POST /api/connections/:id/test - Test connection + auto-discovery

GET  /api/discovery/hardware   - Get client hardware profile

GET  /api/intent/types         - List available intents
POST /api/intent/calculate     - Calculate config from intent
GET  /api/intent/preview/:id   - Preview intent impact
```

### 📝 Configuration

#### Environment Variables
```bash
export LOADGEN_ENCRYPTION_KEY="<fernet-key>"    # Required
export LOADGEN_OUTPUT_DIR="./runs"             # Optional
export LOADGEN_DB="loadtest"                   # Optional
export ATLAS_PUBLIC_KEY="<your-key>"           # Optional (for Atlas API)
export ATLAS_PRIVATE_KEY="<your-secret>"       # Optional
export ATLAS_PROJECT_ID="<project-id>"         # Optional
```

### 🐛 Bug Fixes
- Fixed metric count mismatch (131 → 130 actual metrics)
- Fixed workload validation logic (collect from all intents)
- Fixed import paths in api/connections.py

### 📚 Documentation
- **DESIGN_V2.md**: Complete architecture (71 pages)
- **V2_QUICKSTART.md**: Installation and usage guide
- **PROGRESS_REPORT.md**: Implementation status (54% complete)
- **Inline comments**: All new modules fully documented

### 🗺️ Roadmap

#### Completed (54%)
- ✅ Phase 1: Foundation (data catalogs, database schema)
- ✅ Phase 2: Connection Manager (backend + frontend)
- ✅ Phase 3: Hardware Discovery (cross-platform)
- ✅ Phase 4: Intent Engine (8 intents, optimizer, validator)
- ✅ Phase 5-6: Metric Catalog + Atlas API (foundation)

#### In Progress (46%)
- ⏳ Tab 2 UI: Intent Designer with knobs
- ⏳ Tab 3 UI: Advanced configuration
- ⏳ Tab 4 UI: Live Atlas metrics
- ⏳ Metric-driven mode (V2.1)
- ⏳ Integration tests
- ⏳ Documentation polish

#### Future (v2.1+)
- Metric checkbox mode (130+ metrics)
- Multi-cluster comparison
- Historical trend analysis
- Custom workload builder UI
- Slack/PagerDuty alerts
- GitHub Actions plugin

### 📈 Metrics

#### Code Stats
- **New modules**: 7 core + 3 API + 1 frontend component
- **Lines of code**: ~6,000+ (across all new files)
- **Tests**: 19 passing
- **Commits**: 12 (all phases tested)

#### Data Stats
- **Metrics cataloged**: 130
- **Intent templates**: 8
- **Hardware profiles**: 9 client + 14 Atlas tiers
- **JSON files**: 4

### 🎓 Lessons Learned
1. **Modular architecture pays off**: Each phase tested independently
2. **Hardware discovery is critical**: Enables intelligent recommendations
3. **JSON catalogs work well**: Easy to extend, validate, version control
4. **Encryption first**: Security baked in from start
5. **Test macOS early**: Reference platform for development
6. **Commit often**: Clean milestones, revertable phases

### 🔮 Future Enhancements

#### V2.1 - Metric-Driven Mode
- Full metric checkbox UI (130+ metrics)
- Multi-metric solver algorithm
- Confidence scoring per configuration
- A/B comparison (predicted vs actual)

#### V2.2 - Advanced Features
- Multi-cluster comparison mode
- Historical trend analysis
- Custom workload builder UI
- Export to JMeter/Gatling

#### V2.3 - Integrations
- Slack/PagerDuty alerts
- GitHub Actions plugin
- Kubernetes Helm chart
- CI/CD integration

### 🙏 Acknowledgments
- MongoDB Atlas Monitoring API documentation
- psutil library for cross-platform hardware detection
- FastAPI framework
- SQLAlchemy ORM

---

## [1.x] - Previous Versions

See README.md for V1 changelog.

---

**Generated**: 2026-07-03  
**Status**: Alpha Release (54% complete)  
**Next Release**: v2.0.0-beta (ETA: +40 hours development)
