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
from plm_assistant.modules.plan.api.list_plan_version_wbs import (
    create_plan_version_wbs_list_router,
)
from plm_assistant.modules.plan.api.validate_plan_version import (
    create_plan_version_validate_router,
)
from plm_assistant.modules.plan.api.submit_plan_version_review import (
    create_plan_version_review_submission_router,
)
from plm_assistant.modules.plan.api.wbs_list_cursor import (
    PlanVersionWbsCursorCodec,
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
from plm_assistant.modules.plan.application.list_plan_version_wbs import (
    PlanVersionWbsReadService,
)
from plm_assistant.modules.plan.application.validate_plan_version import (
    PlanVersionValidationService,
)
from plm_assistant.modules.plan.infrastructure.plan_version_create_repository import (
    SqlAlchemyPlanVersionCreateRepository,
)
from plm_assistant.modules.plan.infrastructure.plan_version_read_repository import (
    SqlAlchemyPlanVersionReadRepository,
)
from plm_assistant.modules.plan.infrastructure.plan_version_wbs_read_repository import (
    SqlAlchemyPlanVersionWbsReadRepository,
)
from plm_assistant.modules.plan.infrastructure.plan_version_validation_results import (
    SqlAlchemyPlanVersionValidationRepository,
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


def create_windows_plan_version_wbs_list_router(
    *, runtime, sessions, origins, license_guard,
    cursors: PlanVersionWbsCursorCodec,
):
    if any(value is None for value in (runtime, sessions, origins,
                                       license_guard, cursors)):
        raise WindowsPlanVersionStartupError()
    if type(cursors) is not PlanVersionWbsCursorCodec:
        raise WindowsPlanVersionStartupError()
    try:
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        reads = PlanVersionWbsReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemyPlanVersionWbsReadRepository())
        return create_plan_version_wbs_list_router(
            sessions=sessions, origins=origins, reads=reads, cursors=cursors)
    except Exception:
        raise WindowsPlanVersionStartupError() from None


def create_windows_plan_version_validation_router(
    *, runtime, sessions, origins, license_guard, audit,
    document_storage_root: Path, parse_result_storage_root: Path,
    documents, downloads, parse_results,
):
    return create_windows_plan_version_validation_composition(
        runtime=runtime, sessions=sessions, origins=origins,
        license_guard=license_guard, audit=audit,
        document_storage_root=document_storage_root,
        parse_result_storage_root=parse_result_storage_root,
        documents=documents, downloads=downloads,
        parse_results=parse_results,
    )[0]


def create_windows_plan_version_validation_composition(
    *, runtime, sessions, origins, license_guard, audit,
    document_storage_root: Path, parse_result_storage_root: Path,
    documents, downloads, parse_results,
):
    """Return the explicit Windows validation route and its exact evaluator."""
    if any(value is None for value in (sessions, origins)):
        raise WindowsPlanVersionStartupError()
    try:
        service = create_windows_plan_version_validation_service(
            runtime=runtime, license_guard=license_guard, audit=audit,
            document_storage_root=document_storage_root,
            parse_result_storage_root=parse_result_storage_root,
            documents=documents, downloads=downloads,
            parse_results=parse_results)
        router = create_plan_version_validate_router(
            sessions=sessions, origins=origins, validations=service)
        return router, service
    except Exception:
        raise WindowsPlanVersionStartupError() from None


def create_windows_plan_version_review_submission_router(
    *, runtime, sessions, origins, license_guard, audit,
    validation_service,
):
    """Compose the frozen atomic PlanVersion SubmitReview operation."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            validation_service)) or not callable(getattr(
                validation_service, "evaluate_snapshot_in_transaction", None)):
        raise WindowsPlanVersionStartupError()
    try:
        from plm_assistant.modules.auth.infrastructure.project_write_access import (
            SqlAlchemyProjectWriteAccess,
        )
        from plm_assistant.modules.auth.infrastructure.review_user_access import (
            SqlAlchemyReviewUserAccess,
        )
        from plm_assistant.modules.plan.application.plan_review_readiness import (
            PlanVersionReviewReadinessService,
        )
        from plm_assistant.modules.plan.application.plan_version_review_terminal import (
            PlanVersionReviewSubjectOwner,
        )
        from plm_assistant.modules.plan.application.submit_plan_version_review import (
            PlanVersionReviewSubmissionService,
        )
        from plm_assistant.modules.plan.infrastructure.plan_review_readiness_repository import (
            SqlAlchemyPlanVersionReviewReadinessRepository,
        )
        from plm_assistant.modules.plan.infrastructure.plan_review_subject_repository import (
            SqlAlchemyPlanReviewSubjectRepository,
        )
        from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
            SqlAlchemyIdempotencyReceipts,
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

        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository)
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository)
        owner = PlanVersionReviewSubjectOwner(
            repository=SqlAlchemyPlanReviewSubjectRepository(),
            reviewers=reviewers,
            readiness=PlanVersionReviewReadinessService(
                repository=SqlAlchemyPlanVersionReviewReadinessRepository(),
                evaluator=validation_service),
            audit=audit)
        receipts = SqlAlchemyIdempotencyReceipts()
        reviews = ProjectReviewPersistenceService(
            creation_repository=SqlAlchemyReviewCreationRepository(),
            round_repository=SqlAlchemyReviewStartRepository(), audit=audit,
            subjects=owner)
        submissions = PlanVersionReviewSubmissionService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard, authorization=authorization,
            reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=reviews, subjects=owner,
            scope_repository=SqlAlchemyPlanReviewSubjectRepository())
        return create_plan_version_review_submission_router(
            sessions=sessions, origins=origins, submissions=submissions)
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


def create_windows_plan_version_validation_service(
    *, runtime, license_guard, audit,
    document_storage_root: Path, parse_result_storage_root: Path,
    documents, downloads, parse_results,
) -> PlanVersionValidationService:
    """Build the authorized internal validation graph; mount no HTTP route."""
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
        results = SqlAlchemyPlanVersionValidationRepository()
        return PlanVersionValidationService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectWriteAccess(),
            license_guard=license_guard, authorization=authorization,
            snapshots=results, results=results, solution_proof=proof,
            source_proofs=SqlAlchemyPlanVersionSourceProofs(reviews=reviews),
            receipts=SqlAlchemyIdempotencyReceipts(), audit=audit)
    except Exception:
        raise WindowsPlanVersionStartupError() from None
