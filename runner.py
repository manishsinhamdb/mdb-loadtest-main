"""Run orchestration — the heart of the harness.

A run:
  1. preflight: connection -> permission -> clock skew  (FAIL LOUD on any).
  2. seeder-not-run guard (unless auto-seed requested).
  3. capture serverStatus opcounters BEFORE.
  4. run selected workloads concurrently for `duration_seconds`.
  5. capture opcounters AFTER -> deltas (proves ops landed on the server).
  6. write manifest.json + run.log under the chosen output folder.

Runs execute on a background thread; live progress is observable via the log
bus and the in-memory RunState. Credentials never touch the manifest or logs.
"""
from __future__ import annotations

import threading
import uuid

import config
import preflight
import seeder as seeder_mod
from db import make_client, resolve_db_name, target_summary
from logbus import BUS
from manifest import Manifest
from notify import notify_failure
from tz import dual, now_utc
from workloads import get_workload

OPCOUNTER_KEYS = ["insert", "query", "update", "delete", "getmore", "command"]


class RunState:
    """Live, in-memory state for one run (polled by the UI)."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.status = "starting"   # starting|preflight|seeding|running|done|failed
        self.phase = ""
        self.manifest_path: str | None = None
        self.run_dir: str | None = None
        self.error: str | None = None
        self.summary: dict | None = None
        self.started = dual(now_utc())


# Process-wide registry of runs.
RUNS: dict[str, RunState] = {}
_RUNS_LOCK = threading.Lock()


def _opcounters(client) -> dict | None:
    try:
        ss = client.admin.command("serverStatus")
        oc = ss.get("opcounters", {})
        return {k: int(oc.get(k, 0)) for k in OPCOUNTER_KEYS}
    except Exception as exc:  # noqa: BLE001
        BUS.warn(f"could not read opcounters: {exc}")
        return None


def execute_run(cfg: dict, *, mode: str = "manual", run_id: str | None = None) -> RunState:
    """Synchronous run executor (call from a background thread).

    cfg keys:
      uri, auth_source, default_db, output_dir, duration_seconds,
      workloads: {key: params_dict, ...}, seed,
      auto_seed: bool, seed_params: {...}
    """
    run_id = run_id or uuid.uuid4().hex[:12]
    state = RunState(run_id)
    with _RUNS_LOCK:
        RUNS[run_id] = state

    uri = cfg["uri"]
    auth_source = cfg.get("auth_source")
    default_db = cfg.get("default_db")
    db_name = resolve_db_name(uri, default_db)
    output_dir = cfg.get("output_dir") or config.DEFAULT_OUTPUT_DIR
    duration = float(cfg.get("duration_seconds", 60))
    seed = cfg.get("seed")
    selected = cfg.get("workloads") or {}

    manifest = Manifest(run_id, output_dir, mode=mode)
    manifest.set_seed(seed)

    # Use the global bus (so the UI poll sees run lines); we attach a per-run
    # log file to it for the duration of this run.
    log = BUS

    def fail(subject: str, detail: str):
        state.status = "failed"
        state.error = f"{subject}: {detail}"
        manifest.add_error(state.error)
        log.error(f"RUN {run_id} FAILED — {state.error}")
        notify_failure(subject, detail, run_id=run_id)
        try:
            manifest.write()
            state.manifest_path = manifest.manifest_path
            state.run_dir = manifest.run_dir
        except Exception:
            pass

    try:
        # --- output folder (writable?) ------------------------------------
        state.status = "preflight"; state.phase = "output_folder"
        of = preflight.check_output_folder(output_dir)
        if not of["ok"]:
            return _ret(state, fail("OUTPUT_FOLDER_NOT_WRITABLE", of.get("error", "")))
        manifest.output_dir = of["path"]
        manifest.run_dir = manifest.run_dir  # already computed from output_dir
        manifest.ensure_run_dir()
        # attach run log file
        fh = open(manifest.log_path, "w", encoding="utf-8")
        BUS.attach_file(fh)
        log.info(f"RUN {run_id} starting (mode={mode}) db='{db_name}' duration={duration}s")
        log.info(f"target: {target_summary(uri, default_db)['redacted_uri']}")

        # --- connection ----------------------------------------------------
        state.phase = "connection"
        conn = preflight.test_connection(uri, auth_source, default_db)
        if not conn["ok"]:
            err = conn.get("error", {})
            return _ret(state, fail("CONNECTION_FAILED",
                                    f"{err.get('cause')}: {err.get('hint')}"))
        manifest.set_target({
            **conn["target"],
            "server_version": conn.get("server_version"),
            "topology": conn.get("topology"),
            "is_primary": conn.get("is_primary"),
            "edition": conn.get("edition"),
            "modules": conn.get("modules"),
            "set_name": conn.get("set_name"),
        })
        log.info(f"connected: v{conn.get('server_version')} topology={conn.get('topology')} "
                 f"primary={conn.get('is_primary')} edition={conn.get('edition')}")

        # --- permission ----------------------------------------------------
        state.phase = "permission"
        perm = preflight.permission_check(uri, db_name, auth_source)
        if not perm["ok"]:
            return _ret(state, fail("PERMISSION_CHECK_FAILED",
                                    f"missing: {perm['missing']} ; details: "
                                    f"{[c['detail'] for c in perm['capabilities'] if not c['pass']]}"))
        log.info(f"permission check PASSED on '{db_name}' (all 6 capabilities)")

        # --- clock skew ----------------------------------------------------
        state.phase = "clock_skew"
        skew = preflight.clock_skew_check(uri, auth_source)
        manifest.set_clock_skew(skew)
        if skew.get("warning"):
            log.warn(skew["warning"])
            notify_failure("CLOCK_SKEW_WARNING", skew["warning"], run_id=run_id)
            if not cfg.get("ignore_skew"):
                return _ret(state, fail("CLOCK_SKEW_EXCEEDED", skew["warning"]))
        else:
            log.info(f"clock skew OK: {skew.get('skew_seconds')}s (<= "
                     f"{config.MAX_CLOCK_SKEW_SECONDS}s)")

        # --- build the working client (longer timeouts for the actual load) -
        client = make_client(uri, auth_source=auth_source,
                             server_selection_timeout_ms=8000, max_pool_size=200)
        # Stash for connection_storm to open its own independent clients.
        client._loadgen_uri = uri
        client._loadgen_auth_source = auth_source

        # --- seeder guard / auto-seed -------------------------------------
        if cfg.get("auto_seed"):
            state.status = "seeding"; state.phase = "seeding"
            sp = cfg.get("seed_params") or {}
            seeder_summary = seeder_mod.seed(client, db_name, log, seed=seed, **sp)
            manifest.set_seeder(seeder_summary)
        else:
            seeded, why = seeder_mod.is_seeded(client, db_name)
            if not seeded:
                client.close()
                return _ret(state, fail("SEEDER_NOT_RUN", why))
            manifest.set_seeder({"db": db_name, "note": "pre-existing (guard passed)", "verified": True})

        # --- opcounters BEFORE --------------------------------------------
        before = _opcounters(client)
        log.info(f"opcounters BEFORE: {before}")

        # --- run workloads -------------------------------------------------
        state.status = "running"; state.phase = "workloads"
        manifest.set_started(now_utc())
        stop_event = threading.Event()
        threads: list[threading.Thread] = []
        results: dict[str, object] = {}

        def _run_one(key, params):
            wl = get_workload(key)
            results[key] = wl.run(client, db_name, params, duration, stop_event, log)

        for key, params in selected.items():
            t = threading.Thread(target=_run_one, args=(key, params), daemon=True)
            t.start()
            threads.append(t)
            log.info(f"launched workload '{key}'")

        # Master timer: all workloads honour the same stop_event/duration.
        stop_event.wait(duration)
        stop_event.set()
        for t in threads:
            t.join(timeout=30)

        manifest.set_ended(now_utc())
        for key in selected:
            r = results.get(key)
            if r is not None:
                manifest.add_workload_result(r.to_dict())

        # --- opcounters AFTER ---------------------------------------------
        after = _opcounters(client)
        log.info(f"opcounters AFTER: {after}")
        manifest.set_opcounters(before, after)
        if before and after:
            delta = manifest.data["opcounters"]["delta"]
            log.info(f"opcounters DELTA (proves ops landed): {delta}")

        client.close()

        # --- write manifest -----------------------------------------------
        path = manifest.write()
        state.manifest_path = path
        state.run_dir = manifest.run_dir
        state.status = "done"; state.phase = "complete"
        state.summary = {
            "workloads": [w["name"] for w in manifest.data["workloads"]],
            "opcounter_delta": manifest.data["opcounters"]["delta"],
            "manifest": path,
            "run_dir": manifest.run_dir,
        }
        log.info(f"RUN {run_id} COMPLETE — manifest at {path}")
        return state

    except Exception as exc:  # noqa: BLE001
        return _ret(state, fail("RUN_CRASHED", str(exc)))
    finally:
        BUS.detach_file()


def _ret(state: RunState, _none) -> RunState:
    return state


def start_run_async(cfg: dict, *, mode: str = "manual") -> str:
    """Kick off a run on a daemon thread; return its run_id immediately."""
    run_id = uuid.uuid4().hex[:12]
    t = threading.Thread(target=execute_run, args=(cfg,),
                         kwargs={"mode": mode, "run_id": run_id}, daemon=True)
    t.start()
    return run_id


def get_run(run_id: str) -> RunState | None:
    with _RUNS_LOCK:
        return RUNS.get(run_id)
