"""Explicit Windows read composition for OutputRequest list pages."""
from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.output.api.list_cursor import OutputRequestListCursorCodec
from plm_assistant.modules.output.api.list_requests import (
    create_output_request_list_router,
)
from plm_assistant.modules.output.application.list_requests import (
    OutputRequestListService,
)
from plm_assistant.modules.output.infrastructure.list_requests_repository import (
    SqlAlchemyOutputRequestListRepository,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class ProductionOutputListStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Output list composition unavailable")


def create_windows_output_request_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: OutputRequestListCursorCodec,
    session_access: object | None = None,
) -> APIRouter:
    if (any(value is None for value in
            (runtime, sessions, origins, license_guard, cursors))
            or type(cursors) is not OutputRequestListCursorCodec):
        raise ProductionOutputListStartupError()
    try:
        service = OutputRequestListService(
            unit_of_work=runtime.unit_of_work,
            access=session_access or SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ),
            repository=SqlAlchemyOutputRequestListRepository(),
        )
        return create_output_request_list_router(
            sessions=sessions, origins=origins,
            service=service, cursors=cursors,
        )
    except Exception:
        raise ProductionOutputListStartupError() from None
