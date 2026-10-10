"""Fail-closed Windows composition for frozen Survey definition operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
from typing import Protocol

from fastapi import APIRouter

from plm_assistant.modules.audit.infrastructure.survey_validation_source import (
    SqlAlchemySurveyValidationAuditSource,
)
from plm_assistant.modules.audit.infrastructure.conclusion_validation_source import (
    SqlAlchemyConclusionValidationAuditSource,
)
from plm_assistant.modules.ai.infrastructure.survey_conclusion_task import (
    SqlAlchemySurveyConclusionAITaskProof,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.auth.infrastructure.review_user_access import (
    SqlAlchemyReviewUserAccess,
)
from plm_assistant.modules.capability.infrastructure.survey_source_proof import (
    SqlAlchemyCapabilitySurveySourceProof,
)
from plm_assistant.modules.capability.infrastructure.survey_source_location import (
    SqlAlchemyCapabilitySurveySourceLocation,
)
from plm_assistant.modules.document.infrastructure.survey_source_location import (
    SqlAlchemyDocumentSurveySourceLocation,
)
from plm_assistant.modules.document.infrastructure.survey_template_proof import (
    SqlAlchemySurveyTemplateProof,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    DocumentFixedSourceProofService,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.infrastructure.survey_source_proof import (
    SqlAlchemyHandoverSurveySourceProof,
)
from plm_assistant.modules.handover.infrastructure.survey_source_location import (
    SqlAlchemyHandoverSurveySourceLocation,
)
from plm_assistant.modules.handover.infrastructure.survey_conclusion_issue import (
    SqlAlchemySurveyConclusionIssueProof,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.platform.infrastructure.windows_secret_key_provider import (
    WindowsSecretKeyProvider,
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
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.application.subject_registry import (
    ProjectReviewSubjectRegistry,
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
from plm_assistant.modules.survey.api.commands import create_survey_command_router
from plm_assistant.modules.survey.api.assignments import (
    create_survey_assignment_command_router,
    create_survey_assignment_read_router,
)
from plm_assistant.modules.survey.api.conclusions import (
    create_survey_conclusion_command_router,
    create_survey_conclusion_read_router,
)
from plm_assistant.modules.survey.api.read import create_survey_read_router
from plm_assistant.modules.survey.api.source_location import (
    create_survey_source_location_router,
)
from plm_assistant.modules.survey.api.read_cursor import (
    SurveyAssignmentCursorCodec, SurveyConclusionCursorCodec,
    SurveyCursorCodec, SurveyRoundCursorCodec, SurveyVersionCursorCodec,
)
from plm_assistant.modules.survey.api.rounds import (
    create_survey_round_command_router, create_survey_round_read_router,
)
from plm_assistant.modules.survey.api.submit_review import (
    create_survey_review_submission_router,
)
from plm_assistant.modules.survey.application.change_survey import SurveyStateService
from plm_assistant.modules.survey.application.create_assignment import (
    SurveyAssignmentCreateService,
)
from plm_assistant.modules.survey.application.create_survey import SurveyCreateService
from plm_assistant.modules.survey.application.create_conclusion import (
    SurveyConclusionCreateService,
)
from plm_assistant.modules.survey.application.create_version import SurveyVersionCreateService
from plm_assistant.modules.survey.application.read_surveys import SurveyReadService
from plm_assistant.modules.survey.application.read_assignments import (
    SurveyAssignmentReadService,
)
from plm_assistant.modules.survey.application.read_conclusions import (
    SurveyConclusionReadService,
)
from plm_assistant.modules.survey.application.record_response import (
    SurveyResponseRecordService,
)
from plm_assistant.modules.survey.application.review_assignment import (
    SurveyAssignmentReviewService,
)
from plm_assistant.modules.survey.application.round_source import (
    SurveyRoundProjectRecordProofService,
)
from plm_assistant.modules.survey.application.submit_assignment import (
    SurveyAssignmentSubmitService,
)
from plm_assistant.modules.survey.infrastructure.assignment_repository import (
    SqlAlchemySurveyAssignmentRepository,
)
from plm_assistant.modules.survey.application.create_round import SurveyRoundCreateService
from plm_assistant.modules.survey.application.change_round import SurveyRoundStateService
from plm_assistant.modules.survey.application.read_rounds import SurveyRoundReadService
from plm_assistant.modules.survey.application.round_completeness import (
    SurveyRoundCompletenessOwner,
)
from plm_assistant.modules.survey.application.source_location import (
    SurveySourceLocationService,
)
from plm_assistant.modules.survey.application.review_subject import SurveyReviewSubjectOwner
from plm_assistant.modules.survey.application.conclusion_review_subject import (
    SurveyConclusionReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    SurveyConclusionProjectRecordProofService,
)
from plm_assistant.modules.survey.application.submit_conclusion_review import (
    SurveyConclusionReviewSubmissionService,
)
from plm_assistant.modules.survey.application.submit_review import SurveyReviewSubmissionService
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionCurrentValidator, SurveyVersionValidationService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionCurrentValidator, SurveyConclusionValidationService,
)
from plm_assistant.modules.survey.infrastructure.conclusion_repository import (
    SqlAlchemySurveyConclusionRepository,
)
from plm_assistant.modules.survey.infrastructure.conclusion_response_source import (
    SqlAlchemyConclusionResponseProof,
)
from plm_assistant.modules.survey.infrastructure.conclusion_review_repository import (
    SqlAlchemySurveyConclusionReviewRepository,
)
from plm_assistant.modules.survey.infrastructure.conclusion_validation_repository import (
    SqlAlchemySurveyConclusionValidationRepository,
)
from plm_assistant.modules.survey.infrastructure.read_repository import (
    SqlAlchemySurveyReadRepository,
)
from plm_assistant.modules.survey.infrastructure.round_completeness_repository import (
    SqlAlchemySurveyRoundCompletenessRepository,
)
from plm_assistant.modules.survey.infrastructure.round_repository import (
    SqlAlchemySurveyRoundRepository,
)
from plm_assistant.modules.survey.infrastructure.round_state_repository import (
    SqlAlchemySurveyRoundStateRepository,
)
from plm_assistant.modules.survey.infrastructure.round_source_repository import (
    SqlAlchemySurveyRoundSourceRepository,
)
from plm_assistant.modules.survey.infrastructure.response_repository import (
    SqlAlchemySurveyResponseRepository,
)
from plm_assistant.modules.survey.infrastructure.submission_repository import (
    SqlAlchemySurveyAssignmentSubmissionRepository,
)
from plm_assistant.modules.survey.infrastructure.review_subject_repository import (
    SqlAlchemySurveyReviewSubjectRepository,
)
from plm_assistant.modules.survey.infrastructure.state_repository import (
    SqlAlchemySurveyStateRepository,
)
from plm_assistant.modules.survey.infrastructure.survey_create_repository import (
    SqlAlchemySurveyCreateRepository,
)
from plm_assistant.modules.survey.infrastructure.version_create_repository import (
    SqlAlchemySurveyVersionCreateRepository,
)
from plm_assistant.modules.survey.infrastructure.version_validation_repository import (
    SqlAlchemySurveyVersionValidationRepository,
)


SURVEY_CURSOR_KEY_REF = "survey-cursor-v1"
SURVEY_VERSION_CURSOR_KEY_REF = "survey-version-cursor-v1"


class SurveyKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionSurveyStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Survey production composition unavailable")


@dataclass(frozen=True, slots=True)
class WindowsSurveyRouters:
    reads: APIRouter
    commands: APIRouter | None
    review_submission: APIRouter | None


def create_windows_survey_routers(
    runtime, *, sessions, origins, license_guard, audit,
    include_write: bool, resolver: SurveyKeyResolverPort | None = None,
    documents=None, downloads=None, parse_results=None,
) -> WindowsSurveyRouters:
    if type(include_write) is not bool:
        raise ProductionSurveyStartupError()
    try:
        keys = resolver or WindowsSecretKeyProvider()
        survey_cursor_key = keys.resolve_key(SURVEY_CURSOR_KEY_REF)
        survey_cursors = SurveyCursorCodec(survey_cursor_key)
        round_cursors = SurveyRoundCursorCodec(hmac.digest(
            survey_cursor_key, b"survey-round-cursor-v1", "sha256",
        ))
        assignment_cursors = SurveyAssignmentCursorCodec(hmac.digest(
            survey_cursor_key, b"survey-assignment-cursor-v1", "sha256",
        ))
        conclusion_cursors = SurveyConclusionCursorCodec(hmac.digest(
            survey_cursor_key, b"survey-conclusion-cursor-v1", "sha256",
        ))
        version_cursors = SurveyVersionCursorCodec(
            keys.resolve_key(SURVEY_VERSION_CURSOR_KEY_REF)
        )
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        reads = SurveyReadService(
            unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemySurveyReadRepository(),
        )
        read_router = create_survey_read_router(
            sessions=sessions, origins=origins, reads=reads,
            survey_cursors=survey_cursors, version_cursors=version_cursors,
        )
        locations = SurveySourceLocationService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
            authorization=authorization, sources=SqlAlchemySurveyReadRepository(),
            handover=SqlAlchemyHandoverSurveySourceLocation(),
            capability=SqlAlchemyCapabilitySurveySourceLocation(),
            documents=SqlAlchemyDocumentSurveySourceLocation(),
        )
        read_router.include_router(create_survey_source_location_router(
            sessions=sessions, origins=origins, locations=locations,
        ))
        round_repository = SqlAlchemySurveyRoundRepository()
        round_reads = SurveyRoundReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
            authorization=authorization, repository=round_repository,
        )
        read_router.include_router(create_survey_round_read_router(
            sessions=sessions, origins=origins, reads=round_reads,
            cursors=round_cursors,
        ))
        assignment_repository = SqlAlchemySurveyAssignmentRepository()
        assignment_reads = SurveyAssignmentReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
            authorization=authorization, repository=assignment_repository,
        )
        read_router.include_router(create_survey_assignment_read_router(
            sessions=sessions, origins=origins, reads=assignment_reads,
            cursors=assignment_cursors,
        ))
        conclusion_repository = SqlAlchemySurveyConclusionRepository()
        conclusion_reads = SurveyConclusionReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectReadAccess(), license_guard=license_guard,
            authorization=authorization, repository=conclusion_repository,
        )
        read_router.include_router(create_survey_conclusion_read_router(
            sessions=sessions, origins=origins, reads=conclusion_reads,
            cursors=conclusion_cursors,
        ))
        if not include_write:
            return WindowsSurveyRouters(read_router, None, None)

        access = SqlAlchemyProjectWriteAccess()
        receipts = SqlAlchemyIdempotencyReceipts()
        source_ports = {
            "handover_sources": SqlAlchemyHandoverSurveySourceProof(),
            "capability_sources": SqlAlchemyCapabilitySurveySourceProof(),
            "template_sources": SqlAlchemySurveyTemplateProof(),
            "departments": SqlAlchemySurveyTargetDepartmentProof(),
        }
        surveys = SurveyCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemySurveyCreateRepository(), receipts=receipts,
            audit=audit,
        )
        states = SurveyStateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemySurveyStateRepository(), receipts=receipts,
            audit=audit,
        )
        versions = SurveyVersionCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            **source_ports, repository=SqlAlchemySurveyVersionCreateRepository(),
            receipts=receipts, audit=audit,
        )
        validations = SurveyVersionValidationService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            **source_ports,
            repository=SqlAlchemySurveyVersionValidationRepository(),
            audit_source=SqlAlchemySurveyValidationAuditSource(),
            receipts=receipts, audit=audit,
        )
        command_router = create_survey_command_router(
            sessions=sessions, origins=origins, surveys=surveys, states=states,
            versions=versions, validations=validations,
        )
        dependency_shape = tuple(
            value is not None for value in (documents, downloads, parse_results)
        )
        if any(dependency_shape) and not all(dependency_shape):
            raise ValueError("complete Survey Round evidence dependencies required")
        completeness = None
        if all(dependency_shape):
            document_proofs = DocumentFixedSourceProofService(
                documents=documents, downloads=downloads,
                parse_metadata=SqlAlchemyParseResultReadRepository(),
                parse_results=parse_results,
            )
            completeness = SurveyRoundCompletenessOwner(
                repository=SqlAlchemySurveyRoundCompletenessRepository(),
                submissions=SqlAlchemySurveyAssignmentSubmissionRepository(),
                evidence_owner=EvidenceFixedProjectSourceService(
                    sessions=SqlAlchemyProjectReadAccess(),
                    projects=project_repository,
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    documents=document_proofs,
                    allowed_project_roles=frozenset({"PROJECT_MANAGER"}),
                ),
            )
        round_creates = SurveyRoundCreateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=round_repository, receipts=receipts, audit=audit,
        )
        round_states = SurveyRoundStateService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            repository=SqlAlchemySurveyRoundStateRepository(), receipts=receipts,
            audit=audit, completeness=completeness,
        )
        command_router.include_router(create_survey_round_command_router(
            sessions=sessions, origins=origins, creates=round_creates,
            states=round_states,
        ))
        if all(dependency_shape):
            general_evidence = EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=project_repository,
                evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                documents=document_proofs,
                allowed_project_roles=frozenset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                    "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
                }),
            )
            round_evidence = EvidenceFixedProjectSourceService(
                sessions=SqlAlchemyProjectReadAccess(),
                projects=project_repository,
                evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                documents=document_proofs,
                allowed_project_roles=frozenset({
                    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER",
                }),
                required_document_category="PROJECT_RECORD",
            )
            submission_repository = SqlAlchemySurveyAssignmentSubmissionRepository()
            assignment_creates = SurveyAssignmentCreateService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                repository=assignment_repository, receipts=receipts, audit=audit,
            )
            response_records = SurveyResponseRecordService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemySurveyResponseRepository(), receipts=receipts,
                audit=audit, evidence_owner=general_evidence,
                round_record_proof=SurveyRoundProjectRecordProofService(
                    evidence=round_evidence,
                ),
                round_source_repository=SqlAlchemySurveyRoundSourceRepository(),
            )
            assignment_submissions = SurveyAssignmentSubmitService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                repository=submission_repository, receipts=receipts, audit=audit,
                evidence_owner=general_evidence,
            )
            assignment_reviews = SurveyAssignmentReviewService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                repository=submission_repository, receipts=receipts, audit=audit,
                evidence_owner=general_evidence,
                clock=lambda: datetime.now(timezone.utc),
            )
            command_router.include_router(create_survey_assignment_command_router(
                sessions=sessions, origins=origins, creates=assignment_creates,
                responses=response_records, submissions=assignment_submissions,
                reviews=assignment_reviews,
            ))
            conclusion_create_evidence = SurveyConclusionProjectRecordProofService(
                evidence=round_evidence,
            )
            conclusion_review_evidence = SurveyConclusionProjectRecordProofService(
                evidence=EvidenceFixedProjectSourceService(
                    sessions=SqlAlchemyProjectReadAccess(),
                    projects=project_repository,
                    evidence=SqlAlchemyEvidenceFixedSourceRepository(),
                    documents=document_proofs,
                    allowed_project_roles=ALL_MEMBERS,
                    required_document_category="PROJECT_RECORD",
                ),
                allowed_verified_roles=ALL_MEMBERS,
            )
            conclusion_response_owner = SqlAlchemyConclusionResponseProof()
            conclusion_issue_owner = SqlAlchemySurveyConclusionIssueProof()
            conclusion_ai_owner = SqlAlchemySurveyConclusionAITaskProof()
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        survey_owner = SurveyReviewSubjectOwner(
            repository=SqlAlchemySurveyReviewSubjectRepository(),
            reviewers=reviewers,
            current=SurveyVersionCurrentValidator(**source_ports), audit=audit,
        )
        subjects = survey_owner
        if all(dependency_shape):
            conclusion_owner = SurveyConclusionReviewSubjectOwner(
                repository=SqlAlchemySurveyConclusionReviewRepository(),
                reviewers=reviewers,
                current=SurveyConclusionCurrentValidator(
                    response_owner=conclusion_response_owner,
                    evidence_owner=conclusion_review_evidence,
                    issue_owner=conclusion_issue_owner,
                    ai_owner=conclusion_ai_owner,
                ),
                audit=audit,
            )
            subjects = ProjectReviewSubjectRegistry((survey_owner, conclusion_owner))
        submission = SurveyReviewSubmissionService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=subjects,
            ),
            subjects=subjects,
        )
        if all(dependency_shape):
            conclusion_creates = SurveyConclusionCreateService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                repository=conclusion_repository,
                response_owner=conclusion_response_owner,
                evidence_owner=conclusion_create_evidence,
                issue_owner=conclusion_issue_owner,
                ai_owner=conclusion_ai_owner, receipts=receipts, audit=audit,
            )
            conclusion_validations = SurveyConclusionValidationService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemySurveyConclusionValidationRepository(),
                response_owner=conclusion_response_owner,
                evidence_owner=conclusion_create_evidence,
                issue_owner=conclusion_issue_owner,
                ai_owner=conclusion_ai_owner,
                audit_source=SqlAlchemyConclusionValidationAuditSource(),
                receipts=receipts, audit=audit,
            )
            conclusion_submissions = SurveyConclusionReviewSubmissionService(
                unit_of_work=runtime.unit_of_work, access=access,
                license_guard=license_guard, authorization=authorization,
                reviewers=reviewers, receipts=receipts,
                replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
                reviews=ProjectReviewPersistenceService(
                    creation_repository=SqlAlchemyReviewCreationRepository(),
                    round_repository=SqlAlchemyReviewStartRepository(),
                    audit=audit, subjects=subjects,
                ),
                subjects=subjects,
            )
            command_router.include_router(create_survey_conclusion_command_router(
                sessions=sessions, origins=origins,
                creates=conclusion_creates,
                validations=conclusion_validations,
                submissions=conclusion_submissions,
                reads=conclusion_reads,
            ))
        review_router = create_survey_review_submission_router(
            sessions=sessions, origins=origins, submissions=submission,
        )
        return WindowsSurveyRouters(read_router, command_router, review_router)
    except Exception:
        raise ProductionSurveyStartupError() from None
