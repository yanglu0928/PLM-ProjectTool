"""Fail-closed Windows composition for PROJECT Review Subject Owners."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.ai.infrastructure.task_read_repository import (
    SqlAlchemyAITaskReadRepository,
)
from plm_assistant.modules.ai.infrastructure.survey_conclusion_task import (
    SqlAlchemySurveyConclusionAITaskProof,
)
from plm_assistant.modules.auth.infrastructure.review_start_access import (
    SqlAlchemyReviewStartAccess,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.capability.infrastructure.read_repository import (
    SqlAlchemyCapabilityReadRepository,
)
from plm_assistant.modules.capability.infrastructure.survey_source_proof import (
    SqlAlchemyCapabilitySurveySourceProof,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    DocumentFixedSourceProofService,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.survey_template_proof import (
    SqlAlchemySurveyTemplateProof,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.handover.application.review_subject import (
    HandoverReviewSubjectOwner,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverSourceValidator,
)
from plm_assistant.modules.handover.infrastructure.review_subject_repository import (
    SqlAlchemyHandoverReviewSubjectRepository,
)
from plm_assistant.modules.handover.infrastructure.survey_source_proof import (
    SqlAlchemyHandoverSurveySourceProof,
)
from plm_assistant.modules.handover.infrastructure.survey_conclusion_issue import (
    SqlAlchemySurveyConclusionIssueProof,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerQualificationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.project.infrastructure.survey_source_proof import (
    SqlAlchemySurveyTargetDepartmentProof,
)
from plm_assistant.modules.review.api.commands import create_review_command_router
from plm_assistant.modules.review.application.create_review import ReviewCreateService
from plm_assistant.modules.review.application.start_round import ReviewStartService
from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectRegistry,
)
from plm_assistant.modules.review.application.transition_command import (
    ReviewTransitionCommandService,
)
from plm_assistant.modules.review.infrastructure.create_repository import (
    SqlAlchemyReviewCreationRepository,
)
from plm_assistant.modules.review.infrastructure.start_repository import (
    SqlAlchemyReviewStartRepository,
)
from plm_assistant.modules.review.infrastructure.transition_repository import (
    SqlAlchemyReviewTransitionRepository,
)
from plm_assistant.modules.survey.application.review_subject import (
    SurveyReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.conclusion_review_subject import (
    SurveyConclusionReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    SurveyConclusionProjectRecordProofService,
)
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionCurrentValidator,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionCurrentValidator,
)
from plm_assistant.modules.survey.infrastructure.conclusion_response_source import (
    SqlAlchemyConclusionResponseProof,
)
from plm_assistant.modules.survey.infrastructure.conclusion_review_repository import (
    SqlAlchemySurveyConclusionReviewRepository,
)
from plm_assistant.modules.survey.infrastructure.review_subject_repository import (
    SqlAlchemySurveyReviewSubjectRepository,
)


class ProductionProjectReviewStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PROJECT Review composition unavailable")


def create_windows_project_review_router(
    runtime, *, sessions, origins, license_guard, audit,
    documents=None, downloads=None, parse_results=None,
) -> APIRouter:
    """Compose one frozen Router with all approved PROJECT Subject Owners."""
    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit)):
        raise ProductionProjectReviewStartupError()
    try:
        dependency_shape = tuple(
            value is not None for value in (documents, downloads, parse_results)
        )
        if any(dependency_shape) and not all(dependency_shape):
            raise ValueError("complete SurveyConclusion evidence dependencies required")
        access = SqlAlchemyReviewStartAccess()
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        handover = HandoverReviewSubjectOwner(
            repository=SqlAlchemyHandoverReviewSubjectRepository(),
            reviewers=reviewers,
            sources=HandoverSourceValidator(SqlAlchemyDocumentReadRepository()),
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            capabilities=SqlAlchemyCapabilityReadRepository(),
            ai_tasks=SqlAlchemyAITaskReadRepository(), audit=audit,
        )
        survey = SurveyReviewSubjectOwner(
            repository=SqlAlchemySurveyReviewSubjectRepository(),
            reviewers=reviewers,
            current=SurveyVersionCurrentValidator(
                handover_sources=SqlAlchemyHandoverSurveySourceProof(),
                capability_sources=SqlAlchemyCapabilitySurveySourceProof(),
                template_sources=SqlAlchemySurveyTemplateProof(),
                departments=SqlAlchemySurveyTargetDepartmentProof(),
            ),
            audit=audit,
        )
        subject_owners = [handover, survey]
        if all(dependency_shape):
            document_proofs = DocumentFixedSourceProofService(
                documents=documents, downloads=downloads,
                parse_metadata=SqlAlchemyParseResultReadRepository(),
                parse_results=parse_results,
            )
            conclusion = SurveyConclusionReviewSubjectOwner(
                repository=SqlAlchemySurveyConclusionReviewRepository(),
                reviewers=reviewers,
                current=SurveyConclusionCurrentValidator(
                    response_owner=SqlAlchemyConclusionResponseProof(),
                    evidence_owner=SurveyConclusionProjectRecordProofService(
                        evidence=EvidenceFixedProjectSourceService(
                            sessions=SqlAlchemyProjectReadAccess(),
                            projects=project_repository,
                            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                            documents=document_proofs,
                            allowed_project_roles=ALL_MEMBERS,
                            required_document_category="PROJECT_RECORD",
                        ),
                        allowed_verified_roles=ALL_MEMBERS,
                    ),
                    issue_owner=SqlAlchemySurveyConclusionIssueProof(),
                    ai_owner=SqlAlchemySurveyConclusionAITaskProof(),
                ),
                audit=audit,
            )
            subject_owners.append(conclusion)
        subjects = ProjectReviewSubjectRegistry(tuple(subject_owners))
        receipts = SqlAlchemyIdempotencyReceipts()
        creates = ReviewCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, license_guard=license_guard,
            repository=SqlAlchemyReviewCreationRepository(), receipts=receipts,
            audit=audit, subjects=subjects,
        )
        starts = ReviewStartService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, reviewers=reviewers,
            license_guard=license_guard,
            repository=SqlAlchemyReviewStartRepository(), receipts=receipts,
            audit=audit, subjects=subjects,
        )
        transitions = ReviewTransitionCommandService(
            unit_of_work=runtime.unit_of_work, access=access,
            projects=authorization, license_guard=license_guard,
            repository=SqlAlchemyReviewTransitionRepository(), receipts=receipts,
            audit=audit, subjects=subjects,
        )
        return create_review_command_router(
            sessions=sessions, origins=origins, creates=creates,
            starts=starts, transitions=transitions,
        )
    except Exception:
        raise ProductionProjectReviewStartupError() from None
