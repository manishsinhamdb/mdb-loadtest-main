"""Database and MongoDB client utilities.

V2: SQLAlchemy for connection profiles + run history
V1: MongoDB client construction and URI handling
"""
from __future__ import annotations

import os
from urllib.parse import quote_plus, urlsplit, urlunsplit

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.uri_parser import parse_uri
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

import config


# =============================================================================
# V2: SQLAlchemy Database (connection profiles, run history)
# =============================================================================

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "loadtest.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create database engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False
        )
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()


def init_db():
    """Initialize database tables."""
    from db.models import Base
    Base.metadata.create_all(bind=get_engine())


# =============================================================================
# V1: MongoDB Client Construction + URI Utilities
# =============================================================================

def is_srv(uri: str) -> bool:
    """Check if URI uses SRV format (mongodb+srv://)."""
    return uri.strip().lower().startswith("mongodb+srv://")


def redact_uri(uri: str) -> str:
    """Return the URI with any password replaced by '****'."""
    try:
        parts = urlsplit(uri)
        netloc = parts.netloc
        if "@" in netloc:
            creds, host = netloc.rsplit("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                netloc = f"{user}:****@{host}"
            else:
                netloc = f"****@{host}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return "mongodb://****@<malformed-uri>"


def make_client(
    uri: str,
    *,
    auth_source: str | None = None,
    server_selection_timeout_ms: int = 5000,
    max_pool_size: int = 10,
) -> MongoClient:
    """Create a MongoClient with optional authSource override."""
    options = {
        "serverSelectionTimeoutMS": server_selection_timeout_ms,
        "maxPoolSize": max_pool_size,
    }

    if auth_source:
        options["authSource"] = auth_source

    # Enable Stable API for SRV connections (Atlas)
    if is_srv(uri):
        options["server_api"] = ServerApi("1", strict=False)

    return MongoClient(uri, **options)


def resolve_db_name(uri: str, default_db: str | None = None) -> str:
    """Resolve database name from URI or default."""
    try:
        parsed = parse_uri(uri)
        db_from_uri = parsed.get("database")
        if db_from_uri:
            return db_from_uri
    except Exception:
        pass

    return default_db or config.DEFAULT_DB


def target_summary(uri: str, default_db: str | None = None) -> dict:
    """Return a JSON-safe summary of the target (redacted URI + resolved DB)."""
    return {
        "redacted_uri": redact_uri(uri),
        "database": resolve_db_name(uri, default_db),
    }


__all__ = [
    # V2 SQLAlchemy
    "get_engine",
    "get_session",
    "init_db",
    "DATABASE_URL",
    # V1 MongoDB
    "is_srv",
    "redact_uri",
    "make_client",
    "resolve_db_name",
    "target_summary",
]
