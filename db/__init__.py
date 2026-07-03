"""Database initialization module.

Provides database engine and session management.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

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


__all__ = ["get_engine", "get_session", "init_db", "DATABASE_URL"]
