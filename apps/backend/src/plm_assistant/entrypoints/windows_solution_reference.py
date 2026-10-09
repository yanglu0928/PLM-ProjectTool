"""Fail-closed Windows composition for PROJECT ReferenceSolution creation."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.document.application.prove_fixed_source import DocumentFixedSourceProofService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.reference_version_identity import SqlAlchemyReferenceVersionIdentity
from plm_assistant.modules.evidence.application.fixed_global_reference_source import EvidenceFixedGlobalReferenceService
from plm_assistant.modules.evidence.application.fixed_project_source import EvidenceFixedProjectSourceService
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import SqlAlchemyEvidenceFixedSourceRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.reference_create import (
    create_global_reference_create_router,
    create_project_reference_create_router,
)
from plm_assistant.modules.solution.api.reference_revise import (
    create_global_reference_revise_router,
    create_project_reference_revise_router,
)
from plm_assistant.modules.solution.api.reference_deidentification import create_reference_deidentification_router
from plm_assistant.modules.solution.api.reference_list import create_project_reference_list_router
from plm_assistant.modules.solution.api.global_reference_read import create_global_reference_read_router
from plm_assistant.modules.solution.api.global_reference_list import create_global_reference_list_router
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.api.reference_read import create_project_reference_read_router
from plm_assistant.modules.solution.application.create_reference_solution import ReferenceCreateService
from plm_assistant.modules.solution.application.revise_reference_solution import ReferenceReviseService
from plm_assistant.modules.solution.application.confirm_reference_deidentification import ReferenceDeidentificationConfirmService
from plm_assistant.modules.solution.application.preview_reference_deidentification import ReferenceDeidentificationPreviewService
from plm_assistant.modules.solution.application.lookup_reference_deidentification_operation import ReferenceDeidentificationOperationLookupService
from plm_assistant.modules.solution.application.read_reference import ReferenceReadService
from plm_assistant.modules.solution.application.read_global_reference import GlobalReferenceReadService
from plm_assistant.modules.solution.application.revoke_reference_deidentification import ReferenceDeidentificationRevokeService
from plm_assistant.modules.solution.application.prove_reference_deidentification import ReferenceDeidentificationProofService
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceQualificationService
from plm_assistant.modules.solution.infrastructure.reference_create_repository import SqlAlchemyReferenceCreateRepository
from plm_assistant.modules.solution.infrastructure.reference_revise_repository import SqlAlchemyReferenceReviseRepository
from plm_assistant.modules.solution.infrastructure.reference_read_repository import SqlAlchemyReferenceReadRepository
from plm_assistant.modules.solution.infrastructure.global_reference_read_repository import SqlAlchemyGlobalReferenceReadRepository
from plm_assistant.modules.solution.infrastructure.reference_deidentification_proof_repository import SqlAlchemyReferenceDeidentificationProofRepository
from plm_assistant.modules.solution.infrastructure.reference_deidentification_repository import SqlAlchemyReferenceDeidentificationRepository
from plm_assistant.modules.solution.infrastructure.reference_deidentification_revocation_repository import SqlAlchemyReferenceDeidentificationRevocationRepository
from plm_assistant.modules.solution.infrastructure.reference_deidentification_operation_state import SqlAlchemyReferenceDeidentificationOperationState
from plm_assistant.modules.solution.infrastructure.reference_document_proof import ReferenceDocumentProofAdapter
from plm_assistant.modules.solution.infrastructure.reference_evidence_proof import ReferenceEvidenceProofAdapter


class ProductionSolutionReferenceStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Solution Reference production composition unavailable")


def _read_service(runtime, license_guard) -> ReferenceReadService:
    return ReferenceReadService(
        unit_of_work=runtime.unit_of_work,
        access=SqlAlchemyProjectReadAccess(),
        license_guard=license_guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository()),
        repository=SqlAlchemyReferenceReadRepository(),
    )


def create_windows_project_reference_read_router(
    *, runtime, sessions, origins, license_guard,
) -> APIRouter:
    """Compose the PROJECT GET from current Session/License/project ports."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard)):
        raise ProductionSolutionReferenceStartupError()
    try:
        return create_project_reference_read_router(
            sessions=sessions, origins=origins,
            reads=_read_service(runtime, license_guard))
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def create_windows_global_reference_read_router(
    *, runtime, sessions, origins, license_guard,
) -> APIRouter:
    """Compose an admin-only GLOBAL GET in explicit Windows read mode."""
    if any(value is None for value in (runtime, sessions, origins, license_guard)):
        raise ProductionSolutionReferenceStartupError()
    try:
        service = GlobalReferenceReadService(
            unit_of_work=runtime.unit_of_work,
            admins=SqlAlchemyDeploymentReadAccess(),
            license_guard=license_guard,
            repository=SqlAlchemyGlobalReferenceReadRepository(),
        )
        return create_global_reference_read_router(
            sessions=sessions, origins=origins, reads=service)
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def create_windows_global_reference_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: GlobalReferenceListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionReferenceStartupError()
    try:
        if type(cursors) is not GlobalReferenceListCursorCodec:
            raise ValueError("GLOBAL Reference cursor codec required")
        service = GlobalReferenceReadService(
            unit_of_work=runtime.unit_of_work,
            admins=SqlAlchemyDeploymentReadAccess(),
            license_guard=license_guard,
            repository=SqlAlchemyGlobalReferenceReadRepository(),
        )
        return create_global_reference_list_router(
            sessions=sessions, origins=origins, reads=service, cursors=cursors)
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def create_windows_project_reference_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: ReferenceListCursorCodec,
) -> APIRouter:
    """Compose PROJECT List only after its dedicated cursor key was resolved."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, cursors)):
        raise ProductionSolutionReferenceStartupError()
    try:
        if type(cursors) is not ReferenceListCursorCodec:
            raise ValueError("Reference cursor codec required")
        return create_project_reference_list_router(
            sessions=sessions, origins=origins,
            reads=_read_service(runtime, license_guard), cursors=cursors)
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def create_windows_project_reference_create_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose only an explicit PROJECT write route from real owner ports."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionReferenceStartupError()
    try:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository)
        sources = _source_service(
            documents=documents, downloads=downloads, parse_results=parse_results,
            project_repository=project_repository)
        service = ReferenceCreateService(
            unit_of_work=runtime.unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=authorization,
            license_guard=license_guard, sources=sources,
            repository=SqlAlchemyReferenceCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_project_reference_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def create_windows_global_reference_create_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose GLOBAL create only for the explicit Windows write entrypoint."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionReferenceStartupError()
    try:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        sources = _source_service(
            documents=documents, downloads=downloads, parse_results=parse_results,
            project_repository=project_repository)
        service = ReferenceCreateService(
            unit_of_work=runtime.unit_of_work,
            global_access=SqlAlchemyLicenseImportAccess(),
            project_access=SqlAlchemyProjectWriteAccess(),
            project_authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work, repository=project_repository),
            license_guard=license_guard, sources=sources,
            repository=SqlAlchemyReferenceCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
        )
        return create_global_reference_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def _revise_service(*, runtime, license_guard, audit,
                    documents, downloads, parse_results) -> ReferenceReviseService:
    project_repository = SqlAlchemyProjectAuthorizationRepository()
    sources = _source_service(
        documents=documents, downloads=downloads, parse_results=parse_results,
        project_repository=project_repository)
    return ReferenceReviseService(
        unit_of_work=runtime.unit_of_work,
        global_access=SqlAlchemyLicenseImportAccess(),
        project_access=SqlAlchemyProjectWriteAccess(),
        project_authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository),
        license_guard=license_guard, sources=sources,
        repository=SqlAlchemyReferenceReviseRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
    )


def create_windows_project_reference_revise_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose PROJECT revise only for explicit Windows write mode."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionReferenceStartupError()
    try:
        return create_project_reference_revise_router(
            sessions=sessions, origins=origins,
            revises=_revise_service(
                runtime=runtime, license_guard=license_guard, audit=audit,
                documents=documents, downloads=downloads, parse_results=parse_results))
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def create_windows_global_reference_revise_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose GLOBAL revise only for explicit Windows write mode."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionReferenceStartupError()
    try:
        return create_global_reference_revise_router(
            sessions=sessions, origins=origins,
            revises=_revise_service(
                runtime=runtime, license_guard=license_guard, audit=audit,
                documents=documents, downloads=downloads, parse_results=parse_results))
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None


def _source_service(*, documents, downloads, parse_results,
                    project_repository) -> ReferenceSourceQualificationService:
    admin = SqlAlchemyDeploymentReadAccess()
    fixed = DocumentFixedSourceProofService(
        documents=documents, downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results,
    )
    evidence_rows = SqlAlchemyEvidenceFixedSourceRepository()
    return ReferenceSourceQualificationService(
        documents=ReferenceDocumentProofAdapter(
            identities=SqlAlchemyReferenceVersionIdentity(), fixed_sources=fixed),
        evidence=ReferenceEvidenceProofAdapter(
            project=EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=project_repository, evidence=evidence_rows,
                documents=fixed, allowed_project_roles=frozenset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}),
            ),
            global_reference=EvidenceFixedGlobalReferenceService(
                sessions=SqlAlchemyProjectReadAccess(), admins=admin,
                evidence=evidence_rows, documents=fixed),
        ),
        deidentification=ReferenceDeidentificationProofService(
            admins=admin,
            confirmations=SqlAlchemyReferenceDeidentificationProofRepository(),
        ),
    )


def create_windows_reference_deidentification_router(
    *, runtime, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose GLOBAL attestation only for explicit write-mode admission."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionSolutionReferenceStartupError()
    try:
        sources = _source_service(
            documents=documents, downloads=downloads, parse_results=parse_results,
            project_repository=SqlAlchemyProjectAuthorizationRepository())
        access = SqlAlchemyLicenseImportAccess()
        receipts = SqlAlchemyIdempotencyReceipts()
        previews = ReferenceDeidentificationPreviewService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, sources=sources)
        confirmations = ReferenceDeidentificationConfirmService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, sources=sources,
            repository=SqlAlchemyReferenceDeidentificationRepository(),
            receipts=receipts, audit=audit)
        revocations = ReferenceDeidentificationRevokeService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard,
            repository=SqlAlchemyReferenceDeidentificationRevocationRepository(),
            receipts=receipts, audit=audit)
        lookups = ReferenceDeidentificationOperationLookupService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, receipts=receipts,
            confirmations=SqlAlchemyReferenceDeidentificationOperationState())
        return create_reference_deidentification_router(
            sessions=sessions, origins=origins, previews=previews,
            confirmations=confirmations, revocations=revocations,
            lookups=lookups)
    except Exception:
        raise ProductionSolutionReferenceStartupError() from None
