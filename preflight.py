"""Preflight guards — fail loud with a NAMED reason.

  * test_connection  — connect with a short timeout; map errors to causes; report
                       version / topology / primary / edition.
  * permission_check — probe a throwaway collection for the six capabilities a
                       load test needs; report PASS/FAIL + the missing privilege.
  * clock_skew_check — compare OMEN's clock to the server's; WARN if > 2s.
  * check_output_folder — verify (and create) the chosen output dir is writable.
"""
from __future__ import annotations

import os
import time
from datetime import timezone

from bson import ObjectId
from pymongo.errors import (
    ConfigurationError,
    ExecutionTimeout,
    OperationFailure,
    ServerSelectionTimeoutError,
)

import config
from db import is_srv, make_client, resolve_db_name, target_summary
from tz import dual, now_utc


# --------------------------------------------------------------------------
# Error mapping
# --------------------------------------------------------------------------
def _map_connection_error(exc: Exception, uri: str) -> dict:
    """Translate a pymongo connection exception into an operator-actionable cause."""
    text = str(exc)
    low = text.lower()

    if isinstance(exc, ConfigurationError):
        # SRV resolution failures usually surface here.
        if "srv" in low or "dns" in low or "resolve" in low or "name" in low:
            return {
                "cause": "DNS_SRV_FAILURE",
                "hint": "DNS/SRV lookup failed — Atlas cluster may be paused/deleted, "
                        "or DNS cannot resolve the SRV record for this host.",
            }
        return {"cause": "CONFIG_ERROR", "hint": text}

    if isinstance(exc, ServerSelectionTimeoutError):
        if "authentication" in low or "auth failed" in low:
            return {"cause": "AUTH_FAILED", "hint": "Authentication failed — wrong username/password."}
        if "ssl" in low or "tls" in low or "handshake" in low or "certificate" in low:
            return {"cause": "TLS_ERROR", "hint": "TLS handshake error — check TLS settings / CA / cert."}
        return {
            "cause": "SERVER_SELECTION_TIMEOUT",
            "hint": "Could not reach a server in time — IP not on Atlas access list, "
                    "firewall blocking, or host unreachable.",
        }

    if isinstance(exc, OperationFailure):
        if exc.code in (18, 8000) or "authentication failed" in low:
            return {"cause": "AUTH_FAILED", "hint": "Authentication failed — wrong username/password."}
        if exc.code == 13 or "not authorized" in low:
            return {"cause": "NOT_AUTHORIZED", "hint": f"Authenticated but not authorized: {text}"}
        return {"cause": "OPERATION_FAILURE", "hint": text}

    if "ssl" in low or "tls" in low or "handshake" in low or "certificate" in low:
        return {"cause": "TLS_ERROR", "hint": "TLS handshake error — check TLS settings / CA / cert."}

    return {"cause": "UNKNOWN", "hint": text}


def _topology_from_hello(hello: dict, uri: str) -> str:
    if hello.get("msg") == "isdbgrid":
        return "sharded"
    if hello.get("setName"):
        return "atlas/replicaSet" if is_srv(uri) else "replicaSet"
    if is_srv(uri):
        return "atlas"
    return "standalone"


def test_connection(uri: str, auth_source: str | None = None, default_db: str | None = None) -> dict:
    """Attempt connection and report a rich result dict. Never raises."""
    result: dict = {
        "ok": False,
        "at": dual(),
        "target": target_summary(uri, default_db),
    }
    client = None
    try:
        client = make_client(uri, auth_source=auth_source)
        # hello triggers server selection within the short timeout.
        hello = client.admin.command("hello")
        try:
            build = client.admin.command("buildInfo")
        except OperationFailure:
            build = {}
        result.update(
            {
                "ok": True,
                "server_version": build.get("version") or hello.get("version"),
                "topology": _topology_from_hello(hello, uri),
                "is_primary": bool(hello.get("isWritablePrimary") or hello.get("ismaster")),
                "set_name": hello.get("setName"),
                "modules": build.get("modules", []),
                "edition": "enterprise" if "enterprise" in (build.get("modules") or []) else "community",
                "max_wire_version": hello.get("maxWireVersion"),
            }
        )
    except Exception as exc:  # noqa: BLE001 — we deliberately catch and classify all
        result["error"] = {"message": str(exc), **_map_connection_error(exc, uri)}
    finally:
        if client is not None:
            client.close()
    return result


# --------------------------------------------------------------------------
# Permission precheck
# --------------------------------------------------------------------------
_CAPS = ["createCollection", "insert", "createIndex", "aggregate", "find", "drop"]


def _privilege_hint(cap: str, db_name: str) -> str:
    base = f"user lacks the privilege for '{cap}' on '{db_name}'"
    if cap in ("insert", "find", "createIndex", "createCollection"):
        return f"{base} — grant readWrite (or dbAdmin for index/collection DDL) on {db_name}."
    if cap == "aggregate":
        return f"{base} — grant readWrite/read on {db_name}."
    if cap == "drop":
        return f"{base} — grant dbAdmin (or readWrite) on {db_name}."
    return base


def permission_check(uri: str, db_name: str, auth_source: str | None = None) -> dict:
    """Probe a throwaway collection for the six capabilities a load test needs.

    Returns {ok, db, capabilities: [{name, pass, detail}], missing: [...]}.
    """
    caps: list[dict] = []
    client = None
    coll_name = config.PERMCHECK_COLLECTION

    def record(name: str, ok: bool, detail: str = ""):
        caps.append({"name": name, "pass": ok, "detail": detail})

    try:
        client = make_client(uri, auth_source=auth_source)
        db = client[db_name]
        # Clean any leftover from a previous aborted check.
        try:
            db[coll_name].drop()
        except Exception:
            pass

        # 1. createCollection
        try:
            db.create_collection(coll_name)
            record("createCollection", True)
        except OperationFailure as e:
            record("createCollection", False, _privilege_hint("createCollection", db_name) + f" [{e.code}: {e}]")

        coll = db[coll_name]
        doc_id = ObjectId()

        # 2. insert
        try:
            coll.insert_one({"_id": doc_id, "probe": True, "n": 1})
            record("insert", True)
        except OperationFailure as e:
            record("insert", False, _privilege_hint("insert", db_name) + f" [{e.code}: {e}]")

        # 3. createIndex
        try:
            coll.create_index("n", name="loadgen_permcheck_idx")
            record("createIndex", True)
        except OperationFailure as e:
            record("createIndex", False, _privilege_hint("createIndex", db_name) + f" [{e.code}: {e}]")

        # 4. aggregate
        try:
            list(coll.aggregate([{"$match": {"probe": True}}, {"$count": "c"}]))
            record("aggregate", True)
        except OperationFailure as e:
            record("aggregate", False, _privilege_hint("aggregate", db_name) + f" [{e.code}: {e}]")

        # 5. find (read back)
        try:
            _ = coll.find_one({"_id": doc_id})
            record("find", True)
        except OperationFailure as e:
            record("find", False, _privilege_hint("find", db_name) + f" [{e.code}: {e}]")

        # 6. drop
        try:
            coll.drop()
            record("drop", True)
        except OperationFailure as e:
            record("drop", False, _privilege_hint("drop", db_name) + f" [{e.code}: {e}]")

    except Exception as exc:  # noqa: BLE001
        # Connection-level failure: report everything not-yet-checked as failed.
        done = {c["name"] for c in caps}
        for cap in _CAPS:
            if cap not in done:
                record(cap, False, f"could not run check: {exc}")
    finally:
        if client is not None:
            # Best-effort cleanup of the probe collection.
            try:
                client[db_name][coll_name].drop()
            except Exception:
                pass
            client.close()

    missing = [c["name"] for c in caps if not c["pass"]]
    return {"ok": len(missing) == 0, "db": db_name, "capabilities": caps, "missing": missing, "at": dual()}


# --------------------------------------------------------------------------
# Clock skew
# --------------------------------------------------------------------------
def clock_skew_check(uri: str, auth_source: str | None = None) -> dict:
    """Compare OMEN's clock to the server's localTime. WARN if skew > threshold."""
    client = None
    try:
        client = make_client(uri, auth_source=auth_source)
        t0 = time.time()
        status = client.admin.command("serverStatus")
        t1 = time.time()
        server_local = status.get("localTime")  # bson datetime (UTC)
        if server_local is None:
            return {"ok": False, "error": "serverStatus returned no localTime"}
        if server_local.tzinfo is None:
            server_local = server_local.replace(tzinfo=timezone.utc)
        # Midpoint of the round-trip is our best estimate of "now" on OMEN.
        omen_mid = (t0 + t1) / 2.0
        server_epoch = server_local.timestamp()
        skew = server_epoch - omen_mid
        within = abs(skew) <= config.MAX_CLOCK_SKEW_SECONDS
        return {
            "ok": within,
            "skew_seconds": round(skew, 3),
            "threshold_seconds": config.MAX_CLOCK_SKEW_SECONDS,
            "server_localtime": dual(server_local),
            "omen_time": dual(now_utc()),
            "warning": None if within else (
                f"Clock skew {skew:+.3f}s exceeds {config.MAX_CLOCK_SKEW_SECONDS}s — "
                "FTDC correlation would be corrupted. Sync NTP on OMEN and/or the server."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    finally:
        if client is not None:
            client.close()


# --------------------------------------------------------------------------
# Output folder
# --------------------------------------------------------------------------
def check_output_folder(path: str) -> dict:
    """Verify the chosen output dir exists (create if missing) and is writable."""
    try:
        abspath = os.path.abspath(path)
        os.makedirs(abspath, exist_ok=True)
        probe = os.path.join(abspath, ".loadgen_write_probe")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(probe)
        return {"ok": True, "path": abspath, "writable": True}
    except PermissionError:
        return {"ok": False, "path": os.path.abspath(path), "writable": False,
                "error": f"Output folder not writable (permission denied): {path}"}
    except OSError as exc:
        return {"ok": False, "path": os.path.abspath(path), "writable": False,
                "error": f"Output folder unusable: {exc}"}
