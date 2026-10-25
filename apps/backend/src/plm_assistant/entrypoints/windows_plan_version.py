"""Explicit Windows composition for the internal PlanVersion DRAFT owner."""

from __future__ import annotations

from pathlib import Path

from plm_assistant.entrypoints.windows_solution_outline import (
    _windows_outline_current_facts,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.plan.api.create_plan_version import (
    create_plan_version_create_router,
)
from plm_assistant.modules.plan.api.read_plan_version import (
    create_plan_version_read_router,
)
from plm_assistant.modules.plan.application.create_plan_version import (
    PlanVersionCreateService,
)
from plm_assistant.modules.plan.application.prove_approved_solution_input import (
    ApprovedSolutionInputProofService,
)
from plm_assistant.modules.plan.application.read_plan_version import (
    PlanVersionReadService,
)
from plm_assistant.modules.plan.infrastructure.plan_version_create_repository import (
    SqlAlchemyPlanVersionCreateRepository,
)
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import (
    SqlAlchemyPlanVersionReadRepository,
)
from plm_assistant.modules.plan.infrastructure.plan_version_source_proofs import (
    SqlAlchemyPlanVersionSourceProofs,
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
from plm_assistant.modules.review.infrastructure.read_repository import (
    SqlAlchemyReviewSnapshotReadRepository,
)
from plm_assistant.modules.solution.application.qualify_section_structured_spec import (
    SectionStructuredSpecQualificationService,
)
from plm_assistant.modules.solution.infrastructure.outline_read_repository import (
    SqlAlchemyOutlineReadRepository,
)
from plm_assistant.modules.solution.infrastructure.outline_version_read_repository import (
    SqlAlchemyOutlineVersionReadRepository,
)
from plm_assistant.modules.solution.infrastructure.section_structured_spec_qualification_repository import (
    SqlAlchemySectionSpecCandidateRepository,
    SqlAlchemySectionSpecSourceRepository,
)
from plm_assistant.modules.solution.infrastructure.section_version_read_repository import (
    SqlAlchemySectionVersionReadRepository,
)


class WindowsPlanVersionStartupError(RuntimeError):
    """The explicit PlanVersion source-proof composition is unavailable."""


def create_windows_plan_version_create_router(
    *, runtime, sessions, origins, license_guard, audit,
    document_storage_root: Path, parse_result_storage_root: Path,
    documents, downloads, parse_results,
):
    if any(value is None for value in (sessions, origins)):
        raise WindowsPlanVersionStartupError()
    try:
        service = create_windows_plan_version_create_service(
            runtime=runtime, license_guard=license_guard, audit=audit,
            document_storage_root=document_storage_root,
            parse_result_storage_root=parse_result_storage_root,
            documents=documents, downloads=downloads,
            parse_results=parse_results)
        return create_plan_version_create_router(
            sessions=sessions, origins=origins, creates=service)
    except Exception:
        raise WindowsPlanVersionStartupError() from None


def create_windows_plan_version_read_router(
    *, runtime, sessions, origins, license_guard,
):
    if any(value is None for value in (runtime, sessions, origins, license_guard)):
        raise WindowsPlanVersionStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        reads = PlanVersionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyPlanVersionReadRepository())
        return create_plan_version_read_router(
            sessions=sessions, origins=origins, reads=reads)
    except Exception:
        raise WindowsPlanVersionStartupError() from None


def create_windows_plan_version_create_service(
    *, runtime, license_guard, audit,
    document_storage_root: Path, parse_result_storage_root: Path,
    documents, downloads, parse_results,
) -> PlanVersionCreateService:
    """Build the real transaction/source graph; deliberately mount no HTTP route."""
    if any(value is None for value in (
            runtime, license_guard, audit, document_storage_root,
            parse_result_storage_root, documents, downloads, parse_results)):
        raise WindowsPlanVersionStartupError()
    try:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository)
        current = _windows_outline_current_facts(
            runtime=runtime, license_guard=license_guard,
            authorization=authorization,
            document_storage_root=document_storage_root,
            parse_result_storage_root=parse_result_storage_root,
            documents=documents, downloads=downloads, parse_results=parse_results)
        reviews = SqlAlchemyReviewSnapshotReadRepository()
        sections = SqlAlchemySectionVersionReadRepository()
        specs = SectionStructuredSpecQualificationService(
            specs=SqlAlchemySectionSpecCandidateRepository(),
            sections=SqlAlchemySectionSpecSourceRepository(),
            reviews=reviews)
        proof = ApprovedSolutionInputProofService(
            outlines=SqlAlchemyOutlineReadRepository(),
            versions=SqlAlchemyOutlineVersionReadRepository(),
            reviews=reviews, current_facts=current,
            coverage=current._coverage, sections=sections,
            spec_qualification=specs)
        return PlanVersionCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard, authorization=authorization,
            solution_proof=proof,
            source_proofs=SqlAlchemyPlanVersionSourceProofs(reviews=reviews),
            repository=SqlAlchemyPlanVersionCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    except Exception:
        raise WindowsPlanVersionStartupError() from None
