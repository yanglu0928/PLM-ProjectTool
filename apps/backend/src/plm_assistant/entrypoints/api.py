from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRouter

from plm_assistant import __version__
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers
from plm_assistant.modules.platform.api.health import create_health_router
from plm_assistant.modules.platform.api.trace_middleware import TraceMiddleware
from plm_assistant.modules.platform.application.health import (
    HealthService,
    ReadinessCheck,
)
from plm_assistant.modules.platform.infrastructure.structured_logging import (
    StructuredLoggers,
)


APP_TITLE = "PLM Project Implementation Assistant API"


def create_app(
    *,
    readiness_checks: Iterable[ReadinessCheck] | None = None,
    loggers: StructuredLoggers | None = None,
    login_router: APIRouter | None = None,
    session_router: APIRouter | None = None,
    session_renew_router: APIRouter | None = None,
    session_logout_router: APIRouter | None = None,
    secret_metadata_router: APIRouter | None = None,
    shutdown_callback: Callable[[], None] | None = None,
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
            if shutdown_callback is not None:
                shutdown_callback()

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
    app.state.loggers = loggers or StructuredLoggers()
    app.add_middleware(TraceMiddleware, loggers=app.state.loggers)
    install_error_handlers(app)
    app.include_router(create_health_router(health_service))
    if login_router is not None:
        app.include_router(login_router)
    if session_router is not None:
        app.include_router(session_router)
    if session_renew_router is not None:
        app.include_router(session_renew_router)
    if session_logout_router is not None:
        app.include_router(session_logout_router)
    if secret_metadata_router is not None:
        app.include_router(secret_metadata_router)
    return app
