"""Central configuration and constants for loadgen.

Verified environment facts (do not re-derive):
  * Driver host is OMEN (not a replica-set member, by design).
  * pymongo 4.x; homelab target is MongoDB Enterprise 8.2.11.
  * Atlas (mongodb+srv://) must work with no code change; use Stable API there.
  * Operator timezone is IST (Asia/Kolkata); FTDC timestamps are UTC.
"""
from __future__ import annotations

import os

# --- Timezones -------------------------------------------------------------
OPERATOR_TZ = "Asia/Kolkata"          # IST — what the operator sees
STORAGE_TZ = "UTC"                    # what FTDC uses; stored alongside everywhere

# --- Connection defaults ---------------------------------------------------
SERVER_SELECTION_TIMEOUT_MS = 5000   # short timeout for the Test-Connection probe
CONNECT_TIMEOUT_MS = 5000
SOCKET_TIMEOUT_MS = 20000

# --- Clock skew preflight --------------------------------------------------
MAX_CLOCK_SKEW_SECONDS = 2.0         # WARN above this; corrupts FTDC correlation

# --- Permission-check probe collection -------------------------------------
PERMCHECK_COLLECTION = "__loadgen_permcheck"

# --- Output --------------------------------------------------------------
DEFAULT_OUTPUT_DIR = os.environ.get("LOADGEN_OUTPUT_DIR", "./runs")

# --- Default load-test database --------------------------------------------
DEFAULT_DB = os.environ.get("LOADGEN_DB", "loadtest")

# --- Seeder collection names (one place so every module agrees) ------------
COLL_LARGE = "large_dataset"          # indexed user_id + unindexed random_tag
COLL_AGG = "agg_dataset"              # arrays / subdocs for aggregation
COLL_HOT = "hot_docs"                 # small hot set for update contention
COLL_APPEND = "append_target"         # write_bursts target

# Number of distinct random_tag values (so unindexed scans still match rows).
TAG_CARDINALITY = 50
# Number of hot docs used by update_contention by default.
DEFAULT_HOT_DOCS = 100

# --- Seeder defaults -------------------------------------------------------
DEFAULT_SEED_LARGE_COUNT = 1_000_000  # real spike default
DEFAULT_SEED_AGG_COUNT = 50_000
SMOKE_SEED_LARGE_COUNT = 50_000       # used by smoke test / quick mode

# --- Scheduling defaults ---------------------------------------------------
DEFAULT_WINDOW_START_IST = "10:00"
DEFAULT_WINDOW_END_IST = "12:00"
DEFAULT_SCHEDULE_DAYS = 7

# APScheduler SQLite jobstore lives next to the app so it survives restarts.
SCHEDULER_DB_PATH = os.environ.get("LOADGEN_SCHED_DB", "./loadgen_jobs.sqlite")

APP_VERSION = "1.0.0"
