"""Teardown — drop the load-test database and remove all scheduled jobs.

Usable from the UI (POST /api/teardown) or the command line:
    python teardown.py "mongodb://user:pass@host:27017/?authSource=admin" loadtest
"""
from __future__ import annotations

import sys

import scheduler as scheduler_mod
from db import make_client, resolve_db_name, target_summary
from logbus import BUS


def teardown(uri: str, db_name: str | None = None, auth_source: str | None = None,
             *, drop_db: bool = True, remove_jobs: bool = True) -> dict:
    result: dict = {"dropped_db": None, "removed_jobs": 0, "errors": []}
    db_name = db_name or resolve_db_name(uri, None)
    BUS.warn(f"TEARDOWN requested for db='{db_name}' on "
             f"{target_summary(uri, db_name)['redacted_uri']}")

    if drop_db:
        client = None
        try:
            client = make_client(uri, auth_source=auth_source, server_selection_timeout_ms=8000)
            client.drop_database(db_name)
            result["dropped_db"] = db_name
            BUS.warn(f"dropped database '{db_name}'")
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"drop_database failed: {exc}")
            BUS.error(f"teardown: drop_database failed: {exc}")
        finally:
            if client is not None:
                client.close()

    if remove_jobs:
        try:
            result["removed_jobs"] = scheduler_mod.remove_all_jobs()
        except Exception as exc:  # noqa: BLE001
            result["errors"].append(f"remove jobs failed: {exc}")

    result["ok"] = not result["errors"]
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python teardown.py <uri> [db] [authSource]")
        raise SystemExit(2)
    uri = sys.argv[1]
    db = sys.argv[2] if len(sys.argv) > 2 else None
    auth = sys.argv[3] if len(sys.argv) > 3 else None
    res = teardown(uri, db, auth)
    print(res)
