# MongoDB Load Test Platform - Complete Context

**Version:** 2.0.0  
**Created:** 2026-07-03  
**Purpose:** Comprehensive load testing and validation platform for MongoDB deployments

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Philosophy](#architecture-philosophy)
3. [Key Concepts](#key-concepts)
4. [UI Design Specification](#ui-design-specification)
5. [Technical Implementation](#technical-implementation)
6. [Data Flow](#data-flow)
7. [Future Roadmap](#future-roadmap)

---

## Project Overview

### What Is This?

The MongoDB Load Test Platform is a **hardware-aware, intent-based load testing system** that combines:

- **Connection-first workflow** - Store and manage multiple MongoDB connection profiles with encrypted credentials
- **Intent-based testing** - Choose your goal (e.g., "test connection limits") and let the system calculate optimal configuration
- **Metric-driven mode** - Select specific Atlas metrics you want to spike, system generates the test
- **Hardware discovery** - Auto-detects client and server capabilities to prevent overload
- **130+ metric catalog** - Maps workloads to Atlas monitoring metrics with primary/secondary impact
- **Validation harness** - Ensures tests run within safe limits based on discovered hardware

### Why Was It Created?

**Problem Statement:**
Traditional load testing tools require deep expertise to configure correctly. Users must manually:
- Calculate thread counts based on CPU cores
- Estimate connection pool sizes
- Understand which workloads affect which metrics
- Avoid accidentally overloading the database
- Map test results to Atlas monitoring graphs

**Solution:**
This platform **abstracts complexity** through:
1. **Hardware Discovery** - Automatically detects client (driver host) and server (MongoDB) capabilities
2. **Intent Designer** - User selects "what to test" not "how to configure"
3. **Metric Impact Visualization** - Shows which Atlas metrics will spike for each test
4. **Safety Validation** - Prevents configurations that would crash the system

### Core Principles

1. **Connection-First Workflow**
   - Store multiple connection profiles (prod, staging, local)
   - Encrypted storage of URIs and credentials (Fernet encryption)
   - One-click connection test with full discovery

2. **Intent-Based Testing**
   - User thinks in terms of goals: "I want to stress-test connections"
   - System translates to technical config: threads, pools, workloads
   - Hardware-aware limits prevent overload

3. **Metric-Driven Reverse Mode**
   - User selects Atlas metrics they want to observe
   - System generates test configuration that will spike those metrics
   - Useful for reproducing production metric spikes in testing

4. **Safety First**
   - Never exceed 80% of max connections
   - Thread count capped at 2x CPU cores
   - Warnings for extreme configurations
   - Graceful degradation if limits hit

---

## Architecture Philosophy

### Three-Tier Design

```
┌─────────────────────────────────────────────────────────────┐
│                     USER INTERFACE (Web UI)                 │
│  - Connection Manager (Tab 1)                               │
│  - Intent Designer (Tab 2)                                  │
│  - Advanced Config (Tab 3)                                  │
│  - Monitor (Tab 4)                                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              BUSINESS LOGIC (FastAPI Backend)               │
│  - Intent Calculator (intent_api.py)                        │
│  - Hardware Discovery (core/hardware_discovery.py)          │
│  - Connection Manager (api/connections.py)                  │
│  - Workload Orchestrator (runner.py)                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                DATA LAYER (SQLite + MongoDB)                │
│  - Connection Profiles (loadtest.db)                        │
│  - Run History (loadtest.db)                                │
│  - Metric Catalog (130+ metrics)                            │
│  - Target MongoDB (test database)                           │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

**Why SQLite?**
- Embedded database, no external dependencies
- Connection profiles stored locally with encryption
- Run history persists across sessions
- 130+ metric catalog preloaded

**Why FastAPI?**
- Modern async framework
- Automatic OpenAPI documentation
- Type hints with Pydantic models
- Easy to extend with new endpoints

**Why Fernet Encryption?**
- Symmetric encryption (AES 128)
- Connection URIs contain credentials
- Encryption key stored in .env (user controls)
- Decrypt only when needed (never logged)

**Why Intent-Based Design?**
- Lowers barrier to entry (no MongoDB expertise needed)
- Prevents misconfiguration
- Translates business goals to technical config
- Educational (users learn what each intent does)

---

## Key Concepts

### 1. Intent-Based Testing

An **intent** is a predefined testing goal with known characteristics:

```javascript
{
  id: "connection_stress",
  name: "Connection Stress Test",
  description: "Test connection pool limits and concurrent handling",
  
  // Metrics this intent will affect
  primary_metrics: [
    "CONNECTIONS",
    "CONNECTIONS_AVAILABLE",
    "NETWORK_BYTES_IN",
    "NETWORK_BYTES_OUT"
  ],
  
  secondary_metrics: [
    "OPCOUNTER_COMMAND",
    "SYSTEM_CPU_USER"
  ],
  
  // Workloads that implement this intent
  workload_keys: ["query", "update"],
  
  // How intensity scales
  intensity_scaling: {
    light: { threads_multiplier: 0.3, load_pct: 25 },
    medium: { threads_multiplier: 0.6, load_pct: 60 },
    heavy: { threads_multiplier: 0.9, load_pct: 85 },
    extreme: { threads_multiplier: 1.2, load_pct: 95 }
  }
}
```

**8 Predefined Intents:**

1. **Connection Stress** 🔌
   - Goal: Find connection pool limits
   - Primary Metrics: CONNECTIONS, CONNECTIONS_AVAILABLE
   - Use Case: Sizing connection pools for production

2. **Read Performance** 📖
   - Goal: Benchmark query throughput
   - Primary Metrics: OPCOUNTER_QUERY, QUERY_EXECUTOR_SCANNED
   - Use Case: Index performance testing

3. **Write Throughput** ✍️
   - Goal: Max out write capacity
   - Primary Metrics: OPCOUNTER_INSERT, OPCOUNTER_UPDATE
   - Use Case: Bulk import sizing

4. **Aggregation Pipeline** 🔄
   - Goal: Test complex pipeline performance
   - Primary Metrics: OPCOUNTER_COMMAND, SYSTEM_CPU_USER
   - Use Case: Analytics query optimization

5. **Concurrency Contention** ⚡
   - Goal: Find lock contention limits
   - Primary Metrics: GLOBAL_LOCK_CURRENT_QUEUE_*
   - Use Case: Hot document update patterns

6. **Cache Pressure** 💾
   - Goal: Overflow WiredTiger cache
   - Primary Metrics: CACHE_DIRTY_BYTES, CACHE_USED_BYTES
   - Use Case: Disk I/O fallback testing

7. **Mixed Production Simulation** 🎯
   - Goal: Realistic blend (80% reads, 15% writes, 5% agg)
   - Primary Metrics: All opcounters
   - Use Case: Pre-production validation

8. **Custom** ⚙️
   - Goal: Full manual control
   - Primary Metrics: User-defined
   - Use Case: Advanced users, edge cases

### 2. Hardware Discovery

**Client-Side Discovery (Driver Host):**
```python
{
  "cpu_cores": 12,           # Physical + logical cores
  "ram_gb": 24.0,            # Total system RAM
  "storage_gb": 314.3,       # Available disk space
  "platform": "macOS 14.5",  # OS version
  "python_version": "3.14.5" # Runtime version
}
```

**Server-Side Discovery (MongoDB):**
```python
{
  "server_version": "8.2.11",      # MongoDB version
  "topology": "replicaSet",        # Standalone, replicaSet, sharded
  "is_primary": true,              # Primary or secondary
  "edition": "enterprise",         # Community, enterprise
  "set_name": "rs0",               # Replica set name
  "max_connections": 1000,         # serverStatus.connections.available
  "ram_gb": 16.0,                  # Atlas tier info (if available)
  "vcpus": 4,                      # Atlas tier info (if available)
  "cluster_tier": "M40"            # Atlas cluster tier (if available)
}
```

**How Discovery Drives Configuration:**
```python
# Base thread count from client CPU
base_threads = cpu_cores * intensity_multiplier

# Apply concurrency slider (1-50x)
thread_count = base_threads * (concurrency_slider / 10.0)

# Cap at server limits (safety)
thread_count = min(thread_count, max_connections - 10)

# Warn if exceeding safe limits
if thread_count > cpu_cores * 2:
    warn("Context switching overhead expected")
```

### 3. Metric Impact Model

Each workload has **known metric impacts**:

```python
metric_workload_map = {
  "OPCOUNTER_QUERY": [
    {"workload": "query", "impact": "primary", "confidence": 1.0},
    {"workload": "query_large", "impact": "primary", "confidence": 1.0},
    {"workload": "aggregate", "impact": "secondary", "confidence": 0.7}
  ],
  
  "CONNECTIONS": [
    {"workload": "query", "impact": "secondary", "confidence": 0.8},
    {"workload": "update", "impact": "secondary", "confidence": 0.8},
    {"workload": "hot_update", "impact": "primary", "confidence": 0.9}
  ],
  
  # ... 130+ metrics total
}
```

**Impact Levels:**
- **Primary** - Will definitely spike (direct correlation)
- **Secondary** - Will be affected (indirect correlation)
- **Tertiary** - May be affected (weak correlation)
- **Inverse** - Will decrease (negative correlation)

### 4. Configuration Calculation

**Input Parameters:**
```javascript
{
  intent_id: "read_performance",
  intensity: "heavy",           // light, medium, heavy, extreme
  duration: 600,                // seconds
  concurrency_multiplier: 15,   // 1-50 slider value
  
  // Optional overrides
  client_hardware: { cpu_cores: 12, ram_gb: 24 },
  server_hardware: { max_connections: 1000, vcpus: 4 }
}
```

**Calculation Logic:**
```python
def calculate_from_intent(intent_id, intensity, duration, concurrency_multiplier, 
                         client_hw, server_hw):
    # 1. Get intent definition
    intent = INTENTS[intent_id]
    scaling = intent.intensity_scaling[intensity]
    
    # 2. Calculate base threads
    base_threads = max(2, int(client_hw.cpu_cores * scaling.threads_multiplier))
    
    # 3. Apply concurrency multiplier
    thread_count = int(base_threads * concurrency_multiplier / 10.0)
    
    # 4. Apply safety caps
    thread_count = max(1, min(thread_count, server_hw.max_connections - 10))
    
    # 5. Generate warnings
    warnings = []
    if thread_count > client_hw.cpu_cores * 2:
        warnings.append("Thread count exceeds 2x CPU cores")
    if thread_count > server_hw.max_connections * 0.8:
        warnings.append(f"Using {thread_count/max_connections*100}% of connections")
    if scaling.load_pct >= 90:
        warnings.append("Extreme intensity - monitor closely")
    
    # 6. Return configuration
    return {
        "thread_count": thread_count,
        "estimated_load_pct": scaling.load_pct,
        "estimated_ops_per_sec": thread_count * 50,  # Heuristic
        "workload_keys": intent.workload_keys,
        "warnings": warnings
    }
```

**Output Configuration:**
```javascript
{
  "thread_count": 48,
  "estimated_load_pct": 85,
  "estimated_ops_per_sec": 2400,
  "workload_keys": ["query", "query_large"],
  "primary_metrics": ["OPCOUNTER_QUERY", "QUERY_EXECUTOR_SCANNED"],
  "secondary_metrics": ["CACHE_BYTES_READ", "TICKETS_AVAILABLE_READS"],
  "warnings": [
    "Thread count (48) exceeds 2x CPU cores. Context switching overhead expected."
  ]
}
```

---

## UI Design Specification

### Design Philosophy

The UI is structured as a **progressive workflow** with **4 tabs** that guide users from connection to monitoring:

```
Tab 1: Connection → Tab 2: Intent Designer → Tab 3: Advanced Config → Tab 4: Monitor
   (setup)            (choose goal)           (optional tweaks)         (observe)
```

**Design Principles:**
1. **Progressive Disclosure** - Show complexity only when needed
2. **Visual Feedback** - Immediate response to user actions
3. **Neon Theme** - Dark background with vibrant accent colors
4. **Metric-Centric** - Always show which metrics will be affected
5. **Hardware-Aware** - Display discovered capabilities prominently

---

### Tab 1: Connection Manager

**Purpose:** Manage and test MongoDB connections with auto-discovery

#### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  CONNECTION PROFILES                                        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ○ Manish Sinha Personal CE                         │   │
│  │     ✓ mongodb+srv://***@cluster.mongodb.net        │   │
│  │     → loadtest                                       │   │
│  │     MongoDB 8.2.11 | replicaSet | enterprise        │   │
│  │     [Edit] [Delete]                                  │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  ○ Production M40 Cluster                           │   │
│  │     ? mongodb+srv://***@prod.mongodb.net            │   │
│  │     → analytics                                      │   │
│  │     Not tested yet                                   │   │
│  │     [Edit] [Delete]                                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [+ Add New Connection Profile]  [Test Connection]         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  AUTO-DISCOVERY RESULTS                                     │
│  ┌───────────────────────┬─────────────────────────────┐   │
│  │  CLIENT HARDWARE      │  MONGODB TARGET             │   │
│  │  CPU Cores: 12        │  Version: 8.2.11            │   │
│  │  RAM: 24 GB           │  Topology: replicaSet       │   │
│  │  Storage: 314 GB      │  Max Connections: 1000      │   │
│  │  [Edit Override]      │  [Edit Override]            │   │
│  └───────────────────────┴─────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PERMISSION CHECK          ✓ ALL PASSED             │   │
│  │  ✓ Read    ✓ Write    ✓ Index    ✓ Admin           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  CLOCK SKEW CHECK          ✓ OK                     │   │
│  │  Skew: 0.12s (threshold: 2.0s)                      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

#### Visual Design Details

**Profile Card:**
- Radio button for selection
- Status indicator: ✓ (green), ✗ (red), ? (yellow)
- Redacted URI with masked password
- Database name with arrow (→)
- Server info (version, topology, edition)
- Action buttons: Edit (secondary), Delete (danger)

**Discovery Results:**
- Two-column layout (Client | Server)
- Bold values with units
- Edit Override buttons open modal
- Neon border highlight when hardware overridden

**Permission/Clock Checks:**
- Collapsible sections
- Green checkmarks for pass, red X for fail
- Inline error messages for failures
- Warning icon for clock skew > 2s

#### Interactions

1. **Add New Profile:**
   - Opens form below profile list
   - Fields: Name, URI (password type), Database, Auth Source
   - Show/Hide toggle for URI
   - Save button encrypts URI before storing

2. **Test Connection:**
   - Disabled until profile selected
   - Shows spinner: "Testing connection and discovering hardware..."
   - On success: Displays discovery results
   - On failure: Shows error with retry button

3. **Edit Override:**
   - Opens modal overlay
   - Two sections: Client Hardware | Server Hardware
   - Number inputs with units
   - Apply button recalculates limits
   - Override values shown with yellow indicator

---

### Tab 2: Intent Designer

**Purpose:** Choose testing goal and configure with visual knobs

#### Top Section: Mode Toggle

```
┌─────────────────────────────────────────────────────────────┐
│  [🎯 Guided Intent Mode]     [📊 Metric-Driven Mode]        │
│      (active, glowing)          (inactive, dim)             │
└─────────────────────────────────────────────────────────────┘
```

**Visual States:**
- Active: Neon glow, solid background, bold text
- Inactive: Dim gray, transparent background
- Hover: Subtle glow animation

---

#### Intent Mode Layout

```
┌─────────────────────────────────────────────────────────────┐
│  CHOOSE YOUR TESTING GOAL                                   │
│  Select an intent below. System will calculate optimal      │
│  configuration based on your hardware.                       │
└─────────────────────────────────────────────────────────────┘

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ 🔌           │ 📖           │ ✍️           │ 🔄           │
│ Connection   │ Read         │ Write        │ Aggregation  │
│ Stress       │ Performance  │ Throughput   │ Pipeline     │
│              │              │              │              │
│ Test pool    │ Benchmark    │ Max out      │ Test complex │
│ limits and   │ query        │ write cap    │ pipelines    │
│ concurrent   │ throughput   │ with batch   │ (groupBy,    │
│ handling     │ indexed +    │ inserts      │ unwind)      │
│              │ unindexed    │              │              │
│ 🎯 5 Primary │ 🎯 5 Primary │ 🎯 5 Primary │ 🎯 4 Primary │
│ ↗️ 3 Secondary│ ↗️ 4 Secondary│ ↗️ 5 Secondary│ ↗️ 4 Secondary│
│              │              │              │              │
│ [SELECTED]   │              │              │              │
└──────────────┴──────────────┴──────────────┴──────────────┘

┌──────────────┬──────────────┬──────────────┬──────────────┐
│ ⚡           │ 💾           │ 🎯           │ ⚙️           │
│ Concurrency  │ Cache        │ Mixed        │ Custom       │
│ Contention   │ Pressure     │ Production   │              │
│              │              │              │              │
│ Find lock    │ Overflow     │ Realistic    │ Full manual  │
│ contention   │ WiredTiger   │ blend: 80%   │ control over │
│ limits on    │ cache to     │ reads, 15%   │ all params   │
│ hot docs     │ test disk    │ writes, 5%   │              │
│              │ I/O fallback │ agg          │              │
│ 🎯 4 Primary │ 🎯 5 Primary │ 🎯 4 Primary │ 🎯 0 Primary │
│ ↗️ 4 Secondary│ ↗️ 4 Secondary│ ↗️ 6 Secondary│ ↗️ 0 Secondary│
└──────────────┴──────────────┴──────────────┴──────────────┘
```

**Intent Card Design:**
- 280px x 220px
- Icon (3rem size) at top
- Intent name (bold, 1.2rem)
- Description (0.9rem, gray, 3 lines min-height)
- Metric badges at bottom:
  - Primary: Green background, green border
  - Secondary: Yellow background, yellow border
- Hover: Border glow, translateY(-2px)
- Selected: Neon glow, brighter background

---

#### Configuration Panel (Appears Below Selected Card)

```
┌─────────────────────────────────────────────────────────────┐
│  CONFIGURE: Connection Stress                               │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  KNOBS                                             │    │
│  │                                                     │    │
│  │  Intensity  ℹ️                                      │    │
│  │  [Light (20-40% load) ▼]                           │    │
│  │                                                     │    │
│  │  Duration  ℹ️                                       │    │
│  │  [600] seconds                                      │    │
│  │                                                     │    │
│  │  Concurrency  ℹ️                                    │    │
│  │  ├──────────●──────────┤                           │    │
│  │  1               25               50                │    │
│  │  Current: 15                                        │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  🎯 PRIMARY METRICS (Will Spike)                   │    │
│  │  [CONNECTIONS] [CONNECTIONS_AVAILABLE]              │    │
│  │  [NETWORK_BYTES_IN] [NETWORK_BYTES_OUT]             │    │
│  │  [NETWORK_NUM_REQUESTS]                             │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  ↗️ SECONDARY METRICS (Will Be Affected)            │    │
│  │  [OPCOUNTER_COMMAND] [SYSTEM_CPU_USER]              │    │
│  │  [SYSTEM_MEMORY_AVAILABLE_MB]                       │    │
│  └────────────────────────────────────────────────────┘    │
│                                                              │
│  [Calculate Configuration]                                  │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │  CALCULATED CONFIGURATION                          │    │
│  │                                                     │    │
│  │  Estimated Load:     85% capacity                  │    │
│  │  Thread Count:       48 threads                    │    │
│  │  Operations/sec:     ~2400                         │    │
│  │  Total Duration:     600s                          │    │
│  │                                                     │    │
│  │  ⚠️ WARNINGS                                        │    │
│  │  • Thread count (48) exceeds 2x CPU cores (24).    │    │
│  │    Context switching overhead expected.            │    │
│  │                                                     │    │
│  │  [Apply & Go to Run Tab]  [Export Config JSON]     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

**Knobs Visual Design:**

1. **Intensity Dropdown:**
   - 4 options with visual indicators
   - Light: 🟢 (20-40% load)
   - Medium: 🟡 (60-70% load)
   - Heavy: 🟠 (80-90% load)
   - Extreme: 🔴 (95%+ load)

2. **Duration Input:**
   - Number input with unit label
   - Min: 60s, Max: 7200s (2 hours)
   - Default: 600s (10 minutes)

3. **Concurrency Slider:**
   - Gradient background: Green → Yellow → Red
   - Large thumb (draggable)
   - Live value display below slider
   - Range: 1-50

**Metric Pills:**
- Primary: Rounded rectangle, green border/bg, green text
- Secondary: Rounded rectangle, yellow border/bg, yellow text
- Hover: Tooltip shows full metric description
- Click: (Future) Opens metric detail panel

**Calculate Button:**
- Large, centered
- Neon glow on hover
- Shows spinner while calculating
- Becomes "Recalculate" after first use

**Calculated Configuration Box:**
- Border: Green if safe, Yellow if warnings, Red if errors
- Grid layout: 2 columns
- Values: Bold, neon color
- Warnings section: Collapsible, yellow background
- Action buttons: Primary (Apply), Secondary (Export)

---

#### Metric-Driven Mode Layout

```
┌─────────────────────────────────────────────────────────────┐
│  METRIC-DRIVEN TEST GENERATION                              │
│  Select metrics you want to spike. System will generate     │
│  optimal test configuration.                                 │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────┬──────────────────────────────┐
│  METRIC CATEGORIES           │  SELECTED METRICS (3)        │
│                              │                              │
│  🔍 Search 130+ metrics...   │  [OPCOUNTER_QUERY ×]         │
│                              │  [CONNECTIONS ×]             │
│  ▼ Connections & Network (15)│  [CACHE_BYTES_READ ×]        │
│    ☐ CONNECTIONS             │                              │
│    ☑ CONNECTIONS_AVAILABLE   │  ┌────────────────────────┐ │
│    ☐ NETWORK_BYTES_IN        │  │                        │ │
│    ☐ NETWORK_BYTES_OUT       │  │  [Generate Test]       │ │
│    ...                       │  │                        │ │
│                              │  └────────────────────────┘ │
│  ▼ Operations (12)           │                              │
│    ☑ OPCOUNTER_QUERY         │  GENERATED CONFIG:           │
│    ☐ OPCOUNTER_INSERT        │  ┌────────────────────────┐ │
│    ☐ OPCOUNTER_UPDATE        │  │ Intent: Read Perf      │ │
│    ...                       │  │ Workloads: query,      │ │
│                              │  │            query_large │ │
│  ▼ Memory & Cache (18)       │  │ Matched: 2/3 (67%)     │ │
│    ☑ CACHE_BYTES_READ        │  │                        │ │
│    ☐ CACHE_BYTES_WRITTEN     │  │ [Apply Configuration]  │ │
│    ☐ CACHE_DIRTY_BYTES       │  └────────────────────────┘ │
│    ...                       │                              │
│                              │                              │
│  ▼ Query Execution (22)      │                              │
│    ☐ QUERY_EXECUTOR_SCANNED  │                              │
│    ...                       │                              │
└──────────────────────────────┴──────────────────────────────┘
```

**Metric Selector Design:**
- Left panel: Scrollable (max-height: 70vh)
- Search box: Instant filter (debounced 300ms)
- Categories: Collapsible accordions
- Checkboxes: Neon style, animated check
- Right panel: Sticky (position: sticky, top: 1rem)

**Selected Metrics Panel:**
- Pills with × button to remove
- Counter in header
- Generate button: Disabled if 0 metrics
- Results box: Appears after generation

---

### Tab 3: Advanced Config

**Purpose:** Manual workload configuration and fine-tuning (Legacy V1 mode)

```
┌─────────────────────────────────────────────────────────────┐
│  WORKLOADS - SELECT & CONFIGURE                             │
│                                                              │
│  ☑ 1. Indexed Reads (query)                                 │
│     threads: [10]  duration: [60]                           │
│                                                              │
│  ☐ 2. Large Dataset Scan (query_large)                      │
│     threads: [5]   limit: [1000]                            │
│                                                              │
│  ☑ 3. Bulk Insert (bulk_insert)                             │
│     threads: [8]   batch_size: [1000]                       │
│                                                              │
│  ☐ 4. Aggregation Pipeline (aggregate)                      │
│     threads: [4]   complexity: [medium]                     │
│                                                              │
│  ... (12 workloads total)                                   │
│                                                              │
│  [Select All] [Clear All] [Import JSON]                     │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────────────┬──────────────────────────────┐
│  RUN NOW                     │  OUTPUT & SEEDING            │
│                              │                              │
│  Duration (seconds): [60]    │  Database: [loadtest]        │
│  Run seed: [     ] (random)  │  Output: [./runs/]           │
│                              │                              │
│  ☑ Auto-seed before run      │  [Validate / Create Output]  │
│  ☐ Ignore clock skew > 2s    │                              │
│                              │  [Seed Database]             │
│  [Start Run]                 │                              │
└──────────────────────────────┴──────────────────────────────┘
```

**This tab is the ORIGINAL V1 interface** - kept for:
- Advanced users who want full control
- Edge cases not covered by intents
- Backward compatibility
- Educational purposes (see what intents generate)

---

### Tab 4: Monitor (Future)

**Purpose:** Real-time monitoring and Atlas graph integration

```
┌─────────────────────────────────────────────────────────────┐
│  REAL-TIME METRICS                                          │
│                                                              │
│  ┌─────────────────────────┬─────────────────────────────┐ │
│  │  OPCOUNTER_QUERY        │  ████████░░░░░░  (2400/s)  │ │
│  │  CONNECTIONS            │  ██████░░░░░░░░  (600/1000)│ │
│  │  CACHE_BYTES_READ       │  ███████████░░░  (800MB/s) │ │
│  │  SYSTEM_CPU_USER        │  ██████████░░░░  (75%)     │ │
│  └─────────────────────────┴─────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ATLAS GRAPH PREVIEW                                │    │
│  │  [Link to Atlas UI for this metric group]          │    │
│  │                                                      │    │
│  │  [Embed iframes of Atlas graphs]                    │    │
│  │  (Requires Atlas API credentials from Tab 1)        │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Technical Implementation

### Frontend Stack

**Components:**
```
static/
├── index.html                 # Main shell
├── style.css                  # Neon theme + component styles
├── app.js                     # Main application logic
└── components/
    ├── connection-manager.js  # Tab 1: Connection CRUD + discovery
    └── intent-designer-v2.js  # Tab 2: Intent cards + config
```

**Component Architecture:**
- **ConnectionManager** class: Manages profiles, discovery, overrides
- **IntentDesignerV2** class: Renders intents, calculates config, metric mode
- **APIClient** wrapper: Handles fetch with error handling

**State Management:**
- No framework (Vanilla JS)
- Global objects: `window.connManager`, `window.intentDesigner`
- Event-driven updates via DOM manipulation

**Styling:**
- CSS custom properties for theming
- `--neon` variable (user-configurable color)
- Responsive grid layouts
- Dark theme with neon accents

---

### Backend Stack

**FastAPI Routes:**
```python
# Connection Management
POST   /api/connections              # Create profile
GET    /api/connections              # List all profiles
GET    /api/connections/{id}         # Get profile by ID
PUT    /api/connections/{id}         # Update profile
DELETE /api/connections/{id}         # Delete profile
POST   /api/connections/{id}/test    # Test connection + discovery

# Intent-Based Testing
GET    /api/intent/types             # List 8 intent definitions
POST   /api/intent/calculate         # Calculate config from intent

# Metric-Driven Mode
GET    /api/metrics/catalog          # 130+ metric catalog
POST   /api/metrics/generate-test    # Generate test from metrics

# Legacy V1 (Advanced Config)
GET    /api/catalog                  # Workload catalog
POST   /api/run                      # Start run
GET    /api/run/{id}                 # Run status
```

**Data Models (Pydantic):**
```python
class ConnectionProfile(BaseModel):
    name: str
    uri: str  # Encrypted before storage
    database_name: str
    auth_source: str | None
    
class DiscoveryResult(BaseModel):
    client: ClientHardware
    server: ServerInfo
    connection: ConnectionTest
    permissions: PermissionCheck
    clock_skew: ClockSkew
    
class IntentCalculateRequest(BaseModel):
    intent_id: str
    intensity: str  # light, medium, heavy, extreme
    duration: int
    concurrency_multiplier: float
```

**Database Schema (SQLite):**
```sql
-- Connection profiles (encrypted)
CREATE TABLE connection_profiles (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    uri_encrypted BLOB NOT NULL,  -- Fernet encrypted
    database_name TEXT NOT NULL,
    auth_source TEXT,
    
    -- Discovery cache
    client_cpu_cores INTEGER,
    client_ram_gb REAL,
    server_version TEXT,
    server_max_connections INTEGER,
    
    -- Overrides
    override_cpu_cores INTEGER,
    override_ram_gb REAL,
    
    -- Atlas API (optional)
    atlas_public_key_encrypted BLOB,
    atlas_private_key_encrypted BLOB,
    atlas_group_id TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Run history
CREATE TABLE run_history (
    id INTEGER PRIMARY KEY,
    run_id TEXT UNIQUE NOT NULL,
    connection_profile_id INTEGER,
    intent_type TEXT,  -- NEW: connection_stress, read_performance, etc.
    intensity TEXT,    -- NEW: light, medium, heavy, extreme
    started_utc TIMESTAMP,
    ended_utc TIMESTAMP,
    status TEXT,
    config_json TEXT,
    FOREIGN KEY (connection_profile_id) REFERENCES connection_profiles(id)
);

-- Metric catalog (preloaded from JSON)
CREATE TABLE atlas_metrics (
    metric_name TEXT PRIMARY KEY,
    category_id TEXT NOT NULL,
    category_name TEXT NOT NULL,
    unit TEXT NOT NULL,
    description TEXT NOT NULL,
    atlas_available BOOLEAN DEFAULT TRUE,
    ftdc_available BOOLEAN DEFAULT TRUE
);

-- Metric → Workload mappings
CREATE TABLE metric_workload_map (
    id INTEGER PRIMARY KEY,
    metric_name TEXT NOT NULL,
    workload_key TEXT NOT NULL,
    impact_level TEXT NOT NULL,  -- primary, secondary, tertiary
    confidence REAL NOT NULL,     -- 0.0 to 1.0
    FOREIGN KEY (metric_name) REFERENCES atlas_metrics(metric_name)
);
```

---

## Data Flow

### Connection Test Flow

```
User clicks "Test Connection"
        ↓
ConnectionManager.testConnection(profileId)
        ↓
POST /api/connections/{id}/test
        ↓
Backend:
  1. Decrypt URI from database
  2. Create MongoClient
  3. Run preflight checks:
     - Ping server
     - Check permissions (read, write, index, admin)
     - Measure clock skew
  4. Discover client hardware (psutil)
  5. Discover server info (buildInfo, serverStatus)
  6. Update profile with discovery data
        ↓
Return DiscoveryResult JSON
        ↓
Frontend:
  ConnectionManager.displayDiscoveryResults(result)
        ↓
Render discovery cards with Edit Override buttons
```

### Intent Calculation Flow

```
User selects intent "Read Performance"
        ↓
IntentDesignerV2.selectIntent("read_performance")
        ↓
Render configuration panel with knobs
        ↓
User adjusts: Intensity=Heavy, Duration=600, Concurrency=15
        ↓
User clicks "Calculate Configuration"
        ↓
POST /api/intent/calculate
  Body: {
    intent_id: "read_performance",
    intensity: "heavy",
    duration: 600,
    concurrency_multiplier: 15
  }
        ↓
Backend:
  1. Get intent definition from INTENT_DEFINITIONS
  2. Get hardware from latest discovery (or auto-detect)
  3. Calculate thread_count:
     base = cpu_cores * scaling.threads_multiplier
     threads = base * (concurrency / 10.0)
     threads = min(threads, max_connections - 10)
  4. Calculate estimated_ops_per_sec = threads * 50
  5. Generate warnings (context switching, connection exhaustion)
  6. Return config
        ↓
Frontend:
  IntentDesignerV2.displayCalculatedConfig(result)
        ↓
Show config box with thread count, load %, warnings
        ↓
User clicks "Apply & Go to Run Tab"
        ↓
Store config in window.intentConfig
Switch to Tab 3 (Advanced Config)
Populate workload parameters from config
```

### Metric-Driven Generation Flow

```
User switches to "Metric-Driven Mode"
        ↓
IntentDesignerV2.switchMode("metric-driven")
        ↓
GET /api/metrics/catalog
        ↓
Load 130+ metrics grouped by category
        ↓
Render checkboxes
        ↓
User searches "query"
        ↓
Filter checkboxes (OPCOUNTER_QUERY, QUERY_EXECUTOR_*)
        ↓
User checks: OPCOUNTER_QUERY, QUERY_EXECUTOR_SCANNED
        ↓
Update selectedMetrics array
        ↓
User clicks "Generate Test Configuration"
        ↓
POST /api/metrics/generate-test
  Body: { metrics: ["OPCOUNTER_QUERY", "QUERY_EXECUTOR_SCANNED"] }
        ↓
Backend:
  1. Score each intent by metric overlap:
     - Primary match = +3 points
     - Secondary match = +1 point
  2. Rank intents by score
  3. Return top intent as recommendation
        ↓
Frontend:
  Show recommended intent + workloads
        ↓
User clicks "Apply Configuration"
        ↓
Switch to Intent Mode with recommended intent pre-selected
```

---

## Future Roadmap

### V2.1: Enhanced Metric Catalog
- ✅ Load full 130 metrics from atlas_metrics.json
- ✅ Populate metric_workload_map from data/metric_workload_map.json
- ✅ Metric detail tooltips with descriptions
- ⏳ Atlas graph preview links
- ⏳ Metric history charts (past runs)

### V2.2: Atlas API Integration
- ⏳ Store Atlas API credentials per profile
- ⏳ Fetch real-time metrics during run
- ⏳ Embed Atlas iframes in Monitor tab
- ⏳ Auto-annotate Atlas graphs with test markers
- ⏳ Export test results to Atlas as custom events

### V2.3: Advanced Features
- ⏳ Test templates (save intent + config as template)
- ⏳ Comparison mode (run A vs run B side-by-side)
- ⏳ Regression detection (compare to baseline)
- ⏳ Scheduled tests (cron-style, integration with scheduler)
- ⏳ Multi-target tests (test multiple profiles in parallel)

### V2.4: Workload Enhancements
- ⏳ Custom workload builder (visual editor)
- ⏳ Import real query patterns from logs
- ⏳ Workload recording (capture prod traffic)
- ⏳ Workload replay (simulate prod patterns)

### V2.5: Reporting & Analytics
- ⏳ PDF report generation
- ⏳ Trend analysis (metric changes over time)
- ⏳ Performance regression alerts
- ⏳ Capacity planning recommendations
- ⏳ Cost estimation (Atlas tier recommendations)

---

## Appendix: Complete Intent Definitions

### 1. Connection Stress
```javascript
{
  id: "connection_stress",
  name: "Connection Stress",
  description: "Test connection pool limits and concurrent connection handling",
  icon: "🔌",
  
  primary_metrics: [
    "CONNECTIONS",
    "CONNECTIONS_AVAILABLE",
    "NETWORK_BYTES_IN",
    "NETWORK_BYTES_OUT",
    "NETWORK_NUM_REQUESTS"
  ],
  
  secondary_metrics: [
    "OPCOUNTER_COMMAND",
    "SYSTEM_CPU_USER",
    "SYSTEM_MEMORY_AVAILABLE_MB"
  ],
  
  workload_keys: ["query", "update"],
  
  workload_weights: {
    query: 0.6,
    update: 0.4
  },
  
  intensity_scaling: {
    light: {
      threads_multiplier: 0.3,
      load_pct: 25,
      ops_per_thread: 30,
      batch_size: 1
    },
    medium: {
      threads_multiplier: 0.6,
      load_pct: 60,
      ops_per_thread: 50,
      batch_size: 1
    },
    heavy: {
      threads_multiplier: 0.9,
      load_pct: 85,
      ops_per_thread: 70,
      batch_size: 1
    },
    extreme: {
      threads_multiplier: 1.2,
      load_pct: 95,
      ops_per_thread: 100,
      batch_size: 1
    }
  },
  
  use_cases: [
    "Sizing connection pools for production",
    "Testing connection recovery after network issues",
    "Validating connection pool configuration",
    "Benchmarking max concurrent connections"
  ],
  
  atlas_graph_hints: [
    "Connections: Should spike to near max_connections",
    "Network Bytes In/Out: Should increase linearly",
    "Command Rate: Should match thread count * ops_per_thread"
  ]
}
```

### 2. Read Performance
```javascript
{
  id: "read_performance",
  name: "Read Performance",
  description: "Benchmark query throughput (indexed + unindexed reads)",
  icon: "📖",
  
  primary_metrics: [
    "OPCOUNTER_QUERY",
    "OPCOUNTER_GETMORE",
    "QUERY_EXECUTOR_SCANNED",
    "QUERY_EXECUTOR_SCANNED_OBJECTS",
    "QUERY_TARGETING_SCANNED_PER_RETURNED"
  ],
  
  secondary_metrics: [
    "CACHE_BYTES_READ",
    "TICKETS_AVAILABLE_READS",
    "CURSORS_TOTAL_OPEN",
    "NETWORK_BYTES_OUT"
  ],
  
  workload_keys: ["query", "query_large"],
  
  workload_weights: {
    query: 0.7,        // Indexed reads
    query_large: 0.3   // Unindexed scans
  },
  
  intensity_scaling: {
    light: { threads_multiplier: 0.4, load_pct: 30 },
    medium: { threads_multiplier: 0.7, load_pct: 65 },
    heavy: { threads_multiplier: 1.0, load_pct: 90 },
    extreme: { threads_multiplier: 1.3, load_pct: 98 }
  },
  
  use_cases: [
    "Index performance validation",
    "Query pattern optimization",
    "Cache hit ratio analysis",
    "Read capacity planning"
  ]
}
```

### 3. Write Throughput
```javascript
{
  id: "write_throughput",
  name: "Write Throughput",
  description: "Max out write capacity with batch inserts",
  icon: "✍️",
  
  primary_metrics: [
    "OPCOUNTER_INSERT",
    "OPCOUNTER_UPDATE",
    "OPCOUNTER_DELETE",
    "DOCUMENT_METRICS_INSERTED",
    "DOCUMENT_METRICS_UPDATED"
  ],
  
  secondary_metrics: [
    "CACHE_BYTES_WRITTEN",
    "CACHE_DIRTY_BYTES",
    "TICKETS_AVAILABLE_WRITES",
    "OPLOG_RATE_GB_PER_HOUR",
    "NETWORK_BYTES_IN"
  ],
  
  workload_keys: ["insert", "update", "bulk_insert"],
  
  workload_weights: {
    bulk_insert: 0.6,
    insert: 0.2,
    update: 0.2
  },
  
  intensity_scaling: {
    light: { threads_multiplier: 0.3, load_pct: 20 },
    medium: { threads_multiplier: 0.6, load_pct: 55 },
    heavy: { threads_multiplier: 0.9, load_pct: 80 },
    extreme: { threads_multiplier: 1.1, load_pct: 95 }
  },
  
  use_cases: [
    "Bulk data import sizing",
    "Write capacity benchmarking",
    "Replication lag testing",
    "Oplog growth estimation"
  ]
}
```

*(Continue for remaining 5 intents...)*

---

## Appendix: Metric Catalog Structure

### Category: Connections & Network (15 metrics)

| Metric Name | Unit | Primary Use | Atlas Available |
|-------------|------|-------------|-----------------|
| CONNECTIONS | count | Current active connections | ✓ |
| CONNECTIONS_AVAILABLE | count | Remaining connection slots | ✓ |
| NETWORK_BYTES_IN | bytes/sec | Incoming network traffic | ✓ |
| NETWORK_BYTES_OUT | bytes/sec | Outgoing network traffic | ✓ |
| NETWORK_NUM_REQUESTS | requests/sec | Total network requests | ✓ |
| ... | ... | ... | ... |

### Category: Operations (Opcounters) (12 metrics)

| Metric Name | Unit | Primary Use | Atlas Available |
|-------------|------|-------------|-----------------|
| OPCOUNTER_QUERY | ops/sec | Query operations | ✓ |
| OPCOUNTER_INSERT | ops/sec | Insert operations | ✓ |
| OPCOUNTER_UPDATE | ops/sec | Update operations | ✓ |
| OPCOUNTER_DELETE | ops/sec | Delete operations | ✓ |
| OPCOUNTER_GETMORE | ops/sec | Cursor iteration ops | ✓ |
| OPCOUNTER_COMMAND | ops/sec | Command operations | ✓ |
| ... | ... | ... | ... |

*(Continue for all 9 categories, 130+ total metrics)*

---

**End of Context Document**

This document serves as the complete specification for the MongoDB Load Test Platform V2.0. It should be used as reference for:
- New developers joining the project
- Extending the system with new features
- Understanding design decisions
- Planning UI/UX improvements
- API integration and testing

Last Updated: 2026-07-03  
Version: 2.0.0  
Commit: 8454205
