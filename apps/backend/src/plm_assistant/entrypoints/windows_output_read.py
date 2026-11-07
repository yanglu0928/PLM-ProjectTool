"""Explicit Windows read composition for OutputRequest and available artifacts."""
from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.output.api.read_artifact import create_output_artifact_read_router
from plm_assistant.modules.output.api.read_request import (
    create_output_request_read_router,
)
from plm_assistant.modules.output.application.read_artifact import OutputArtifactReadService
from plm_assistant.modules.output.application.read_request import (
    OutputRequestReadService,
)
from plm_assistant.modules.output.infrastructure.read_artifact_repository import (
    SqlAlchemyOutputArtifactReadRepository,
)
from plm_assistant.modules.output.infrastructure.read_request_repository import (
    SqlAlchemyOutputRequestReadRepository,
)
from plm_assistant.modules.project.infrastructure.read_repository import (
    SqlAlchemyProjectReadRepository,
)


class ProductionOutputReadStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Output read composition unavailable")


def create_windows_output_request_read_router(
    *, runtime, sessions, origins, license_guard,
    session_access: object | None = None,
) -> APIRouter:
    if any(value is None for value in
           (runtime, sessions, origins, license_guard)):
        raise ProductionOutputReadStartupError()
    try:
        access = session_access or SqlAlchemyProjectReadAccess()
        projects = SqlAlchemyProjectReadRepository()
        detail = OutputRequestReadService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=projects, license_guard=license_guard,
            repository=SqlAlchemyOutputRequestReadRepository(),
        )
        artifact = OutputArtifactReadService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=projects, license_guard=license_guard,
            repository=SqlAlchemyOutputArtifactReadRepository(),
        )
        router = APIRouter()
        router.include_router(create_output_request_read_router(
            sessions=sessions, origins=origins, service=detail,
        ))
        router.include_router(create_output_artifact_read_router(
            sessions=sessions, origins=origins, service=artifact,
        ))
        return router
    except Exception:
        raise ProductionOutputReadStartupError() from None
