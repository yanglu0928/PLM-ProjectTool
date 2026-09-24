from __future__ import annotations

from collections.abc import Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from plm_assistant import __version__
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers
from plm_assistant.modules.platform.api.health import create_health_router
from plm_assistant.modules.platform.application.health import (
    HealthService,
    ReadinessCheck,
)


APP_TITLE = "PLM Project Implementation Assistant API"


def create_app(
    *, readiness_checks: Iterable[ReadinessCheck] | None = None
) -> FastAPI:
    """Create one isolated API application instance.

    Uvicorn must load this callable with ``--factory``. Runtime integrations add
    readiness probes through the composition root instead of changing the
    public health response or importing infrastructure from the health router.
    """

    health_service = HealthService(tuple(readiness_checks or ()))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        health_service.mark_started()
        try:
            yield
        finally:
            health_service.mark_stopped()

    app = FastAPI(
        title=APP_TITLE,
        version=__version__,
        debug=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.health_service = health_service
    install_error_handlers(app)
    app.include_router(create_health_router(health_service))
    return app
