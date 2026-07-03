"""SQLAlchemy database models for V2 features.

Tables:
- connection_profiles: Stored connection profiles with encrypted URIs
- run_history: Extended run history with intent metadata
- atlas_metrics: Metric catalog (loaded from JSON)
- metric_workload_map: Metric→workload mappings
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()


class ConnectionProfile(Base):
    """Stored MongoDB connection profiles with encrypted credentials."""

    __tablename__ = "connection_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    uri_encrypted = Column(LargeBinary, nullable=False)  # Fernet encrypted
    database_name = Column(String(255), nullable=False)
    auth_source = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    last_test_success = Column(Boolean, nullable=True)
    last_test_at = Column(DateTime, nullable=True)

    # Cached discovery data (client)
    client_cpu_cores = Column(Integer, nullable=True)
    client_ram_gb = Column(Float, nullable=True)
    client_storage_gb = Column(Float, nullable=True)

    # Cached discovery data (server)
    server_version = Column(String(50), nullable=True)
    server_topology = Column(String(50), nullable=True)
    server_cluster_tier = Column(String(50), nullable=True)
    server_ram_gb = Column(Float, nullable=True)
    server_vcpus = Column(Integer, nullable=True)
    server_max_connections = Column(Integer, nullable=True)

    # User overrides
    override_cpu_cores = Column(Integer, nullable=True)
    override_ram_gb = Column(Float, nullable=True)

    # Atlas API credentials (optional, encrypted)
    atlas_public_key_encrypted = Column(LargeBinary, nullable=True)
    atlas_private_key_encrypted = Column(LargeBinary, nullable=True)
    atlas_group_id = Column(String(255), nullable=True)

    # Relationships
    runs = relationship("RunHistory", back_populates="profile")

    def __repr__(self):
        return f"<ConnectionProfile(id={self.id}, name='{self.name}', db='{self.database_name}')>"


class RunHistory(Base):
    """Extended run history with intent metadata."""

    __tablename__ = "run_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), nullable=False, unique=True, index=True)
    connection_profile_id = Column(Integer, ForeignKey("connection_profiles.id"), nullable=True)

    # Intent metadata (V2 new fields)
    intent_type = Column(String(50), nullable=True, index=True)  # connection_stress, read_performance, etc.
    intensity = Column(String(20), nullable=True)  # light, medium, heavy, extreme

    # Existing fields
    mode = Column(String(20), nullable=False)  # manual, scheduled
    started_utc = Column(DateTime, nullable=False)
    ended_utc = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)  # done, failed

    # Paths
    manifest_path = Column(Text, nullable=True)
    run_dir = Column(Text, nullable=True)

    # Configuration snapshot (full JSON)
    config_json = Column(Text, nullable=False)

    # Results summary
    ops_total = Column(Integer, nullable=True)
    errors_total = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    # Relationships
    profile = relationship("ConnectionProfile", back_populates="runs")

    def __repr__(self):
        return f"<RunHistory(run_id='{self.run_id}', intent='{self.intent_type}', status='{self.status}')>"

    @property
    def config(self) -> dict:
        """Parse config_json to dict."""
        return json.loads(self.config_json) if self.config_json else {}

    @config.setter
    def config(self, value: dict):
        """Store config as JSON string."""
        self.config_json = json.dumps(value)


class AtlasMetric(Base):
    """Atlas metric catalog (loaded from atlas_metrics.json)."""

    __tablename__ = "atlas_metrics"

    metric_name = Column(String(100), primary_key=True)
    category_id = Column(String(50), nullable=False, index=True)
    category_name = Column(String(100), nullable=False)
    unit = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)

    atlas_available = Column(Boolean, default=True)
    ftdc_available = Column(Boolean, default=True)

    baseline_low = Column(Float, nullable=True)
    baseline_high = Column(Float, nullable=True)
    alert_threshold = Column(Float, nullable=True)

    impact_level = Column(String(20), nullable=True)  # low, medium, high, critical

    # Preview image path (for Atlas graph screenshots)
    preview_image_path = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<AtlasMetric(name='{self.metric_name}', category='{self.category_name}')>"


class MetricWorkloadMap(Base):
    """Metric→Workload impact mappings."""

    __tablename__ = "metric_workload_map"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), ForeignKey("atlas_metrics.metric_name"), nullable=False, index=True)
    workload_key = Column(String(50), nullable=False, index=True)
    impact_level = Column(String(20), nullable=False)  # primary, secondary, tertiary, inverse
    confidence = Column(Float, nullable=False)  # 0.0 to 1.0
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<MetricWorkloadMap(metric='{self.metric_name}', workload='{self.workload_key}', impact='{self.impact_level}')>"


# Database initialization and session factory
def init_db(db_path: str = "./loadgen_v2.sqlite") -> tuple:
    """Initialize database and return engine and session maker.

    Args:
        db_path: Path to SQLite database file

    Returns:
        Tuple of (engine, Session class)
    """
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def load_metrics_from_json(session, json_path: str):
    """Load atlas_metrics.json into database."""
    import json

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for category in data["categories"]:
        cat_id = category["id"]
        cat_name = category["name"]

        for metric in category["metrics"]:
            existing = session.query(AtlasMetric).filter_by(metric_name=metric["name"]).first()
            if existing:
                continue  # Skip if already loaded

            m = AtlasMetric(
                metric_name=metric["name"],
                category_id=cat_id,
                category_name=cat_name,
                unit=metric["unit"],
                description=metric["description"],
                atlas_available=metric["atlas_available"],
                ftdc_available=metric["ftdc_available"],
                baseline_low=metric.get("baseline_low"),
                baseline_high=metric.get("baseline_high"),
                alert_threshold=metric.get("alert_threshold"),
                impact_level=metric.get("impact_level"),
            )
            session.add(m)

    session.commit()


def load_metric_workload_map_from_json(session, json_path: str):
    """Load metric_workload_map.json into database."""
    import json

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for metric_name, mappings in data["mappings"].items():
        for mapping in mappings:
            existing = session.query(MetricWorkloadMap).filter_by(
                metric_name=metric_name,
                workload_key=mapping["workload"]
            ).first()
            if existing:
                continue  # Skip if already loaded

            m = MetricWorkloadMap(
                metric_name=metric_name,
                workload_key=mapping["workload"],
                impact_level=mapping["impact"],
                confidence=mapping["confidence"],
                notes=mapping.get("note"),
            )
            session.add(m)

    session.commit()


if __name__ == "__main__":
    # Test database creation
    import os

    db_path = "./loadgen_v2_test.sqlite"

    # Clean up test DB if exists
    if os.path.exists(db_path):
        os.remove(db_path)

    engine, SessionLocal = init_db(db_path)
    session = SessionLocal()

    print(f"✓ Database created at {db_path}")
    print(f"✓ Tables: {', '.join(Base.metadata.tables.keys())}")

    # Test loading metrics
    metrics_path = "../data/atlas_metrics.json"
    if os.path.exists(metrics_path):
        load_metrics_from_json(session, metrics_path)
        count = session.query(AtlasMetric).count()
        print(f"✓ Loaded {count} metrics from atlas_metrics.json")

    # Test loading metric map
    map_path = "../data/metric_workload_map.json"
    if os.path.exists(map_path):
        load_metric_workload_map_from_json(session, map_path)
        count = session.query(MetricWorkloadMap).count()
        print(f"✓ Loaded {count} metric→workload mappings")

    session.close()
    print("✓ Database initialization test passed")
