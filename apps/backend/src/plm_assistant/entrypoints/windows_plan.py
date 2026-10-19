"""Explicit Windows composition for current Plan identity routes."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.plan.api.create_plan import create_plan_create_router
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
from plm_assistant.modules.plan.api.list_plan import create_plan_list_router
from plm_assistant.modules.plan.api.read_plan import create_plan_read_router
from plm_assistant.modules.plan.application.create_plan import PlanCreateService
from plm_assistant.modules.plan.application.read_plan import PlanReadService
from plm_assistant.modules.plan.infrastructure.create_repository import SqlAlchemyPlanCreateRepository
from plm_assistant.modules.plan.infrastructure.read_repository import SqlAlchemyPlanReadRepository
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository


class ProductionPlanStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Plan production composition unavailable")


def _authorization(runtime) -> ProjectAuthorizationService:
    return ProjectAuthorizationService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemyProjectAuthorizationRepository())


def create_windows_plan_read_routers(
    *, runtime, sessions, origins, license_guard,
    cursors: PlanListCursorCodec,
) -> tuple[APIRouter, APIRouter]:
    if (any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors))
            or type(cursors) is not PlanListCursorCodec):
        raise ProductionPlanStartupError()
    try:
        reads = PlanReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard, authorization=_authorization(runtime),
            repository=SqlAlchemyPlanReadRepository())
        return (
            create_plan_read_router(sessions=sessions, origins=origins, reads=reads),
            create_plan_list_router(sessions=sessions, origins=origins,
                                    reads=reads, cursors=cursors),
        )
    except Exception:
        raise ProductionPlanStartupError() from None


def create_windows_plan_create_router(
    *, runtime, sessions, origins, license_guard, audit,
) -> APIRouter:
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit)):
        raise ProductionPlanStartupError()
    try:
        creates = PlanCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard, authorization=_authorization(runtime),
            repository=SqlAlchemyPlanCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
        return create_plan_create_router(
            sessions=sessions, origins=origins, creates=creates)
    except Exception:
        raise ProductionPlanStartupError() from None
