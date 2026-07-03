"""connection_storm — open and hold many concurrent connections.

Expected FTDC signal: connections.current ↑, globalLock.activeClients ↑.

Unlike the other workloads this does not issue a tight op loop; it opens N
*separate* clients (each forced to establish at least one socket) and holds them
open for the duration, pinging periodically to keep them active.
"""
from __future__ import annotations

import threading
import time

from db import make_client
from tz import dual, now_utc

from .base import Workload, WorkloadResult


class ConnectionStorm(Workload):
    key = "connection_storm"
    label = "Connection storm"

    @staticmethod
    def default_params() -> dict:
        return {"connection_count": 50, "ping_interval_s": 5}

    def run(self, client, db_name, params, duration_seconds, stop_event, log) -> WorkloadResult:
        params = {**self.default_params(), **(params or {})}
        n = int(params["connection_count"])
        ping_interval = float(params.get("ping_interval_s", 5))
        # We need the URI to open independent clients; the runner stashes it on
        # the shared client object as `_loadgen_uri` / `_loadgen_auth_source`.
        uri = getattr(client, "_loadgen_uri", None)
        auth_source = getattr(client, "_loadgen_auth_source", None)
        log.info(f"workload 'connection_storm': opening {n} connections, holding for {duration_seconds}s")
        start = time.time()
        started = dual(now_utc())

        clients = []
        opened = 0
        errors = 0
        # maxPoolSize=2 per client so each client really holds its own sockets
        # rather than multiplexing through one pool.
        for i in range(n):
            if stop_event.is_set():
                break
            try:
                c = make_client(uri, auth_source=auth_source, max_pool_size=2,
                                server_selection_timeout_ms=5000, app_name=f"loadgen-storm-{i}")
                c.admin.command("ping")  # force a real socket + handshake
                clients.append(c)
                opened += 1
            except Exception as exc:  # noqa: BLE001
                errors += 1
                log.warn(f"connection_storm: failed to open connection {i}: {exc}")

        log.info(f"connection_storm: {opened}/{n} connections live; holding")

        # Hold + periodic keepalive ping until the duration elapses.
        pings = 0
        while not stop_event.wait(ping_interval):
            if time.time() - start >= duration_seconds:
                break
            for c in clients:
                try:
                    c.admin.command("ping")
                    pings += 1
                except Exception:  # noqa: BLE001
                    errors += 1

        for c in clients:
            try:
                c.close()
            except Exception:
                pass

        elapsed = time.time() - start
        res = WorkloadResult(
            name=self.key,
            params=params,
            started=started,
            ended=dual(now_utc()),
            ops_issued=opened + pings,
            errors=errors,
            duration_seconds=elapsed,
            achieved_ops_per_sec=((opened + pings) / elapsed if elapsed > 0 else 0.0),
            extra={"connections_opened": opened, "keepalive_pings": pings},
        )
        log.info(f"connection_storm: done opened={opened} pings={pings} errors={errors}")
        return res
