"""Fail-closed explicit Windows composition for SolutionOutline routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.entrypoints.trace_structured_spec_owner import StructuredSpecTraceOwner
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
from plm_assistant.modules.document.application.prove_reference_use_document import ReferenceUseDocumentProofService
from plm_assistant.modules.document.application.prove_reference_use_parse import ReferenceUseParseProofService
from plm_assistant.modules.document.application.prove_fixed_source import DocumentFixedSourceProofService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.document.infrastructure.reference_version_identity import SqlAlchemyReferenceVersionIdentity
from plm_assistant.modules.document.infrastructure.reference_use_source import SqlAlchemyReferenceUseDocumentSource
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import ReferenceUseEvidenceProofService
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.review.application.project_persistence import ProjectReviewPersistenceService
from plm_assistant.modules.review.infrastructure.create_repository import SqlAlchemyReviewCreationRepository
from plm_assistant.modules.review.infrastructure.project_submission_repository import SqlAlchemyProjectReviewSubmissionRepository
from plm_assistant.modules.review.infrastructure.start_repository import SqlAlchemyReviewStartRepository
from plm_assistant.modules.solution.api.outline_create import create_outline_create_router
from plm_assistant.modules.solution.api.outline_version_create import create_outline_version_create_router
from plm_assistant.modules.solution.api.outline_version_read import create_outline_version_read_router
from plm_assistant.modules.solution.api.outline_version_list_cursor import OutlineVersionListCursorCodec
from plm_assistant.modules.solution.api.section_create import create_section_create_router
from plm_assistant.modules.solution.api.section_version_create import create_section_version_create_router
from plm_assistant.modules.solution.api.structured_spec_create import create_structured_spec_create_router
from plm_assistant.modules.solution.api.structured_spec_revise import create_structured_spec_revise_router
from plm_assistant.modules.solution.api.structured_spec_list import create_structured_spec_list_router
from plm_assistant.modules.solution.api.structured_spec_list_cursor import StructuredSpecListCursorCodec
from plm_assistant.modules.solution.api.structured_spec_read import create_structured_spec_read_router
from plm_assistant.modules.solution.api.structured_spec_validate import create_structured_spec_validate_router
from plm_assistant.modules.solution.api.structured_spec_submit_review import create_structured_spec_review_submission_router
from plm_assistant.modules.solution.api.section_version_read import create_section_version_read_router
from plm_assistant.modules.solution.api.section_version_validate import create_section_version_validate_router
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec
from plm_assistant.modules.solution.api.outline_list import create_outline_list_router
from plm_assistant.modules.solution.api.outline_read import create_outline_read_router
from plm_assistant.modules.solution.api.section_read import create_section_read_router
from plm_assistant.modules.solution.api.section_list import create_section_list_router
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.api.outline_list_cursor import OutlineListCursorCodec
from plm_assistant.modules.solution.application.create_outline import OutlineCreateService
from plm_assistant.modules.solution.application.create_outline_version import OutlineVersionCreateService
from plm_assistant.modules.solution.application.read_outline_version import OutlineVersionReadService
from plm_assistant.modules.solution.application.create_section import SectionCreateService
from plm_assistant.modules.solution.application.create_section_version import SectionVersionCreateService
from plm_assistant.modules.solution.application.create_structured_spec import StructuredSpecCreateService
from plm_assistant.modules.solution.application.revise_structured_spec import StructuredSpecReviseService
from plm_assistant.modules.solution.application.read_structured_spec import StructuredSpecReadService
from plm_assistant.modules.solution.application.evaluate_structured_spec_validation import StructuredSpecCurrentFactEvaluator
from plm_assistant.modules.solution.application.validate_structured_spec import StructuredSpecValidationService
from plm_assistant.modules.solution.application.structured_spec_review_readiness import StructuredSpecReviewReadinessService
from plm_assistant.modules.solution.application.structured_spec_review_subject import StructuredSpecReviewSubjectOwner
from plm_assistant.modules.solution.application.structured_spec_submit_review import StructuredSpecReviewSubmissionService
from plm_assistant.modules.solution.application.prove_structured_spec_sources import StructuredSpecSourceProofService
from plm_assistant.modules.solution.application.read_section_version import SectionVersionReadService
from plm_assistant.modules.solution.application.validate_section_version import (
    SectionVersionCurrentValidator, SectionVersionValidationService,
)
from plm_assistant.modules.solution.application.prove_section_version_input import SectionVersionInputProofService
from plm_assistant.modules.solution.application.prove_outline_section_use import OutlineSectionUseProofService
from plm_assistant.modules.solution.application.prove_outline_version_input import OutlineVersionInputProofService
from plm_assistant.modules.solution.application.prove_reference_use import ReferenceUseProofService
from plm_assistant.modules.requirement.application.outline_version_proof import OutlineRequirementUseProofService
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadService
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import SqlAlchemyPrototypeApprovedRequirementVersionProof
from plm_assistant.modules.requirement.infrastructure.version_read_repository import SqlAlchemyRequirementVersionReadRepository
from plm_assistant.modules.solution.application.read_outline import OutlineReadService
from plm_assistant.modules.solution.application.read_section import SectionReadService
from plm_assistant.modules.solution.infrastructure.outline_create_repository import SqlAlchemyOutlineCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_version_base import SqlAlchemyCurrentOutlineVersionBase
from plm_assistant.modules.solution.infrastructure.outline_version_create_repository import SqlAlchemyOutlineVersionCreateRepository
from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import SqlAlchemyOutlineVersionReadRepository
from plm_assistant.modules.solution.infrastructure.section_create_repository import SqlAlchemySectionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import SectionDocumentContentProofAdapter
from plm_assistant.modules.solution.infrastructure.section_evidence_use_proof import SectionEvidenceUseProofAdapter
from plm_assistant.modules.solution.infrastructure.section_version_base import SqlAlchemyCurrentSectionVersionBase
from plm_assistant.modules.solution.infrastructure.section_version_create_repository import SqlAlchemySectionVersionCreateRepository
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import SqlAlchemySectionVersionReadRepository
from plm_assistant.modules.solution.infrastructure.structured_spec_create_repository import SqlAlchemyStructuredSpecCreateRepository
from plm_assistant.modules.solution.infrastructure.structured_spec_read_repository import SqlAlchemyStructuredSpecReadRepository
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_audit_source import (
    SqlAlchemyStructuredSpecValidationAuditSource,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_validation_repository import (
    SqlAlchemyStructuredSpecValidationRepository,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_review_repository import SqlAlchemyStructuredSpecReviewSubjectRepository
from plm_assistant.modules.solution.infrastructure.section_version_validation_audit_source import (
    SqlAlchemySectionVersionValidationAuditSource,
)
from plm_assistant.modules.solution.infrastructure.outline_read_repository import SqlAlchemyOutlineReadRepository
from plm_assistant.modules.solution.infrastructure.section_read_repository import SqlAlchemySectionReadRepository
from plm_assistant.modules.solution.infrastructure.reference_use_repository import (
    SqlAlchemyCurrentGlobalConfirmationRepository, SqlAlchemyCurrentReferenceUseRepository,
)
from plm_assistant.modules.solution.infrastructure.reference_use_source import CurrentReferenceSourceAdapter
from plm_assistant.modules.trace.application.implements_coverage import TraceImplementsCoverageService
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.implements_repository import SqlAlchemyTraceImplementsRepository


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


def create_windows_outline_version_read_router(
    *, runtime, sessions, origins, license_guard,
    cursors: OutlineVersionListCursorCodec,
) -> APIRouter:
    """Mount historical GET/LIST only with dedicated cursor and read trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionOutlineStartupError()
    if type(cursors) is not OutlineVersionListCursorCodec:
        raise ProductionSolutionOutlineStartupError()
    try:
        service = OutlineVersionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            outlines=SqlAlchemyOutlineReadRepository(),
            versions=SqlAlchemyOutlineVersionReadRepository(),
        )
        return create_outline_version_read_router(
            sessions=sessions, origins=origins, reads=service,
            cursors=cursors)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_section_version_read_router(
    *, runtime, sessions, origins, license_guard,
    cursors: SectionVersionListCursorCodec,
) -> APIRouter:
    """Mount historical SectionVersion GET/LIST only with read trust and its key."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionOutlineStartupError()
    if type(cursors) is not SectionVersionListCursorCodec:
        raise ProductionSolutionOutlineStartupError()
    try:
        service = SectionVersionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(),
        )
        return create_section_version_read_router(
            sessions=sessions, origins=origins, reads=service,
            cursors=cursors)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_read_router(
    *, runtime, sessions, origins, license_guard,
) -> APIRouter:
    """Mount SOL_SPEC_GET only with explicit read-mode trust dependencies."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard)):
        raise ProductionSolutionOutlineStartupError()
    try:
        service = StructuredSpecReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            specs=SqlAlchemyStructuredSpecReadRepository(),
        )
        return create_structured_spec_read_router(
            sessions=sessions, origins=origins, reads=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: StructuredSpecListCursorCodec,
) -> APIRouter:
    """Mount SOL_SPEC_LIST only with dedicated cursor and read trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionOutlineStartupError()
    if type(cursors) is not StructuredSpecListCursorCodec:
        raise ProductionSolutionOutlineStartupError()
    try:
        service = StructuredSpecReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            specs=SqlAlchemyStructuredSpecReadRepository(),
        )
        return create_structured_spec_list_router(
            sessions=sessions, origins=origins, reads=service,
            cursors=cursors)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_section_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: SectionListCursorCodec,
) -> APIRouter:
    """Mount Section LIST only with dedicated signed cursor and read trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionOutlineStartupError()
    if type(cursors) is not SectionListCursorCodec:
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
        return create_section_list_router(
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


def create_windows_outline_version_create_router(
    *, runtime, sessions, origins, license_guard, audit,
    document_storage_root: Path, parse_result_storage_root: Path,
) -> APIRouter:
    """Mount Version CREATE only with explicit write trust and verified storage."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            document_storage_root, parse_result_storage_root)):
        raise ProductionSolutionOutlineStartupError()
    try:
        documents = ReferenceUseDocumentProofService(
            sources=SqlAlchemyReferenceUseDocumentSource(),
            storage=LocalFileStorage(document_storage_root))
        parses = ReferenceUseParseProofService(
            documents=documents,
            metadata=SqlAlchemyParseResultReadRepository(),
            storage=LocalParseResultStorage(parse_result_storage_root))
        evidence = ReferenceUseEvidenceProofService(
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=documents, parses=parses)
        references = ReferenceUseProofService(
            references=SqlAlchemyCurrentReferenceUseRepository(),
            sources=CurrentReferenceSourceAdapter(
                documents=documents, evidence=evidence),
            confirmations=SqlAlchemyCurrentGlobalConfirmationRepository())
        inputs = OutlineVersionInputProofService(
            bases=SqlAlchemyCurrentOutlineVersionBase(),
            sections=OutlineSectionUseProofService(
                sections=SqlAlchemySectionReadRepository()),
            requirements=OutlineRequirementUseProofService(
                approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
            references=references)
        service = OutlineVersionCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            inputs=inputs,
            repository=SqlAlchemyOutlineVersionCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
        return create_outline_version_create_router(
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


def create_windows_section_version_create_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Mount SectionVersion CREATE only with explicit write/source trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        fixed = DocumentFixedSourceProofService(
            documents=documents, downloads=downloads,
            parse_metadata=SqlAlchemyParseResultReadRepository(),
            parse_results=parse_results)
        evidence = EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=SqlAlchemyProjectAuthorizationRepository(),
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=fixed,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
        )
        inputs = SectionVersionInputProofService(
            bases=SqlAlchemyCurrentSectionVersionBase(),
            documents=SectionDocumentContentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(),
                fixed_sources=fixed),
            requirements=OutlineRequirementUseProofService(
                approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
            evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
        )
        service = SectionVersionCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            inputs=inputs, repository=SqlAlchemySectionVersionCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_section_version_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_create_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Mount SOL-06 CREATE only with explicit write and current-source trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        fixed = DocumentFixedSourceProofService(
            documents=documents, downloads=downloads,
            parse_metadata=SqlAlchemyParseResultReadRepository(),
            parse_results=parse_results)
        evidence = EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=SqlAlchemyProjectAuthorizationRepository(),
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=fixed,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
        )
        sources = StructuredSpecSourceProofService(
            requirements=OutlineRequirementUseProofService(
                approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(),
            evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
            documents=SectionDocumentContentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(),
                fixed_sources=fixed),
        )
        service = StructuredSpecCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            sources=sources, repository=SqlAlchemyStructuredSpecCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_structured_spec_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_revise_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Mount SOL-06 REVISE only with explicit write and current-source trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        fixed = DocumentFixedSourceProofService(
            documents=documents, downloads=downloads,
            parse_metadata=SqlAlchemyParseResultReadRepository(),
            parse_results=parse_results)
        evidence = EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=SqlAlchemyProjectAuthorizationRepository(),
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=fixed,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
        )
        sources = StructuredSpecSourceProofService(
            requirements=OutlineRequirementUseProofService(
                approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(),
            evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
            documents=SectionDocumentContentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(),
                fixed_sources=fixed),
        )
        service = StructuredSpecReviseService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository()),
            sources=sources, repository=SqlAlchemyStructuredSpecCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_structured_spec_revise_router(
            sessions=sessions, origins=origins, revises=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_validate_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Mount SOL-06 VALIDATE only in explicit write/current-source mode."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        read_access = SqlAlchemyProjectReadAccess()
        fixed = DocumentFixedSourceProofService(
            documents=documents, downloads=downloads,
            parse_metadata=SqlAlchemyParseResultReadRepository(),
            parse_results=parse_results)
        evidence = EvidenceFixedProjectSourceService(
            sessions=read_access,
            projects=SqlAlchemyProjectAuthorizationRepository(),
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=fixed,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
        )
        requirement_trace_owner = RequirementVersionTraceOwner(
            RequirementVersionReadService(
                unit_of_work=runtime.unit_of_work, access=read_access,
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemyRequirementVersionReadRepository()))
        spec_trace_owner = StructuredSpecTraceOwner(StructuredSpecReadService(
            unit_of_work=runtime.unit_of_work, access=read_access,
            license_guard=license_guard, authorization=authorization,
            specs=SqlAlchemyStructuredSpecReadRepository()))
        trace = TraceImplementsCoverageService(
            repository=SqlAlchemyTraceImplementsRepository(),
            owners=TraceTargetProofService({
                ("requirement", "REQ-03"): requirement_trace_owner,
                ("solution", "SOL-06"): spec_trace_owner,
            }))
        evaluator = StructuredSpecCurrentFactEvaluator(
            requirements=OutlineRequirementUseProofService(
                approved_versions=(
                    SqlAlchemyPrototypeApprovedRequirementVersionProof())),
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(),
            evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
            documents=SectionDocumentContentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(),
                fixed_sources=fixed),
            trace=trace,
        )
        service = StructuredSpecValidationService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyStructuredSpecValidationRepository(),
            evaluator=evaluator, receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit,
            audit_source=SqlAlchemyStructuredSpecValidationAuditSource(),
        )
        return create_structured_spec_validate_router(
            sessions=sessions, origins=origins, validations=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_review_submission_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Mount SOL-06 submit-review only in explicit write/source mode."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        authorization_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=authorization_repository)
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(),
            projects=authorization_repository)
        subject_repository = SqlAlchemyStructuredSpecReviewSubjectRepository()
        owner = create_windows_structured_spec_review_subject(
            runtime=runtime, license_guard=license_guard, audit=audit,
            documents=documents, downloads=downloads,
            parse_results=parse_results,
            authorization_repository=authorization_repository,
            authorization=authorization, reviewers=reviewers,
            repository=subject_repository)
        service = StructuredSpecReviewSubmissionService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard, authorization=authorization,
            reviewers=reviewers, receipts=SqlAlchemyIdempotencyReceipts(),
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            identity=subject_repository,
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=owner),
            subjects=owner)
        return create_structured_spec_review_submission_router(
            sessions=sessions, origins=origins, submissions=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_structured_spec_review_subject(
    *, runtime, license_guard, audit, documents, downloads, parse_results,
    authorization_repository=None, authorization=None, reviewers=None,
    repository=None,
) -> StructuredSpecReviewSubjectOwner:
    """Compose the one production SOL-06 Owner shared by submit and terminal Review."""
    if any(value is None for value in (
            runtime, license_guard, audit, documents, downloads,
            parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        project_repository = (
            authorization_repository
            or SqlAlchemyProjectAuthorizationRepository())
        project_authorization = authorization or ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=project_repository)
        reviewer_service = reviewers or ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository)
        subject_repository = (
            repository or SqlAlchemyStructuredSpecReviewSubjectRepository())
        read_access = SqlAlchemyProjectReadAccess()
        fixed = DocumentFixedSourceProofService(
            documents=documents, downloads=downloads,
            parse_metadata=SqlAlchemyParseResultReadRepository(),
            parse_results=parse_results)
        evidence = EvidenceFixedProjectSourceService(
            sessions=read_access, projects=project_repository,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=fixed,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
        )
        requirement_trace_owner = RequirementVersionTraceOwner(
            RequirementVersionReadService(
                unit_of_work=runtime.unit_of_work, access=read_access,
                license_guard=license_guard,
                authorization=project_authorization,
                repository=SqlAlchemyRequirementVersionReadRepository()))
        spec_trace_owner = StructuredSpecTraceOwner(StructuredSpecReadService(
            unit_of_work=runtime.unit_of_work, access=read_access,
            license_guard=license_guard,
            authorization=project_authorization,
            specs=SqlAlchemyStructuredSpecReadRepository()))
        trace = TraceImplementsCoverageService(
            repository=SqlAlchemyTraceImplementsRepository(),
            owners=TraceTargetProofService({
                ("requirement", "REQ-03"): requirement_trace_owner,
                ("solution", "SOL-06"): spec_trace_owner,
            }))
        evaluator = StructuredSpecCurrentFactEvaluator(
            requirements=OutlineRequirementUseProofService(
                approved_versions=(
                    SqlAlchemyPrototypeApprovedRequirementVersionProof())),
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(),
            evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
            documents=SectionDocumentContentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(),
                fixed_sources=fixed),
            trace=trace,
        )
        return StructuredSpecReviewSubjectOwner(
            repository=subject_repository, reviewers=reviewer_service,
            readiness=StructuredSpecReviewReadinessService(
                repository=SqlAlchemyStructuredSpecValidationRepository(),
                evaluator=evaluator),
            audit=audit)
    except ProductionSolutionOutlineStartupError:
        raise
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None


def create_windows_section_version_validate_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Mount VALIDATE only with explicit write and current-source trust."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionOutlineStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        read_access = SqlAlchemyProjectReadAccess()
        requirement_trace_owner = RequirementVersionTraceOwner(
            RequirementVersionReadService(
                unit_of_work=runtime.unit_of_work, access=read_access,
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemyRequirementVersionReadRepository()))
        section_trace_owner = SectionVersionTraceOwner(
            SectionVersionReadService(
                unit_of_work=runtime.unit_of_work, access=read_access,
                license_guard=license_guard, authorization=authorization,
                sections=SqlAlchemySectionReadRepository(),
                versions=SqlAlchemySectionVersionReadRepository()))
        trace = TraceImplementsCoverageService(
            repository=SqlAlchemyTraceImplementsRepository(),
            owners=TraceTargetProofService({
                ("requirement", "REQ-03"): requirement_trace_owner,
                ("solution", "SOL-05"): section_trace_owner,
            }))
        fixed = DocumentFixedSourceProofService(
            documents=documents, downloads=downloads,
            parse_metadata=SqlAlchemyParseResultReadRepository(),
            parse_results=parse_results)
        evidence = EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=SqlAlchemyProjectAuthorizationRepository(),
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=fixed,
            allowed_project_roles=frozenset({
                "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
        )
        current = SectionVersionCurrentValidator(
            documents=SectionDocumentContentProofAdapter(
                identities=SqlAlchemyReferenceVersionIdentity(),
                fixed_sources=fixed),
            requirements=OutlineRequirementUseProofService(
                approved_versions=SqlAlchemyPrototypeApprovedRequirementVersionProof()),
            evidence=SectionEvidenceUseProofAdapter(fixed_sources=evidence),
            trace=trace,
        )
        service = SectionVersionValidationService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(), license_guard=license_guard,
            authorization=authorization,
            sections=SqlAlchemySectionReadRepository(),
            versions=SqlAlchemySectionVersionReadRepository(), current=current,
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
            audit_source=SqlAlchemySectionVersionValidationAuditSource(),
        )
        return create_section_version_validate_router(
            sessions=sessions, origins=origins, validations=service)
    except Exception:
        raise ProductionSolutionOutlineStartupError() from None
