"""Fail-closed Windows composition for frozen Requirement operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

from plm_assistant.modules.audit.infrastructure.requirement_validation_source import (
    SqlAlchemyRequirementValidationAuditSource,
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
from plm_assistant.modules.capability.infrastructure.requirement_source_proof import (
    SqlAlchemyCapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import (
    SqlAlchemyEvidenceRequirementSourceProof,
)
from plm_assistant.modules.handover.infrastructure.requirement_source_proof import (
    SqlAlchemyHandoverRequirementSourceProof,
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
from plm_assistant.modules.requirement.api.package_cursor import (
    RequirementPackageCursorCodec,
)
from plm_assistant.modules.requirement.api.packages import (
    create_requirement_package_router,
)
from plm_assistant.modules.requirement.api.relation_cursor import (
    RequirementRelationCursorCodec,
)
from plm_assistant.modules.requirement.api.relations import (
    create_requirement_relation_router,
)
from plm_assistant.modules.requirement.api.requirement_cursor import (
    RequirementCursorCodec,
)
from plm_assistant.modules.requirement.api.requirements import (
    create_requirement_router,
)
from plm_assistant.modules.requirement.api.submit_review import (
    create_requirement_review_submission_router,
)
from plm_assistant.modules.requirement.api.version_cursor import (
    RequirementVersionCursorCodec,
)
from plm_assistant.modules.requirement.api.versions import (
    create_requirement_version_router,
)
from plm_assistant.modules.requirement.application.create_identity import (
    RequirementIdentityCreateService,
)
from plm_assistant.modules.requirement.application.create_version import (
    RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.application.mutate_package import (
    RequirementPackageMutationService,
)
from plm_assistant.modules.requirement.application.mutate_requirement import (
    RequirementMutationService,
)
from plm_assistant.modules.requirement.application.read_identities import (
    RequirementIdentityReadService,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementVersionReadService,
)
from plm_assistant.modules.requirement.application.relations import (
    RequirementRelationService,
)
from plm_assistant.modules.requirement.application.review_subject import (
    RequirementReviewSubjectOwner,
)
from plm_assistant.modules.requirement.application.submit_review import (
    RequirementReviewSubmissionService,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionCurrentValidator, RequirementVersionValidationService,
)
from plm_assistant.modules.requirement.infrastructure.human_decision_source_proof import (
    SqlAlchemyRequirementHumanDecisionSourceProof,
)
from plm_assistant.modules.requirement.infrastructure.identity_create_repository import (
    SqlAlchemyRequirementIdentityCreateRepository,
)
from plm_assistant.modules.requirement.infrastructure.identity_read_repository import (
    SqlAlchemyRequirementIdentityReadRepository,
)
from plm_assistant.modules.requirement.infrastructure.package_mutation_repository import (
    SqlAlchemyRequirementPackageMutationRepository,
)
from plm_assistant.modules.requirement.infrastructure.relation_repository import (
    SqlAlchemyRequirementRelationRepository,
)
from plm_assistant.modules.requirement.infrastructure.requirement_mutation_repository import (
    SqlAlchemyRequirementMutationRepository,
)
from plm_assistant.modules.requirement.infrastructure.review_subject_repository import (
    SqlAlchemyRequirementReviewSubjectRepository,
)
from plm_assistant.modules.requirement.infrastructure.version_create_repository import (
    SqlAlchemyRequirementVersionCreateRepository,
)
from plm_assistant.modules.requirement.infrastructure.version_read_repository import (
    SqlAlchemyRequirementVersionReadRepository,
)
from plm_assistant.modules.requirement.infrastructure.version_validation_repository import (
    SqlAlchemyRequirementVersionValidationRepository,
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
from plm_assistant.modules.survey.infrastructure.requirement_source_proof import (
    SqlAlchemySurveyConclusionRequirementSourceProof,
)


REQUIREMENT_PACKAGE_CURSOR_KEY_REF = "requirement-package-cursor-v1"
REQUIREMENT_CURSOR_KEY_REF = "requirement-cursor-v1"
REQUIREMENT_VERSION_CURSOR_KEY_REF = "requirement-version-cursor-v1"
REQUIREMENT_RELATION_CURSOR_KEY_REF = "requirement-relation-cursor-v1"


class RequirementKeyResolverPort(Protocol):
    def resolve_key(self, key_ref: str) -> bytes | None: ...


class ProductionRequirementStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Requirement production composition unavailable")


@dataclass(frozen=True, slots=True)
class WindowsRequirementRouters:
    packages: APIRouter
    requirements: APIRouter
    versions: APIRouter
    relations: APIRouter
    review_submission: APIRouter | None


def _read_routes(router: APIRouter) -> APIRouter:
    result = APIRouter()
    result.routes.extend(
        route for route in router.routes
        if "GET" in getattr(route, "methods", set())
    )
    return result


def create_windows_requirement_routers(
    runtime, *, sessions, origins, license_guard, audit,
    include_write: bool, resolver: RequirementKeyResolverPort | None = None,
) -> WindowsRequirementRouters:
    """Compose seven read routes or all 22 frozen Requirement operations."""
    if type(include_write) is not bool:
        raise ProductionRequirementStartupError()
    try:
        keys = resolver or WindowsSecretKeyProvider()
        package_cursors = RequirementPackageCursorCodec(
            keys.resolve_key(REQUIREMENT_PACKAGE_CURSOR_KEY_REF),
        )
        requirement_cursors = RequirementCursorCodec(
            keys.resolve_key(REQUIREMENT_CURSOR_KEY_REF),
        )
        version_cursors = RequirementVersionCursorCodec(
            keys.resolve_key(REQUIREMENT_VERSION_CURSOR_KEY_REF),
        )
        relation_cursors = RequirementRelationCursorCodec(
            keys.resolve_key(REQUIREMENT_RELATION_CURSOR_KEY_REF),
        )
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        )
        read_access = SqlAlchemyProjectReadAccess()
        write_access = SqlAlchemyProjectWriteAccess()
        receipts = SqlAlchemyIdempotencyReceipts()
        common = {
            "unit_of_work": runtime.unit_of_work,
            "license_guard": license_guard,
            "authorization": authorization,
        }
        reads = RequirementIdentityReadService(
            **common, access=read_access,
            repository=SqlAlchemyRequirementIdentityReadRepository(),
        )
        creates = RequirementIdentityCreateService(
            **common, access=write_access,
            repository=SqlAlchemyRequirementIdentityCreateRepository(),
            receipts=receipts, audit=audit,
        )
        package_mutations = RequirementPackageMutationService(
            **common, access=write_access,
            repository=SqlAlchemyRequirementPackageMutationRepository(),
            receipts=receipts, audit=audit,
        )
        requirement_mutations = RequirementMutationService(
            **common, access=write_access,
            repository=SqlAlchemyRequirementMutationRepository(),
            receipts=receipts, audit=audit,
        )

        survey_sources = SqlAlchemySurveyConclusionRequirementSourceProof()
        handover_sources = SqlAlchemyHandoverRequirementSourceProof()
        human_decisions = SqlAlchemyRequirementHumanDecisionSourceProof()
        project_evidence = SqlAlchemyEvidenceRequirementSourceProof()
        capability_sources = SqlAlchemyCapabilityRequirementSourceProof()
        fixed_evidence = SqlAlchemyEvidenceFixedSourceRepository()
        source_proofs = {
            "survey_sources": survey_sources,
            "handover_sources": handover_sources,
            "human_decisions": human_decisions,
            "project_evidence": project_evidence,
            "capability_sources": capability_sources,
            "fixed_evidence": fixed_evidence,
        }
        version_reads = RequirementVersionReadService(
            **common, access=read_access,
            repository=SqlAlchemyRequirementVersionReadRepository(),
        )
        version_creates = RequirementVersionCreateService(
            **common, access=write_access,
            repository=SqlAlchemyRequirementVersionCreateRepository(),
            receipts=receipts, audit=audit, **source_proofs,
        )
        version_validations = RequirementVersionValidationService(
            **common, access=write_access,
            repository=SqlAlchemyRequirementVersionValidationRepository(),
            receipts=receipts, audit=audit,
            audit_source=SqlAlchemyRequirementValidationAuditSource(),
            **source_proofs,
        )
        relations = RequirementRelationService(
            unit_of_work=runtime.unit_of_work, write_access=write_access,
            read_access=read_access, license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyRequirementRelationRepository(),
            receipts=receipts, audit=audit,
        )

        package_router = create_requirement_package_router(
            sessions=sessions, origins=origins, reads=reads, creates=creates,
            mutations=package_mutations, cursors=package_cursors,
        )
        requirement_router = create_requirement_router(
            sessions=sessions, origins=origins, reads=reads, creates=creates,
            mutations=requirement_mutations, cursors=requirement_cursors,
        )
        version_router = create_requirement_version_router(
            sessions=sessions, origins=origins, reads=version_reads,
            creates=version_creates, validations=version_validations,
            cursors=version_cursors,
        )
        relation_router = create_requirement_relation_router(
            sessions=sessions, origins=origins, relations=relations,
            cursors=relation_cursors,
        )
        if not include_write:
            return WindowsRequirementRouters(
                _read_routes(package_router), _read_routes(requirement_router),
                _read_routes(version_router), _read_routes(relation_router), None,
            )

        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        subject = RequirementReviewSubjectOwner(
            repository=SqlAlchemyRequirementReviewSubjectRepository(),
            reviewers=reviewers,
            current=RequirementVersionCurrentValidator(**source_proofs),
            audit=audit,
        )
        submission = RequirementReviewSubmissionService(
            unit_of_work=runtime.unit_of_work, access=write_access,
            license_guard=license_guard, authorization=authorization,
            reviewers=reviewers, receipts=receipts,
            replay_repository=SqlAlchemyProjectReviewSubmissionRepository(),
            reviews=ProjectReviewPersistenceService(
                creation_repository=SqlAlchemyReviewCreationRepository(),
                round_repository=SqlAlchemyReviewStartRepository(),
                audit=audit, subjects=subject,
            ),
            subjects=subject,
        )
        review_router = create_requirement_review_submission_router(
            sessions=sessions, origins=origins, submissions=submission,
        )
        return WindowsRequirementRouters(
            package_router, requirement_router, version_router,
            relation_router, review_router,
        )
    except Exception:
        raise ProductionRequirementStartupError() from None
