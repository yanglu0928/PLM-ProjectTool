"""Fail-closed Windows composition for frozen Survey definition operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

from plm_assistant.modules.audit.infrastructure.survey_validation_source import (
    SqlAlchemySurveyValidationAuditSource,
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
from plm_assistant.modules.document.infrastructure.survey_template_proof import (
    SqlAlchemySurveyTemplateProof,
)
from plm_assistant.modules.handover.infrastructure.survey_source_proof import (
    SqlAlchemyHandoverSurveySourceProof,
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
from plm_assistant.modules.project.infrastructure.survey_source_proof import (
    SqlAlchemySurveyTargetDepartmentProof,
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
from plm_assistant.modules.survey.api.commands import create_survey_command_router
from plm_assistant.modules.survey.api.read import create_survey_read_router
from plm_assistant.modules.survey.api.read_cursor import (
    SurveyCursorCodec, SurveyVersionCursorCodec,
)
from plm_assistant.modules.survey.api.submit_review import (
    create_survey_review_submission_router,
)
from plm_assistant.modules.survey.application.change_survey import SurveyStateService
from plm_assistant.modules.survey.application.create_survey import SurveyCreateService
from plm_assistant.modules.survey.application.create_version import SurveyVersionCreateService
from plm_assistant.modules.survey.application.read_surveys import SurveyReadService
from plm_assistant.modules.survey.application.review_subject import SurveyReviewSubjectOwner
from plm_assistant.modules.survey.application.submit_review import SurveyReviewSubmissionService
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionCurrentValidator, SurveyVersionValidationService,
)
from plm_assistant.modules.survey.infrastructure.read_repository import (
    SqlAlchemySurveyReadRepository,
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
) -> WindowsSurveyRouters:
    if type(include_write) is not bool:
        raise ProductionSurveyStartupError()
    try:
        keys = resolver or WindowsSecretKeyProvider()
        survey_cursors = SurveyCursorCodec(keys.resolve_key(SURVEY_CURSOR_KEY_REF))
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
        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        owner = SurveyReviewSubjectOwner(
            repository=SqlAlchemySurveyReviewSubjectRepository(),
            reviewers=reviewers,
            current=SurveyVersionCurrentValidator(**source_ports), audit=audit,
        )
        submission = SurveyReviewSubmissionService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=owner,
            ),
            subjects=owner,
        )
        review_router = create_survey_review_submission_router(
            sessions=sessions, origins=origins, submissions=submission,
        )
        return WindowsSurveyRouters(read_router, command_router, review_router)
    except Exception:
        raise ProductionSurveyStartupError() from None
