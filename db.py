"""MongoClient construction + URI redaction.

The connection URI is the single source of truth for the target. We parse it,
honour optional authSource / default-DB overrides, enable the Stable API for
Atlas (mongodb+srv://), and NEVER surface credentials anywhere.
"""
from __future__ import annotations

from urllib.parse import quote_plus, urlsplit, urlunsplit

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.uri_parser import parse_uri

import config


def is_srv(uri: str) -> bool:
    return uri.strip().lower().startswith("mongodb+srv://")


def redact_uri(uri: str) -> str:
    """Return the URI with any password replaced by '****'. Best-effort: even on
    a malformed URI we never echo the raw string back."""
    try:
        parts = urlsplit(uri)
        netloc = parts.netloc
        if "@" in netloc:
            creds, host = netloc.rsplit("@", 1)
            if ":" in creds:
                user, _pw = creds.split(":", 1)
                creds = f"{user}:****"
            else:
                creds = creds  # username only, nothing to mask
            netloc = f"{creds}@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "<unparseable-uri-redacted>"


def target_summary(uri: str, default_db: str | None = None) -> dict:
    """Host + db descriptor with NO credentials — safe for logs and manifests."""
    info: dict = {"scheme": "mongodb+srv" if is_srv(uri) else "mongodb"}
    try:
        parsed = parse_uri(uri, validate=False)
        nodes = parsed.get("nodelist") or []
        info["hosts"] = [f"{h}:{p}" if p else h for (h, p) in nodes]
        info["database"] = parsed.get("database") or default_db or config.DEFAULT_DB
        opts = parsed.get("options") or {}
        if "authSource" in opts:
            info["authSource"] = opts["authSource"]
        if parsed.get("username"):
            info["username"] = parsed["username"]  # username is not secret
    except Exception:
        # Fall back to host extraction from a redacted URI.
        info["hosts"] = []
        info["database"] = default_db or config.DEFAULT_DB
    info["redacted_uri"] = redact_uri(uri)
    return info


def resolve_db_name(uri: str, default_db: str | None) -> str:
    """Database to target: explicit override wins, else URI path, else config default."""
    if default_db:
        return default_db
    try:
        parsed = parse_uri(uri, validate=False)
        if parsed.get("database"):
            return parsed["database"]
    except Exception:
        pass
    return config.DEFAULT_DB


def make_client(
    uri: str,
    auth_source: str | None = None,
    server_selection_timeout_ms: int = config.SERVER_SELECTION_TIMEOUT_MS,
    *,
    max_pool_size: int | None = None,
    app_name: str = "loadgen",
    **extra,
) -> MongoClient:
    """Build a MongoClient from the URI.

    - Short serverSelectionTimeoutMS by default (used for the probe).
    - Stable API v1 for Atlas SRV targets (avoids version coupling).
    - Optional authSource override applied on top of whatever the URI carries.
    """
    opts: dict = {
        "serverSelectionTimeoutMS": server_selection_timeout_ms,
        "connectTimeoutMS": config.CONNECT_TIMEOUT_MS,
        "socketTimeoutMS": config.SOCKET_TIMEOUT_MS,
        "appname": app_name,
    }
    if is_srv(uri):
        opts["server_api"] = ServerApi("1")
    if auth_source:
        opts["authSource"] = auth_source
    if max_pool_size is not None:
        opts["maxPoolSize"] = max_pool_size
    opts.update(extra)
    return MongoClient(uri, **opts)
