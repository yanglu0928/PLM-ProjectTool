from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from plm_assistant.modules.platform.application.health import HealthService


class HealthView(BaseModel):
    """Minimal public health response with no deployment metadata."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["UP", "NOT_READY"]


def create_health_router(health_service: HealthService) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get(
        "/health/live",
        operation_id="HEALTH_LIVE",
        response_model=HealthView,
    )
    async def liveness() -> JSONResponse:
        return _response(status_code=200, status="UP")

    @router.get(
        "/health/ready",
        operation_id="HEALTH_READY",
        response_model=HealthView,
        responses={503: {"model": HealthView}},
    )
    async def readiness() -> JSONResponse:
        if await health_service.is_ready():
            return _response(status_code=200, status="UP")
        return _response(status_code=503, status="NOT_READY")

    return router


def _response(
    *, status_code: int, status: Literal["UP", "NOT_READY"]
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"status": status},
        headers={"Cache-Control": "no-store"},
    )
