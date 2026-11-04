"""Explicit Windows write composition for OutputRequest cancellation."""
from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.jobs.application.output_cancel import OutputJobCancellation
from plm_assistant.modules.jobs.infrastructure.output_cancel_repository import (
    SqlAlchemyOutputJobCancellationRepository,
)
from plm_assistant.modules.output.api.cancel_request import (
    create_output_request_cancel_router,
)
from plm_assistant.modules.output.application.cancel_request import (
    OutputRequestCancelService,
)
from plm_assistant.modules.output.infrastructure.cancel_access import (
    SqlAlchemyOutputRequestCancelAccess,
)
from plm_assistant.modules.output.infrastructure.cancel_request_repository import (
    SqlAlchemyOutputRequestCancelRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class ProductionOutputCancelStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Output cancellation composition unavailable")


def create_windows_output_cancel_router(
    *, runtime, sessions, origins, license_guard, audit,
) -> APIRouter:
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit)):
        raise ProductionOutputCancelStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        service = OutputRequestCancelService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyOutputRequestCancelAccess(
                authorization=authorization,
            ),
            license_guard=license_guard,
            repository=SqlAlchemyOutputRequestCancelRepository(),
            jobs=OutputJobCancellation(
                SqlAlchemyOutputJobCancellationRepository(),
            ),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit,
        )
        return create_output_request_cancel_router(
            sessions=sessions, origins=origins, service=service,
        )
    except Exception:
        raise ProductionOutputCancelStartupError() from None
