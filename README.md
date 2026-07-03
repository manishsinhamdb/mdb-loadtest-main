# loadgen — MongoDB Load Generator + Validation Harness

A configurable MongoDB load-generation web app. Its scientific purpose: generate
**known, characterized** load against a target MongoDB so the effects can be
diffed against the target's **FTDC** diagnostic output — validating a separate
FTDC analyzer. Every run emits a ground-truth **manifest** of exactly what load
ran and when (in **both local time and UTC**).

It is also a reusable, general-purpose MongoDB load tester for **any** deployment
(self-managed replica set **or** MongoDB Atlas), driven entirely from the UI.

Requirements: **Python 3.10+** and network access to your MongoDB target. The
target connection string is entered in the UI — nothing is hardcoded.

---

## Quick start (one command)

Clone, then run the deploy script for your OS. It creates a virtualenv, installs
dependencies, and (with the run flag) starts the app.

**macOS / Linux**
```bash
git clone git@github.com:looking4manish/mdb-loadtest.git
cd mdb-loadtest
./deploy.sh --run                 # add PORT=9000 to change the port
```

**Windows (PowerShell)**
```powershell
git clone git@github.com:looking4manish/mdb-loadtest.git
cd mdb-loadtest
.\deploy.ps1 -Run                 # add -Port 8077 if 8000 is reserved (winerror 10013)
```

Then open **http://127.0.0.1:8000/** (or whatever port you chose).

> Manual equivalent, if you'd rather not use the script:
> ```bash
> python3 -m venv venv                                   # Windows: py -3 -m venv venv
> venv/bin/python -m pip install -r requirements.txt      # Windows: venv\Scripts\python -m pip ...
> venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
> ```

---

## Using the UI (the three first-class features)

1. **Connection URI** — paste a full `mongodb://…` or `mongodb+srv://…` (Atlas)
   string. It is the single source of truth for the target. The password is
   masked after entry and **never** logged or stored (all logs/manifests carry a
   redacted host+db only). Optional **auth source** and **default database**
   override fields are parsed on top of whatever the URI already carries. For
   Atlas SRV targets the **Stable API v1** is enabled automatically.

2. **Test Connection + Permission Check** — one button that:
   - connects with a short (~5s) `serverSelectionTimeoutMS` and maps any failure
     to a named cause (DNS/SRV failure, server-selection timeout = IP/firewall,
     authentication failed, TLS handshake error);
   - on success reports server **version, topology** (standalone / replicaSet /
     sharded / atlas), whether it is **PRIMARY**, and **edition/modules**;
   - runs a **permission precheck** against the chosen DB by probing a throwaway
     `__loadgen_permcheck` collection through all six capabilities
     (createCollection, insert, createIndex, aggregate, find, drop) and reports
     each PASS/FAIL with the **missing privilege named** on failure;
   - reports **clock skew** vs. the target (warns if > 2s).
   A real load will refuse to run until the permission check passes.

3. **Output folder** — choose where manifests + logs are written (default
   `./runs`). Validated as writable (and created if missing) before any run;
   fails loud with a named reason otherwise. Each run gets a timestamped
   subfolder `run_<UTCstamp>_<run_id>/` containing `manifest.json` + `run.log`.

Then: pick a doc count and **Seed** (idempotent), select & configure any of the
**8 workloads**, set a duration, and **Start Run**. Watch the dual-TZ live log.

---

## Workloads

See **[EXPECTED_SIGNALS.md](EXPECTED_SIGNALS.md)** for the full workload → FTDC
metric mapping. The eight classes: `connection_storm`, `indexed_reads`,
`unindexed_scans`, `inmemory_sorts`, `aggregation_pipelines`, `write_bursts`,
`update_contention`, `mixed_blend`. Each runs in its own thread pool so intensity
is independently dialable, and each logs ops-issued and achieved ops/sec.

## Seeder

Idempotent; tops up rather than duplicating. Creates:
`large_dataset` (indexed `user_id` + unindexed `random_tag`), `agg_dataset`
(arrays/subdocs), `hot_docs` (small hot set), `append_target` (write sink).
Doc counts are set from the UI. What it created is recorded in the manifest.

## Ground-truth manifest

Per run: `run_id`; start/end in **IST and UTC**; random seed; every workload that
ran with **all** parameters; per-workload ops issued / achieved ops/sec / errors;
target version / topology / edition; **redacted** connection target (host + db,
no credentials); `serverStatus.opcounters` **before/after deltas** (proof ops
landed); and an **expected FTDC signals** section for the active workloads.

## Scheduling

The UI schedules a recurring **daily window** (default 10:00–12:00 local) over a
date range (default 7 days). Each day fires a **randomized, seeded** blend (seed
logged in that day's manifest). The Schedule card offers two persistence modes:

- **In-app (APScheduler + SQLite jobstore).** Survives an app *restart*, but only
  fires while the web app is running.
- **Permanent (OS scheduler).** The same UI button registers a real OS task so the
  run fires with the app closed and survives a reboot. The backend is chosen by
  platform (`ostask.py` dispatches):
  - **Windows** — a **Task Scheduler** task (`wintask.py`). The wrapper under
    `win_tasks/` holds the URI and is locked with `icacls`. Jitter = the task's
    `RandomDelay`.
  - **macOS** — a **launchd LaunchAgent** (`mactask.py`) written to
    `~/Library/LaunchAgents/com.loadgen.daily.plist` and loaded with
    `launchctl bootstrap`. The wrapper under `mac_tasks/` holds the URI (`chmod 600`).
    launchd has no random delay, so jitter is a random sleep inside `run_window.py`
    (`LOADGEN_JITTER_MAX_SEC`); the N-day range is honoured by the wrapper
    self-removing after its end date. A reference plist lives in `launchd/`.
  - **Linux** — the UI button is not wired; use the `systemd` timer below.

  On both Windows and macOS the task runs *while you are logged on* and auto-starts
  after reboot/login. Running while **fully logged off** needs elevation (a Windows
  S4U task / a root `LaunchDaemon`). The wrapper files (`win_tasks/`, `mac_tasks/`)
  contain the connection URI and are git-ignored — never committed.

### systemd alternative (journald-logged)

`systemd/loadgen.service` + `systemd/loadgen.timer` are a robust alternative to
the in-app scheduler. The timer fires at **10:00 IST** with up to 2h
`RandomizedDelaySec` jitter (lands in the 10:00–12:00 IST band); the oneshot
service runs `run_window.py` for one seeded blend window and logs to journald.
**They are not auto-installed.** To install:

```bash
sudo cp systemd/loadgen.* /etc/systemd/system/
echo 'LOADGEN_URI=mongodb://user:pass@host:27017/?authSource=admin' | sudo tee /etc/loadgen.env
echo 'LOADGEN_DB=loadtest'        | sudo tee -a /etc/loadgen.env
echo 'LOADGEN_OUTPUT_DIR=/opt/loadgen/runs' | sudo tee -a /etc/loadgen.env
sudo chmod 600 /etc/loadgen.env           # keep the URI/creds out of the unit + journal
sudo systemctl daemon-reload
sudo systemctl enable --now loadgen.timer
journalctl -u loadgen.service -f
```

(Adjust `WorkingDirectory` / `ExecStart` paths in the unit to your install dir.)

## Preflight guards (fail loud, named reason)

Bad/unreachable URI · permission check failed · output folder not writable ·
seeder-not-run-before-load · clock skew > 2s. Each routes through the
failure-notification hook (`notify.py`, currently logs prominently — TODO: wire
a real channel).

## Teardown

Drops the load-test database **and** removes all scheduled jobs:

```bash
# From the UI: the red "Drop DB + remove all jobs" button.
# Or CLI:
./venv/Scripts/python teardown.py "mongodb://user:pass@host:27017/?authSource=admin" loadtest
```

## Timezone discipline

Operator is IST; FTDC is UTC. The UI displays IST; every manifest, log line, and
scheduled job stores **both**. UTC is the source of truth for correlation.

## Environment notes

- Driver: `pymongo` 4.x (4.17 current). Homelab target is MongoDB **Enterprise
  8.2.11**. Works unchanged against **Atlas** (`mongodb+srv://`, TLS by default).
- OMEN is the driver host and is intentionally **not** a replica-set member, to
  keep the load driver out of the metrics being validated.

## Files

```
loadgen/
  app.py            FastAPI app + routes (serves the UI)
  config.py         constants / defaults
  tz.py             dual-timezone helpers
  logbus.py         timestamped (IST+UTC) logging + UI log buffer
  db.py             MongoClient builder + URI redaction
  preflight.py      connection / permission / clock-skew / output-folder checks
  seeder.py         idempotent seeder
  manifest.py       dual-TZ, credential-redacting manifest
  runner.py         run orchestration (preflight → seed guard → workloads → manifest)
  scheduler.py      APScheduler (SQLite jobstore) — in-app schedule
  ostask.py         picks the permanent-schedule backend by platform
  wintask.py        Windows Task Scheduler integration (permanent schedule)
  mactask.py        macOS launchd integration (permanent schedule)
  run_window.py     headless single-window runner (used by systemd / Task Scheduler / launchd)
  deploy.sh         one-command deploy for macOS / Linux
  deploy.ps1        one-command deploy for Windows (PowerShell)
  teardown.py       drop DB + remove jobs (UI + CLI)
  notify.py         failure-notification hook (stub)
  workloads/        one module per workload class + registry
  static/           single-page UI (index.html, app.js, style.css)
  systemd/          loadgen.service + loadgen.timer (Linux; not auto-installed)
  launchd/          com.loadgen.daily.plist reference (macOS)
  runs/             default output dir
  EXPECTED_SIGNALS.md
  requirements.txt
```
