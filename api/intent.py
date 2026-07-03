"""Intent API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.intent_engine import IntentEngine
from core.workload_optimizer import WorkloadOptimizer
from core.resource_validator import ResourceValidator

router = APIRouter(prefix="/api/intent", tags=["intent"])
engine = IntentEngine()


class CalculateRequest(BaseModel):
    intent_id: str
    intensity: str = "medium"
    duration_seconds: int = 600
    data_size: str | None = None
    concurrency_level: int = 10
    client_hardware: dict | None = None
    server_hardware: dict | None = None
    allow_overrides: bool = False


@router.get("/types")
def list_intent_types():
    """List all available intent types."""
    return {"intents": engine.list_intents()}


@router.post("/calculate")
def calculate_intent(req: CalculateRequest):
    """Calculate configuration from intent."""
    try:
        config = engine.calculate_configuration(
            req.intent_id,
            req.intensity,
            req.duration_seconds,
            req.data_size,
            req.concurrency_level,
            req.client_hardware,
            req.server_hardware,
        )

        # Optimize
        if req.client_hardware and req.server_hardware:
            limits = {
                "max_threads": ResourceValidator.max_threads(
                    req.client_hardware.get("summary", {}).get("cpu_cores", 4)
                ),
                "max_connections": ResourceValidator.max_connections(
                    req.server_hardware.get("max_connections", 1000)
                ),
            }
            config = WorkloadOptimizer.optimize_configuration(
                config, req.client_hardware, req.server_hardware, limits
            )

        # Validate
        if req.client_hardware and req.server_hardware:
            validation = ResourceValidator.validate_configuration(
                config, req.client_hardware, req.server_hardware, req.allow_overrides
            )
            config["validation"] = validation

        return config
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/preview/{intent_id}")
def preview_intent(intent_id: str, intensity: str = "medium"):
    """Preview intent impact."""
    try:
        return engine.preview_impact(intent_id, intensity)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
