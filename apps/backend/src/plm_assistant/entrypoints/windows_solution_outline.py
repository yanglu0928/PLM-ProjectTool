"""Fail-closed explicit Windows composition for SolutionOutline routes."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.outline_create import create_outline_create_router
from plm_assistant.modules.solution.api.section_create import create_section_create_router
from plm_assistant.modules.solution.api.outline_list import create_outline_list_router
from plm_assistant.modules.solution.api.outline_read import create_outline_read_router
from plm_assistant.modules.solution.api.section_read import create_section_read_router
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.application.create_outline import OutlineCreateService
from plm_assistant.modules.solution.application.create_section import SectionCreateService
from plm_assistant.modules.solution.application.read_outline import OutlineReadService
from plm_assistant.modules.solution.application.read_section import SectionReadService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository


class ProductionSolutionOutlineStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("SolutionOutline production composition unavailable")


def create_windows_outline_read_router(
    *, runtime, sessions, origins, license_guard,
) -> APIRouter:
    """Mount GET only with all explicit read-mode trust dependencies present."""
    if any(value is None for value in (runtime, sessions, origins, license_guard)):
        raise ProductionSolutionOutlineStartupError()
    try:
        service = OutlineReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            repository=SqlAlchemyOutlineReadRepository(),
        )
        return create_outline_read_router(
            sessions=sessions, origins=origins, reads=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_section_read_router(
    *, runtime, sessions, origins, license_guard,
) -> APIRouter:
    """Mount Section GET only with explicit read-mode trust dependencies."""
    if any(value is None for value in (runtime, sessions, origins, license_guard)):
        raise ProductionSolutionOutlineStartupError()
    try:
        service = SectionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            repository=SqlAlchemySectionReadRepository(),
        )
        return create_section_read_router(
            sessions=sessions, origins=origins, reads=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_outline_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: OutlineListCursorCodec,
) -> APIRouter:
    """Mount LIST only with the dedicated signed cursor and read trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionOutlineStartupError()
    if type(cursors) is not OutlineListCursorCodec:
        raise ProductionSolutionOutlineStartupError()
    try:
        service = OutlineReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            repository=SqlAlchemyOutlineReadRepository(),
        )
        return create_outline_list_router(
            sessions=sessions, origins=origins, reads=service,
            cursors=cursors)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


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


def create_windows_section_create_router(
    *, runtime, sessions, origins, license_guard, audit,
) -> APIRouter:
    """Mount Section CREATE only with explicit write-mode dependencies."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit)):
        raise ProductionSolutionOutlineStartupError()
    try:
        service = SectionCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            repository=SqlAlchemySectionCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_section_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None
