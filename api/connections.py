"""API endpoints for connection profile management.

Routes:
    POST   /api/connections                  - Create new profile
    GET    /api/connections                  - List all profiles
    GET    /api/connections/{id}             - Get profile by ID
    PUT    /api/connections/{id}             - Update profile
    DELETE /api/connections/{id}             - Delete profile
    POST   /api/connections/{id}/test        - Test connection (triggers discovery)
    POST   /api/connections/{id}/atlas       - Set Atlas API credentials
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.connection_manager import get_connection_manager
from core.hardware_discovery import discover_client_hardware
from db.models import init_db
import preflight
from db import resolve_db_name

router = APIRouter(prefix="/api/connections", tags=["connections"])

# Initialize database session
_, SessionLocal = init_db()


class CreateProfileRequest(BaseModel):
    name: str
    uri: str
    database_name: str
    auth_source: str | None = None


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    uri: str | None = None
    database_name: str | None = None
    auth_source: str | None = None


class SetAtlasCredentialsRequest(BaseModel):
    public_key: str
    private_key: str
    group_id: str


class ProfileResponse(BaseModel):
    id: int
    name: str
    database_name: str
    auth_source: str | None
    created_at: str
    last_used: str | None
    last_test_success: bool | None
    last_test_at: str | None

    # Discovery data
    client_cpu_cores: int | None
    client_ram_gb: float | None
    client_storage_gb: float | None
    server_version: str | None
    server_topology: str | None
    server_cluster_tier: str | None
    server_ram_gb: float | None
    server_vcpus: int | None
    server_max_connections: int | None

    # Overrides
    override_cpu_cores: int | None
    override_ram_gb: float | None

    # Atlas config (just group_id, keys are encrypted)
    atlas_group_id: str | None
    has_atlas_credentials: bool

    # Redacted URI for display
    redacted_uri: str | None

    class Config:
        from_attributes = True


def _profile_to_response(profile, manager) -> ProfileResponse:
    """Convert ConnectionProfile to response model."""
    # Get decrypted URI and redact it
    try:
        uri = manager.get_decrypted_uri(profile)
        # Basic redaction: hide password
        redacted = uri
        if "@" in uri:
            parts = uri.split("@")
            if "://" in parts[0]:
                scheme_user = parts[0].split("://")
                if ":" in scheme_user[1]:
                    user = scheme_user[1].split(":")[0]
                    redacted = f"{scheme_user[0]}://{user}:****@{parts[1]}"
    except Exception:
        redacted = "***ENCRYPTED***"

    return ProfileResponse(
        id=profile.id,
        name=profile.name,
        database_name=profile.database_name,
        auth_source=profile.auth_source,
        created_at=profile.created_at.isoformat() if profile.created_at else None,
        last_used=profile.last_used.isoformat() if profile.last_used else None,
        last_test_success=profile.last_test_success,
        last_test_at=profile.last_test_at.isoformat() if profile.last_test_at else None,
        client_cpu_cores=profile.client_cpu_cores,
        client_ram_gb=profile.client_ram_gb,
        client_storage_gb=profile.client_storage_gb,
        server_version=profile.server_version,
        server_topology=profile.server_topology,
        server_cluster_tier=profile.server_cluster_tier,
        server_ram_gb=profile.server_ram_gb,
        server_vcpus=profile.server_vcpus,
        server_max_connections=profile.server_max_connections,
        override_cpu_cores=profile.override_cpu_cores,
        override_ram_gb=profile.override_ram_gb,
        atlas_group_id=profile.atlas_group_id,
        has_atlas_credentials=profile.atlas_public_key_encrypted is not None,
        redacted_uri=redacted,
    )


@router.post("", response_model=ProfileResponse, status_code=201)
def create_profile(req: CreateProfileRequest):
    """Create a new connection profile."""
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        profile = manager.create_profile(
            session,
            name=req.name,
            uri=req.uri,
            database_name=req.database_name,
            auth_source=req.auth_source,
        )
        return _profile_to_response(profile, manager)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@router.get("", response_model=list[ProfileResponse])
def list_profiles():
    """List all connection profiles."""
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        profiles = manager.list_profiles(session)
        return [_profile_to_response(p, manager) for p in profiles]
    finally:
        session.close()


@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: int):
    """Get a specific connection profile."""
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        profile = manager.get_profile(session, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
        return _profile_to_response(profile, manager)
    finally:
        session.close()


@router.put("/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: int, req: UpdateProfileRequest):
    """Update a connection profile."""
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        profile = manager.update_profile(
            session,
            profile_id,
            name=req.name,
            uri=req.uri,
            database_name=req.database_name,
            auth_source=req.auth_source,
        )
        return _profile_to_response(profile, manager)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: int):
    """Delete a connection profile."""
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        deleted = manager.delete_profile(session, profile_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    finally:
        session.close()


@router.post("/{profile_id}/test")
def test_connection(profile_id: int):
    """Test connection and run auto-discovery.

    This endpoint:
    1. Gets the profile's decrypted URI
    2. Tests the connection using preflight.test_connection()
    3. If successful, runs hardware discovery
    4. Stores discovery results in the profile
    5. Returns full connection + discovery results
    """
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        profile = manager.get_profile(session, profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")

        # Decrypt URI
        uri = manager.get_decrypted_uri(profile)

        # Test connection
        conn_result = preflight.test_connection(uri, profile.auth_source, profile.database_name)

        # Update test result
        manager.update_test_result(session, profile_id, conn_result["ok"])

        if conn_result["ok"]:
            # Run client hardware discovery
            client_hw = discover_client_hardware()
            if "error" not in client_hw and "summary" in client_hw:
                client_data = {
                    "cpu_cores": client_hw["summary"]["cpu_cores"],
                    "ram_gb": client_hw["summary"]["ram_gb"],
                    "storage_gb": client_hw["summary"]["storage_free_gb"],
                }
                manager.update_discovery_data(session, profile_id, client_data=client_data)

            # Store server discovery data
            server_data = {
                "version": conn_result.get("server_version"),
                "topology": conn_result.get("topology"),
                "cluster_tier": None,  # TODO: Detect from Atlas API if available
                "ram_gb": None,  # TODO: Get from serverStatus if available
                "vcpus": None,
                "max_connections": None,  # TODO: Get from serverStatus
            }
            manager.update_discovery_data(session, profile_id, server_data=server_data)

            # Run permission check
            db_name = resolve_db_name(uri, profile.database_name)
            perm_result = preflight.permission_check(uri, db_name, profile.auth_source)

            # Run clock skew check
            skew_result = preflight.clock_skew_check(uri, profile.auth_source)

            # Refresh profile with updated data
            session.refresh(profile)

            return {
                "profile": _profile_to_response(profile, manager),
                "connection": conn_result,
                "permission": perm_result,
                "clock_skew": skew_result,
            }
        else:
            return {
                "profile": _profile_to_response(profile, manager),
                "connection": conn_result,
                "permission": None,
                "clock_skew": None,
            }
    finally:
        session.close()


@router.post("/{profile_id}/atlas", response_model=ProfileResponse)
def set_atlas_credentials(profile_id: int, req: SetAtlasCredentialsRequest):
    """Set Atlas API credentials for live metrics."""
    session = SessionLocal()
    manager = get_connection_manager()

    try:
        profile = manager.set_atlas_credentials(
            session,
            profile_id,
            req.public_key,
            req.private_key,
            req.group_id,
        )
        return _profile_to_response(profile, manager)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        session.close()
