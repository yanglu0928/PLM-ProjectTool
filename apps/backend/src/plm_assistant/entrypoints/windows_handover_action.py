"""Fail-closed Windows composition for Handover Action write operations."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.review_start_access import (
    SqlAlchemyReviewStartAccess,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.api.action_commands import (
    create_handover_action_command_router,
    create_handover_action_lifecycle_router,
)
from plm_assistant.modules.handover.application.cancel_action import (
    HandoverActionCancelService,
)
from plm_assistant.modules.handover.application.close_action import (
    HandoverActionCloseService,
)
from plm_assistant.modules.handover.application.create_action import (
    HandoverActionCreateService,
)
from plm_assistant.modules.handover.application.patch_action import (
    HandoverActionPatchService,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverSourceValidator,
)
from plm_assistant.modules.handover.application.start_action import (
    HandoverActionStartService,
)
from plm_assistant.modules.handover.application.submit_action import (
    HandoverActionSubmitService,
)
from plm_assistant.modules.handover.application.verify_action import (
    HandoverActionVerifyService,
)
from plm_assistant.modules.handover.infrastructure.action_cancel_repository import (
    SqlAlchemyHandoverActionCancelRepository,
)
from plm_assistant.modules.handover.infrastructure.action_close_repository import (
    SqlAlchemyHandoverActionCloseRepository,
)
from plm_assistant.modules.handover.infrastructure.action_create_repository import (
    SqlAlchemyHandoverActionCreateRepository,
)
from plm_assistant.modules.handover.infrastructure.action_patch_repository import (
    SqlAlchemyHandoverActionPatchRepository,
)
from plm_assistant.modules.handover.infrastructure.action_start_repository import (
    SqlAlchemyHandoverActionStartRepository,
)
from plm_assistant.modules.handover.infrastructure.action_submit_repository import (
    SqlAlchemyHandoverActionSubmitRepository,
)
from plm_assistant.modules.handover.infrastructure.action_verify_repository import (
    SqlAlchemyHandoverActionVerifyRepository,
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
from plm_assistant.modules.project.infrastructure.handover_action_assignee import (
    SqlAlchemyHandoverActionAssigneeSource,
)
from plm_assistant.modules.trace.application.resolution_proof import (
    TraceResolutionProofService,
)
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.resolution_repository import (
    SqlAlchemyTraceResolutionRepository,
)


class ProductionHandoverActionWriteStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Handover Action write composition unavailable")


@dataclass(frozen=True, slots=True)
class WindowsHandoverActionWriteRouters:
    commands: APIRouter
    lifecycle: APIRouter


def create_windows_handover_action_write_routers(
    runtime, *, sessions, origins, license_guard, audit,
    target_proofs: TraceTargetProofService | None = None,
) -> WindowsHandoverActionWriteRouters:
    """Compose seven Action writes; absent downstream owners keep CLOSE denied."""

    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit)):
        raise ProductionHandoverActionWriteStartupError()
    try:
        access = SqlAlchemyReviewStartAccess()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        assignees = SqlAlchemyHandoverActionAssigneeSource()
        receipts = SqlAlchemyIdempotencyReceipts()
        sources = HandoverSourceValidator(SqlAlchemyDocumentReadRepository())
        evidence = SqlAlchemyEvidenceFixedSourceRepository()
        creates = HandoverActionCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            assignees=assignees,
            repository=SqlAlchemyHandoverActionCreateRepository(),
            receipts=receipts, audit=audit,
        )
        patches = HandoverActionPatchService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            assignees=assignees,
            repository=SqlAlchemyHandoverActionPatchRepository(), audit=audit,
        )
        starts = HandoverActionStartService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyHandoverActionStartRepository(),
            receipts=receipts, audit=audit,
        )
        submits = HandoverActionSubmitService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            sources=sources, evidence=evidence,
            repository=SqlAlchemyHandoverActionSubmitRepository(),
            receipts=receipts, audit=audit,
        )
        verifies = HandoverActionVerifyService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            sources=sources, evidence=evidence,
            repository=SqlAlchemyHandoverActionVerifyRepository(),
            receipts=receipts, audit=audit,
        )
        proofs = target_proofs or TraceTargetProofService({})
        closes = HandoverActionCloseService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            trace_proofs=TraceResolutionProofService(
                SqlAlchemyTraceResolutionRepository(), proofs,
            ),
            repository=SqlAlchemyHandoverActionCloseRepository(),
            receipts=receipts, audit=audit,
        )
        cancels = HandoverActionCancelService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyHandoverActionCancelRepository(),
            receipts=receipts, audit=audit,
        )
        return WindowsHandoverActionWriteRouters(
            create_handover_action_command_router(
                sessions=sessions, origins=origins, creates=creates, patches=patches,
            ),
            create_handover_action_lifecycle_router(
                sessions=sessions, origins=origins, starts=starts, submits=submits,
                verifies=verifies, closes=closes, cancels=cancels,
            ),
        )
    except Exception:
        raise ProductionHandoverActionWriteStartupError() from None
