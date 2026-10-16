"""Fail-closed Windows composition for all frozen Capability operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

from plm_assistant.modules.audit.infrastructure.capability_validation_source import (
    SqlAlchemyCapabilityValidationAuditSource,
)
from plm_assistant.modules.auth.infrastructure.current_user_access import (
    SqlAlchemyCurrentUserAccess,
)
from plm_assistant.modules.auth.infrastructure.license_import_access import (
    SqlAlchemyLicenseImportAccess,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.capability.api.commands import create_capability_command_router
from plm_assistant.modules.capability.api.read import create_capability_read_router
from plm_assistant.modules.capability.api.read_cursor import (
    CapabilityBaselineCursorCodec, CapabilityChildCursorCodec,
)
from plm_assistant.modules.capability.api.submit_review import (
    create_capability_review_submission_router,
)
from plm_assistant.modules.capability.application.change_state import CapabilityStateService
from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateService,
)
from plm_assistant.modules.capability.application.create_version import (
    CapabilityVersionCreateService,
)
from plm_assistant.modules.capability.application.read_capability import CapabilityReadService
from plm_assistant.modules.capability.application.review_subject import (
    CapabilityReviewSubjectOwner,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilitySourceValidator,
)
from plm_assistant.modules.capability.application.submit_review import (
    CapabilityReviewSubmissionService,
)
from plm_assistant.modules.capability.application.validate_version import (
    CapabilityVersionValidationService,
)
from plm_assistant.modules.capability.infrastructure.baseline_create_repository import (
    SqlAlchemyCapabilityBaselineCreateRepository,
)
from plm_assistant.modules.capability.infrastructure.read_repository import (
    SqlAlchemyCapabilityReadRepository,
)
from plm_assistant.modules.capability.infrastructure.review_subject_repository import (
    SqlAlchemyCapabilityReviewSubjectRepository,
)
from plm_assistant.modules.capability.infrastructure.state_repository import (
    SqlAlchemyCapabilityStateRepository,
)
from plm_assistant.modules.capability.infrastructure.version_create_repository import (
    SqlAlchemyCapabilityVersionCreateRepository,
)
from plm_assistant.modules.capability.infrastructure.version_validation_repository import (
    SqlAlchemyCapabilityVersionValidationRepository,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
)
from plm_assistant.modules.project.infrastructure.capability_read_access import (
    SqlAlchemyCapabilityReadMembership,
)
from plm_assistant.modules.review.application.global_persistence import (
    GlobalReviewPersistenceService,
)
from plm_assistant.modules.review.infrastructure.global_repository import (
    SqlAlchemyGlobalReviewRepository,
)


CAPABILITY_BASELINE_CURSOR_KEY_REF = "capability-baseline-cursor-v1"
CAPABILITY_CHILD_CURSOR_KEY_REF = "capability-child-cursor-v1"


class CapabilityKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionCapabilityStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Capability production composition unavailable")


@dataclass(frozen=True, slots=True)
class WindowsCapabilityRouters:
    reads: APIRouter
    commands: APIRouter | None
    review_submission: APIRouter | None


def create_windows_capability_routers(
    runtime, *, sessions, origins, license_guard, audit,
    include_write: bool, resolver: CapabilityKeyResolverPort | None = None,
) -> WindowsCapabilityRouters:
    if type(include_write) is not bool:
        raise ProductionCapabilityStartupError()
    try:
        keys = resolver or WindowsSecretKeyProvider()
        baseline_cursors = CapabilityBaselineCursorCodec(
            keys.resolve_key(CAPABILITY_BASELINE_CURSOR_KEY_REF),
        )
        child_cursors = CapabilityChildCursorCodec(
            keys.resolve_key(CAPABILITY_CHILD_CURSOR_KEY_REF),
        )
        source_validator = CapabilitySourceValidator(SqlAlchemyDocumentReadRepository())
        evidence = SqlAlchemyEvidenceFixedSourceRepository()
        reads = CapabilityReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            current_user=SqlAlchemyCurrentUserAccess(),
            membership=SqlAlchemyCapabilityReadMembership(),
            license_guard=license_guard,
            repository=SqlAlchemyCapabilityReadRepository(),
        )
        read_router = create_capability_read_router(
            sessions=sessions, origins=origins, reads=reads,
            baseline_cursors=baseline_cursors, child_cursors=child_cursors,
        )
        if not include_write:
            return WindowsCapabilityRouters(read_router, None, None)

        access = SqlAlchemyLicenseImportAccess()
        receipts = SqlAlchemyIdempotencyReceipts()
        baselines = CapabilityBaselineCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, sources=source_validator,
            repository=SqlAlchemyCapabilityBaselineCreateRepository(),
            receipts=receipts, audit=audit,
        )
        versions = CapabilityVersionCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, sources=source_validator, evidence=evidence,
            repository=SqlAlchemyCapabilityVersionCreateRepository(),
            receipts=receipts, audit=audit,
        )
        validations = CapabilityVersionValidationService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, sources=source_validator, evidence=evidence,
            repository=SqlAlchemyCapabilityVersionValidationRepository(),
            audit_source=SqlAlchemyCapabilityValidationAuditSource(),
            receipts=receipts, audit=audit,
        )
        states = CapabilityStateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard,
            repository=SqlAlchemyCapabilityStateRepository(),
            receipts=receipts, audit=audit,
        )
        command_router = create_capability_command_router(
            sessions=sessions, origins=origins, baselines=baselines,
            versions=versions, validations=validations, states=states,
        )
        subject = CapabilityReviewSubjectOwner(
            users=SqlAlchemyCurrentUserAccess(),
            repository=SqlAlchemyCapabilityReviewSubjectRepository(),
            sources=source_validator, evidence=evidence, audit=audit,
        )
        review_repository = SqlAlchemyGlobalReviewRepository()
        review_kernel = GlobalReviewPersistenceService(
            repository=review_repository, audit=audit, subjects=subject,
        )
        submission = CapabilityReviewSubmissionService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, receipts=receipts,
            replay_repository=review_repository, reviews=review_kernel,
            subjects=subject,
        )
        review_router = create_capability_review_submission_router(
            sessions=sessions, origins=origins, submissions=submission,
        )
        return WindowsCapabilityRouters(read_router, command_router, review_router)
    except Exception:
        raise ProductionCapabilityStartupError() from None
