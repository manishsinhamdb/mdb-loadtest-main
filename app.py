"""FastAPI application: serves the single-page UI and the JSON API.

Routes:
  GET  /                       -> UI
  GET  /api/catalog            -> workload catalog + defaults
  POST /api/test-connection    -> connection + permission + clock-skew preflight
  POST /api/check-output       -> validate/create output folder
  POST /api/seed               -> idempotent seeder (background)
  POST /api/run                -> start a load run (background)
  GET  /api/run/{run_id}       -> run status
  GET  /api/logs?since=N       -> poll the dual-TZ log buffer
  POST /api/schedule           -> schedule a daily window
  GET  /api/schedule           -> list scheduled jobs
  DELETE /api/schedule/{job_id}-> remove a scheduled job
  POST /api/teardown           -> drop DB + remove all jobs
"""
from __future__ import annotations

import os
import threading

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import preflight
import runner
import scheduler as scheduler_mod
import seeder as seeder_mod
import teardown as teardown_mod
import ostask
from db import make_client, resolve_db_name
from logbus import BUS
from tz import dual
from workloads import catalog

# V2 imports
from api.connections import router as connections_router

HERE = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(HERE, "static")

app = FastAPI(title="loadgen — MongoDB Load Generator + Validation Harness",
              version=config.APP_VERSION)

# V2 routes
app.include_router(connections_router)


# --------------------------------------------------------------------------
# Request models
# --------------------------------------------------------------------------
class ConnReq(BaseModel):
    uri: str
    auth_source: str | None = None
    default_db: str | None = None


class OutputReq(BaseModel):
    path: str = config.DEFAULT_OUTPUT_DIR


class SeedReq(BaseModel):
    uri: str
    auth_source: str | None = None
    default_db: str | None = None
    large_count: int = config.DEFAULT_SEED_LARGE_COUNT
    agg_count: int = config.DEFAULT_SEED_AGG_COUNT
    hot_docs: int = config.DEFAULT_HOT_DOCS
    seed: int | None = None


class RunReq(BaseModel):
    uri: str
    auth_source: str | None = None
    default_db: str | None = None
    output_dir: str = config.DEFAULT_OUTPUT_DIR
    duration_seconds: float = 60
    seed: int | None = None
    workloads: dict = {}            # {key: params_dict}
    auto_seed: bool = False
    seed_params: dict = {}
    ignore_skew: bool = False


class ScheduleReq(BaseModel):
    uri: str
    auth_source: str | None = None
    default_db: str | None = None
    output_dir: str = config.DEFAULT_OUTPUT_DIR
    duration_seconds: float = 600
    start_ist: str = config.DEFAULT_WINDOW_START_IST
    end_ist: str = config.DEFAULT_WINDOW_END_IST
    days: int = config.DEFAULT_SCHEDULE_DAYS
    base_seed: int = 1234
    blend_threads: int = 12
    workloads: dict = {}            # empty -> seeded mixed_blend per day


class PersistentReq(BaseModel):
    uri: str
    auth_source: str | None = None
    default_db: str | None = None
    output_dir: str = config.DEFAULT_OUTPUT_DIR
    duration_seconds: float = 600
    start_ist: str = config.DEFAULT_WINDOW_START_IST
    days: int = config.DEFAULT_SCHEDULE_DAYS
    base_seed: int = 1234
    blend_threads: int = 12
    random_delay_min: int = 15
    seed_large: int = config.SMOKE_SEED_LARGE_COUNT
    seed_agg: int = 50000
    seed_hot: int = config.DEFAULT_HOT_DOCS


class TeardownReq(BaseModel):
    uri: str
    auth_source: str | None = None
    default_db: str | None = None
    drop_db: bool = True
    remove_jobs: bool = True


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------
@app.get("/api/catalog")
def api_catalog():
    return {
        "workloads": catalog(),
        "collections": [
            {"name": config.COLL_LARGE,
             "role": "Large dataset — INDEXED user_id + UNINDEXED random_tag. "
                     "Targets indexed_reads, unindexed_scans, inmemory_sorts.",
             "indexes": "user_id_idx (user_id); random_tag intentionally unindexed"},
            {"name": config.COLL_AGG,
             "role": "Arrays/subdocs (items, tags). Target for aggregation_pipelines.",
             "indexes": "category_idx (category)"},
            {"name": config.COLL_HOT,
             "role": "Small hot set. Target for update_contention.",
             "indexes": "_id (default)"},
            {"name": config.COLL_APPEND,
             "role": "Append sink. Target for write_bursts.",
             "indexes": "_id (default)"},
        ],
        "defaults": {
            "output_dir": config.DEFAULT_OUTPUT_DIR,
            "db": config.DEFAULT_DB,
            "window_start_ist": config.DEFAULT_WINDOW_START_IST,
            "window_end_ist": config.DEFAULT_WINDOW_END_IST,
            "schedule_days": config.DEFAULT_SCHEDULE_DAYS,
            "smoke_large_count": config.SMOKE_SEED_LARGE_COUNT,
            "large_count": config.DEFAULT_SEED_LARGE_COUNT,
            "persistent_backend": ostask.backend_name(),
        },
        "now": dual(),
    }


@app.post("/api/test-connection")
def api_test_connection(req: ConnReq):
    BUS.info("UI: Test-Connection requested")
    conn = preflight.test_connection(req.uri, req.auth_source, req.default_db)
    out = {"connection": conn}
    if conn["ok"]:
        db_name = resolve_db_name(req.uri, req.default_db)
        out["permission"] = preflight.permission_check(req.uri, db_name, req.auth_source)
        out["clock_skew"] = preflight.clock_skew_check(req.uri, req.auth_source)
        out["db"] = db_name
    return out


@app.post("/api/check-output")
def api_check_output(req: OutputReq):
    return preflight.check_output_folder(req.path)


_seed_state: dict = {"running": False, "result": None, "error": None}


@app.post("/api/seed")
def api_seed(req: SeedReq):
    if _seed_state["running"]:
        return JSONResponse({"error": "a seed is already running"}, status_code=409)

    def _do():
        _seed_state.update(running=True, result=None, error=None)
        client = None
        try:
            client = make_client(req.uri, auth_source=req.auth_source,
                                 server_selection_timeout_ms=8000, max_pool_size=50)
            db_name = resolve_db_name(req.uri, req.default_db)
            res = seeder_mod.seed(client, db_name, BUS,
                                 large_count=req.large_count, agg_count=req.agg_count,
                                 hot_docs=req.hot_docs, seed=req.seed)
            _seed_state["result"] = res
        except Exception as exc:  # noqa: BLE001
            _seed_state["error"] = str(exc)
            BUS.error(f"seed failed: {exc}")
        finally:
            if client is not None:
                client.close()
            _seed_state["running"] = False

    threading.Thread(target=_do, daemon=True).start()
    return {"started": True}


@app.get("/api/seed")
def api_seed_status():
    return _seed_state


@app.post("/api/run")
def api_run(req: RunReq):
    run_id = runner.start_run_async(req.model_dump(), mode="manual")
    return {"run_id": run_id}


@app.get("/api/run/{run_id}")
def api_run_status(run_id: str):
    st = runner.get_run(run_id)
    if not st:
        return JSONResponse({"error": "unknown run_id"}, status_code=404)
    return {
        "run_id": st.run_id,
        "status": st.status,
        "phase": st.phase,
        "error": st.error,
        "manifest_path": st.manifest_path,
        "run_dir": st.run_dir,
        "summary": st.summary,
        "started": st.started,
    }


@app.get("/api/logs")
def api_logs(since: int = 0):
    return {"logs": BUS.since(since)}


@app.post("/api/schedule")
def api_schedule(req: ScheduleReq):
    cfg = {
        "uri": req.uri, "auth_source": req.auth_source, "default_db": req.default_db,
        "output_dir": req.output_dir, "duration_seconds": req.duration_seconds,
        "workloads": req.workloads, "blend_threads": req.blend_threads,
    }
    info = scheduler_mod.add_daily_window(
        cfg, start_ist=req.start_ist, end_ist=req.end_ist, days=req.days,
        base_seed=req.base_seed,
    )
    return {"scheduled": info}


@app.get("/api/schedule")
def api_schedule_list():
    return {"jobs": scheduler_mod.list_jobs()}


@app.delete("/api/schedule/{job_id}")
def api_schedule_delete(job_id: str):
    return {"removed": scheduler_mod.remove_job(job_id)}


@app.post("/api/persistent-schedule")
def api_persistent_create(req: PersistentReq):
    return ostask.create_persistent_task(req.model_dump())


@app.get("/api/persistent-schedule")
def api_persistent_list():
    return ostask.list_persistent_tasks()


@app.delete("/api/persistent-schedule")
def api_persistent_delete():
    return ostask.remove_persistent_task()


@app.post("/api/teardown")
def api_teardown(req: TeardownReq):
    db_name = resolve_db_name(req.uri, req.default_db)
    return teardown_mod.teardown(req.uri, db_name, req.auth_source,
                                drop_db=req.drop_db, remove_jobs=req.remove_jobs)


@app.on_event("startup")
def _startup():
    BUS.info(f"loadgen v{config.APP_VERSION} started — open the UI at the host:port uvicorn is bound to")
