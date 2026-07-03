"""API endpoints for hardware discovery.

Routes:
    GET  /api/discovery/client    - Get client machine specs
    POST /api/discovery/server    - Discover server specs (requires connection)
"""
from __future__ import annotations

from fastapi import APIRouter

from core.hardware_discovery import discover_client_hardware

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


@router.get("/client")
def get_client_hardware():
    """Get client machine hardware specifications.

    Returns auto-detected CPU, RAM, disk, network info.
    """
    return discover_client_hardware()


@router.post("/server")
def discover_server(uri: str, auth_source: str | None = None):
    """Discover server specifications from MongoDB.

    Args:
        uri: MongoDB connection URI
        auth_source: Optional auth source

    Returns:
        Server specs from serverStatus and buildInfo
    """
    # TODO: Implement full server discovery
    # For now, this is handled by test_connection in connections.py
    return {"todo": "Full server discovery to be implemented"}
