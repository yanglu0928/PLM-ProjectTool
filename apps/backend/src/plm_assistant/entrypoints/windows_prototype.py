"""Fail-closed Windows composition for frozen Prototype operations."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter

from plm_assistant.entrypoints.windows_prototype_cursor import (
    PrototypeCursorKeyResolverPort,
    create_windows_prototype_cursor_codecs,
)
from plm_assistant.modules.audit.infrastructure.prototype_validation_source import (
    SqlAlchemyPrototypeValidationAuditSource,
)
from plm_assistant.modules.auth.infrastructure.deployment_read_access import (
    SqlAlchemyDeploymentReadAccess,
)
from plm_assistant.modules.auth.infrastructure.license_import_access import (
    SqlAlchemyLicenseImportAccess,
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
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import (
    SqlAlchemyPrototypeDocumentArtifactProof,
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
from plm_assistant.modules.prototype.api.packages import (
    create_prototype_package_router,
)
from plm_assistant.modules.prototype.api.prototypes import create_prototype_router
from plm_assistant.modules.prototype.api.requirement_links import (
    create_requirement_prototype_link_router,
)
from plm_assistant.modules.prototype.api.submit_review import (
    create_prototype_review_submission_router,
)
from plm_assistant.modules.prototype.api.templates import (
    create_prototype_template_router,
)
from plm_assistant.modules.prototype.api.versions import (
    create_prototype_version_router,
)
from plm_assistant.modules.prototype.application.approval_trace import (
    PrototypeApprovalTraceOwner,
)
from plm_assistant.modules.prototype.application.create_identity import (
    PrototypeIdentityCreateService,
)
from plm_assistant.modules.prototype.application.create_template import (
    PrototypeTemplateCreateService,
)
from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionCreateService,
)
from plm_assistant.modules.prototype.application.current_version import (
    PrototypeVersionCurrentValidator,
)
from plm_assistant.modules.prototype.application.mark_not_required import (
    PrototypeScopeDecisionService,
)
from plm_assistant.modules.prototype.application.mutate_package import (
    PrototypePackageMutationService,
)
from plm_assistant.modules.prototype.application.mutate_prototype import (
    PrototypeMutationService,
)
from plm_assistant.modules.prototype.application.read_identities import (
    PrototypeIdentityReadService,
)
from plm_assistant.modules.prototype.application.read_templates import (
    PrototypeTemplateReadService,
)
from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeVersionReadValidationService,
)
from plm_assistant.modules.prototype.application.requirement_links import (
    RequirementPrototypeLinkService,
)
from plm_assistant.modules.prototype.application.review_subject import (
    PrototypeReviewSubjectOwner,
)
from plm_assistant.modules.prototype.application.revise_template import (
    PrototypeTemplateReviseService,
)
from plm_assistant.modules.prototype.application.submit_review import (
    PrototypeReviewSubmissionService,
)
from plm_assistant.modules.prototype.infrastructure.approval_trace_repository import (
    SqlAlchemyPrototypeApprovalTraceRepository,
)
from plm_assistant.modules.prototype.infrastructure.identity_create_repository import (
    SqlAlchemyPrototypeIdentityCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.identity_read_repository import (
    SqlAlchemyPrototypeIdentityReadRepository,
)
from plm_assistant.modules.prototype.infrastructure.package_mutation_repository import (
    SqlAlchemyPrototypePackageMutationRepository,
)
from plm_assistant.modules.prototype.infrastructure.prototype_mutation_repository import (
    SqlAlchemyPrototypeMutationRepository,
)
from plm_assistant.modules.prototype.infrastructure.requirement_link_repository import (
    SqlAlchemyRequirementPrototypeLinkRepository,
)
from plm_assistant.modules.prototype.infrastructure.review_subject_repository import (
    SqlAlchemyPrototypeReviewSubjectRepository,
)
from plm_assistant.modules.prototype.infrastructure.scope_decision_repository import (
    SqlAlchemyPrototypeScopeDecisionRepository,
)
from plm_assistant.modules.prototype.infrastructure.template_create_repository import (
    SqlAlchemyPrototypeTemplateCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.template_read_repository import (
    SqlAlchemyPrototypeTemplateReadRepository,
)
from plm_assistant.modules.prototype.infrastructure.template_revise_repository import (
    SqlAlchemyPrototypeTemplateReviseRepository,
)
from plm_assistant.modules.prototype.infrastructure.version_create_repository import (
    SqlAlchemyPrototypeVersionCreateRepository,
)
from plm_assistant.modules.prototype.infrastructure.version_input_proofs import (
    SqlAlchemyPrototypeVersionTemplateProof,
)
from plm_assistant.modules.prototype.infrastructure.version_read_repository import (
    SqlAlchemyPrototypeVersionReadRepository,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
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
from plm_assistant.modules.trace.infrastructure.create_repository import (
    SqlAlchemyTraceCreateRepository,
)


class ProductionPrototypeStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Prototype production composition unavailable")


@dataclass(frozen=True, slots=True)
class WindowsPrototypeRouters:
    packages: APIRouter
    prototypes: APIRouter
    templates: APIRouter
    versions: APIRouter
    links: APIRouter
    review_submission: APIRouter | None


def _read_routes(router: APIRouter) -> APIRouter:
    result = APIRouter()
    result.routes.extend(
        route for route in router.routes
        if "GET" in getattr(route, "methods", set())
    )
    return result


def create_windows_prototype_review_subject(
    *, reviewers: ProjectReviewerQualificationService, audit,
) -> PrototypeReviewSubjectOwner:
    """Build the same PRT-03 owner for submission and global Review commands."""
    templates = SqlAlchemyPrototypeVersionTemplateProof()
    requirements = SqlAlchemyPrototypeApprovedRequirementVersionProof()
    documents = SqlAlchemyPrototypeDocumentArtifactProof()
    current = PrototypeVersionCurrentValidator(
        templates=templates, requirements=requirements, documents=documents,
    )
    approval_trace = PrototypeApprovalTraceOwner(
        current=current, trace_links=SqlAlchemyTraceCreateRepository(),
        manifests=SqlAlchemyPrototypeApprovalTraceRepository(),
    )
    return PrototypeReviewSubjectOwner(
        repository=SqlAlchemyPrototypeReviewSubjectRepository(),
        reviewers=reviewers, current=current, audit=audit,
        approval_trace=approval_trace,
    )


def create_windows_prototype_routers(
    runtime, *, sessions, origins, license_guard, audit,
    include_write: bool,
    resolver: PrototypeCursorKeyResolverPort | None = None,
) -> WindowsPrototypeRouters:
    """Compose nine read routes or all 26 frozen Prototype operations."""
    if type(include_write) is not bool:
        raise ProductionPrototypeStartupError()
    try:
        cursors = create_windows_prototype_cursor_codecs(resolver=resolver)
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

        identity_reads = PrototypeIdentityReadService(
            **common, access=read_access,
            repository=SqlAlchemyPrototypeIdentityReadRepository(),
        )
        identity_creates = PrototypeIdentityCreateService(
            **common, access=write_access,
            repository=SqlAlchemyPrototypeIdentityCreateRepository(),
            receipts=receipts, audit=audit,
        )
        package_mutations = PrototypePackageMutationService(
            **common, access=write_access,
            repository=SqlAlchemyPrototypePackageMutationRepository(),
            receipts=receipts, audit=audit,
        )
        prototype_mutations = PrototypeMutationService(
            **common, access=write_access,
            repository=SqlAlchemyPrototypeMutationRepository(),
            receipts=receipts, audit=audit,
        )
        scope_decisions = PrototypeScopeDecisionService(
            **common, access=write_access,
            repository=SqlAlchemyPrototypeScopeDecisionRepository(),
            receipts=receipts, audit=audit,
        )

        documents = SqlAlchemyPrototypeDocumentArtifactProof()
        requirements = SqlAlchemyPrototypeApprovedRequirementVersionProof()
        templates = SqlAlchemyPrototypeVersionTemplateProof()
        template_reads = PrototypeTemplateReadService(
            **common, project_access=read_access,
            admin_access=SqlAlchemyDeploymentReadAccess(),
            repository=SqlAlchemyPrototypeTemplateReadRepository(),
        )
        template_creates = PrototypeTemplateCreateService(
            **common, project_access=write_access,
            admin_access=SqlAlchemyLicenseImportAccess(),
            document_artifacts=documents,
            repository=SqlAlchemyPrototypeTemplateCreateRepository(),
            receipts=receipts, audit=audit,
        )
        template_revisions = PrototypeTemplateReviseService(
            **common, project_access=write_access,
            admin_access=SqlAlchemyLicenseImportAccess(),
            document_artifacts=documents,
            repository=SqlAlchemyPrototypeTemplateReviseRepository(),
            receipts=receipts, audit=audit,
        )
        version_reader = SqlAlchemyPrototypeVersionReadRepository()
        version_reads = PrototypeVersionReadValidationService(
            **common, project_access=read_access, repository=version_reader,
            templates=templates, requirements=requirements, documents=documents,
            audit_source=SqlAlchemyPrototypeValidationAuditSource(),
            receipts=receipts, audit=audit,
        )
        version_creates = PrototypeVersionCreateService(
            **common, project_access=write_access,
            requirements=requirements, templates=templates, documents=documents,
            repository=SqlAlchemyPrototypeVersionCreateRepository(),
            receipts=receipts, audit=audit,
        )
        current = PrototypeVersionCurrentValidator(
            templates=templates, requirements=requirements, documents=documents,
        )
        links = RequirementPrototypeLinkService(
            unit_of_work=runtime.unit_of_work, write_access=write_access,
            read_access=read_access, license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyRequirementPrototypeLinkRepository(),
            version_reader=version_reader, current_validator=current,
            receipts=receipts, audit=audit,
        )

        package_router = create_prototype_package_router(
            sessions=sessions, origins=origins, reads=identity_reads,
            creates=identity_creates, mutations=package_mutations,
            cursors=cursors.package,
        )
        prototype_router = create_prototype_router(
            sessions=sessions, origins=origins, reads=identity_reads,
            creates=identity_creates, mutations=prototype_mutations,
            decisions=scope_decisions, cursors=cursors.prototype,
        )
        template_router = create_prototype_template_router(
            sessions=sessions, origins=origins, reads=template_reads,
            creates=template_creates, revisions=template_revisions,
            cursors=cursors.template,
        )
        version_router = create_prototype_version_router(
            sessions=sessions, origins=origins, reads=version_reads,
            creates=version_creates, cursors=cursors.version,
        )
        link_router = create_requirement_prototype_link_router(
            sessions=sessions, origins=origins, service=links,
            cursors=cursors.link,
        )
        if not include_write:
            return WindowsPrototypeRouters(
                _read_routes(package_router), _read_routes(prototype_router),
                _read_routes(template_router), _read_routes(version_router),
                _read_routes(link_router), None,
            )

        reviewers = ProjectReviewerQualificationService(
            users=SqlAlchemyReviewUserAccess(), projects=project_repository,
        )
        subject = create_windows_prototype_review_subject(
            reviewers=reviewers, audit=audit,
        )
        submission = PrototypeReviewSubmissionService(
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
        review_router = create_prototype_review_submission_router(
            sessions=sessions, origins=origins, submissions=submission,
        )
        return WindowsPrototypeRouters(
            package_router, prototype_router, template_router, version_router,
            link_router, review_router,
        )
    except Exception:
        raise ProductionPrototypeStartupError() from None
