"""Fail-closed Windows composition for frozen Handover Analysis operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

from plm_assistant.modules.ai.infrastructure.task_read_repository import (
    SqlAlchemyAITaskReadRepository,
)
from plm_assistant.modules.audit.infrastructure.handover_validation_source import (
    SqlAlchemyHandoverValidationAuditSource,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.review_start_access import (
    SqlAlchemyReviewStartAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.capability.infrastructure.read_repository import (
    SqlAlchemyCapabilityReadRepository,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.api.commands import create_handover_command_router
from plm_assistant.modules.handover.api.read import create_handover_read_router
from plm_assistant.modules.handover.api.read_cursor import (
    HandoverAnalysisCursorCodec, HandoverItemCursorCodec,
    HandoverVersionCursorCodec,
)
from plm_assistant.modules.handover.api.submit_review import (
    create_handover_review_submission_router,
)
from plm_assistant.modules.handover.application.change_analysis import (
    HandoverAnalysisStateService,
)
from plm_assistant.modules.handover.application.create_analysis import (
    HandoverAnalysisCreateService,
)
from plm_assistant.modules.handover.application.create_version import (
    HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisReadService,
)
from plm_assistant.modules.handover.application.review_subject import (
    HandoverReviewSubjectOwner,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverSourceValidator,
)
from plm_assistant.modules.handover.application.submit_review import (
    HandoverReviewSubmissionService,
)
from plm_assistant.modules.handover.application.validate_version import (
    HandoverVersionValidationService,
)
from plm_assistant.modules.handover.infrastructure.analysis_create_repository import (
    SqlAlchemyHandoverAnalysisCreateRepository,
)
from plm_assistant.modules.handover.infrastructure.analysis_read_repository import (
    SqlAlchemyHandoverAnalysisReadRepository,
)
from plm_assistant.modules.handover.infrastructure.analysis_state_repository import (
    SqlAlchemyHandoverAnalysisStateRepository,
)
from plm_assistant.modules.handover.infrastructure.review_subject_repository import (
    SqlAlchemyHandoverReviewSubjectRepository,
)
from plm_assistant.modules.handover.infrastructure.version_create_repository import (
    SqlAlchemyHandoverVersionCreateRepository,
)
from plm_assistant.modules.handover.infrastructure.version_validation_repository import (
    SqlAlchemyHandoverVersionValidationRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.project_submission_repository import (
    SqlAlchemyProjectReviewSubmissionRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)


HANDOVER_ANALYSIS_CURSOR_KEY_REF = "handover-analysis-cursor-v1"
HANDOVER_VERSION_CURSOR_KEY_REF = "handover-version-cursor-v1"
HANDOVER_ITEM_CURSOR_KEY_REF = "handover-item-cursor-v1"


class HandoverKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionHandoverStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Handover production composition unavailable")


@dataclass(frozen=True, slots=True)
class WindowsHandoverRouters:
    reads: APIRouter
    commands: APIRouter | None
    review_submission: APIRouter | None


def create_windows_handover_routers(
    runtime, *, sessions, origins, license_guard, audit,
    include_write: bool, resolver: HandoverKeyResolverPort | None = None,
) -> WindowsHandoverRouters:
    if type(include_write) is not bool:
        raise ProductionHandoverStartupError()
    try:
        keys = resolver or WindowsSecretKeyProvider()
        analysis_cursors = HandoverAnalysisCursorCodec(
            keys.resolve_key(HANDOVER_ANALYSIS_CURSOR_KEY_REF),
        )
        version_cursors = HandoverVersionCursorCodec(
            keys.resolve_key(HANDOVER_VERSION_CURSOR_KEY_REF),
        )
        item_cursors = HandoverItemCursorCodec(
            keys.resolve_key(HANDOVER_ITEM_CURSOR_KEY_REF),
        )
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        reads = HandoverAnalysisReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyHandoverAnalysisReadRepository(),
        )
        read_router = create_handover_read_router(
            sessions=sessions, origins=origins, reads=reads,
            analysis_cursors=analysis_cursors, version_cursors=version_cursors,
            item_cursors=item_cursors,
        )
        if not include_write:
            return WindowsHandoverRouters(read_router, None, None)

        access = SqlAlchemyReviewStartAccess()
        receipts = SqlAlchemyIdempotencyReceipts()
        sources = HandoverSourceValidator(SqlAlchemyDocumentReadRepository())
        evidence = SqlAlchemyEvidenceFixedSourceRepository()
        capabilities = SqlAlchemyCapabilityReadRepository()
        ai_tasks = SqlAlchemyAITaskReadRepository()
        analyses = HandoverAnalysisCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            sources=sources,
            repository=SqlAlchemyHandoverAnalysisCreateRepository(),
            receipts=receipts, audit=audit,
        )
        states = HandoverAnalysisStateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyHandoverAnalysisStateRepository(),
            receipts=receipts, audit=audit,
        )
        versions = HandoverVersionCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            sources=sources, evidence=evidence, capabilities=capabilities,
            ai_tasks=ai_tasks,
            repository=SqlAlchemyHandoverVersionCreateRepository(),
            receipts=receipts, audit=audit,
        )
        validations = HandoverVersionValidationService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            sources=sources, evidence=evidence, capabilities=capabilities,
            ai_tasks=ai_tasks,
            repository=SqlAlchemyHandoverVersionValidationRepository(),
            audit_source=SqlAlchemyHandoverValidationAuditSource(),
            receipts=receipts, audit=audit,
        )
        command_router = create_handover_command_router(
            sessions=sessions, origins=origins, analyses=analyses, states=states,
            versions=versions, validations=validations,
        )
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        owner = HandoverReviewSubjectOwner(
            repository=SqlAlchemyHandoverReviewSubjectRepository(),
            reviewers=reviewers, sources=sources, evidence=evidence,
            capabilities=capabilities, ai_tasks=ai_tasks, audit=audit,
        )
        review_repository = SqlAlchemyReviewStartRepository()
        submission = HandoverReviewSubmissionService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=review_repository, audit=audit, subjects=owner,
            ),
            subjects=owner,
        )
        review_router = create_handover_review_submission_router(
            sessions=sessions, origins=origins, submissions=submission,
        )
        return WindowsHandoverRouters(read_router, command_router, review_router)
    except Exception:
        raise ProductionHandoverStartupError() from None
