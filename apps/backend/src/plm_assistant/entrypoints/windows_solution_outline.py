"""Fail-closed explicit Windows composition for SolutionOutline CREATE."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.outline_create import create_outline_create_router
from plm_assistant.modules.solution.application.create_outline import OutlineCreateService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository


class ProductionSolutionOutlineStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SolutionOutline production composition unavailable")


def create_windows_outline_create_router(
    *, runtime, sessions, origins, license_guard, audit,
) -> APIRouter:
    """Mount only with all explicit write-mode trust dependencies present."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit)):
        raise ProductionSolutionOutlineStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        service = OutlineCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyOutlineCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_outline_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None
