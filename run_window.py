"""Headless single-window runner — used by systemd (loadgen.service) and usable
by hand. Reads config from the environment so credentials stay out of argv.

Env:
  LOADGEN_URI         (required) full mongodb:// or mongodb+srv:// URI
  LOADGEN_AUTH_SOURCE (optional)
  LOADGEN_DB          (optional, default 'loadtest')
  LOADGEN_OUTPUT_DIR  (optional, default './runs')
  LOADGEN_DURATION    (optional seconds, default 600)
  LOADGEN_BASE_SEED   (optional int, default 1234)
  LOADGEN_BLEND_THREADS (optional int, default 12)
  LOADGEN_AUTO_SEED   (optional 1/true) — top up the seed before the run so an
                      unattended run never trips the 'seeder not run' guard
  LOADGEN_SEED_LARGE / LOADGEN_SEED_AGG / LOADGEN_SEED_HOT (optional counts)

Runs one seeded mixed_blend window and writes a manifest. Exit code 0 on a
completed run, 1 on failure (so systemd/journald records the failure).
"""
from __future__ import annotations

import os
import sys

import config
from runner import execute_run


def main() -> int:
    uri = os.environ.get("LOADGEN_URI")
    if not uri:
        print("ERROR: LOADGEN_URI not set", file=sys.stderr)
        return 1
    # Jitter: launchd has no random delay, so apply it here (Windows uses the
    # task's RandomDelay instead and leaves this unset).
    jitter_max = int(os.environ.get("LOADGEN_JITTER_MAX_SEC", "0") or "0")
    if jitter_max > 0:
        import random
        import time
        delay = random.randint(0, jitter_max)
        print(f"jitter: sleeping {delay}s (0..{jitter_max}) before run", file=sys.stderr)
        time.sleep(delay)
    today = __import__("datetime").datetime.utcnow().strftime("%Y%m%d")
    base_seed = int(os.environ.get("LOADGEN_BASE_SEED", "1234"))
    day_seed = (base_seed + int(today)) % (2 ** 31)
    cfg = {
        "uri": uri,
        "auth_source": os.environ.get("LOADGEN_AUTH_SOURCE"),
        "default_db": os.environ.get("LOADGEN_DB", config.DEFAULT_DB),
        "output_dir": os.environ.get("LOADGEN_OUTPUT_DIR", config.DEFAULT_OUTPUT_DIR),
        "duration_seconds": float(os.environ.get("LOADGEN_DURATION", "600")),
        "seed": day_seed,
        "workloads": {"mixed_blend": {"seed": day_seed,
                                      "total_threads": int(os.environ.get("LOADGEN_BLEND_THREADS", "12"))}},
    }
    if os.environ.get("LOADGEN_AUTO_SEED", "").lower() in ("1", "true", "yes"):
        cfg["auto_seed"] = True
        cfg["seed_params"] = {
            "large_count": int(os.environ.get("LOADGEN_SEED_LARGE", config.SMOKE_SEED_LARGE_COUNT)),
            "agg_count": int(os.environ.get("LOADGEN_SEED_AGG", "50000")),
            "hot_docs": int(os.environ.get("LOADGEN_SEED_HOT", str(config.DEFAULT_HOT_DOCS))),
        }
    state = execute_run(cfg, mode="scheduled")
    print(f"run {state.run_id}: status={state.status} manifest={state.manifest_path}")
    return 0 if state.status == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
