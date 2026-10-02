"""Fail-closed Windows production composition for the frozen login endpoint."""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from sqlalchemy import create_engine, text

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.password_capacity import get_process_password_capacity
from plm_assistant.entrypoints.windows_audit_list_cursor import create_windows_audit_cursor_codec
from plm_assistant.modules.audit.api.read_events import create_audit_read_router
from plm_assistant.modules.audit.application.authorized_read import AuthorizedAuditReadService
from plm_assistant.modules.audit.infrastructure.audit_read_repository import SqlAlchemyAuditReadRepository
from plm_assistant.modules.audit.api.read_export_result import create_audit_export_result_router
from plm_assistant.modules.audit.api.download_export import create_audit_export_download_router
from plm_assistant.modules.audit.application.export_content import AuditExportContentReader, PrepareAuditExportContent
from plm_assistant.modules.audit.infrastructure.export_submit_repository import SqlAlchemyAuditExportSubmitRepository
from plm_assistant.modules.audit.infrastructure.export_result_repository import SqlAlchemyAuditExportResults
from plm_assistant.modules.audit.infrastructure.render_plan_repository import SqlAlchemyAuditRenderPlans
from plm_assistant.modules.document.infrastructure.audit_export_metadata import SqlAlchemyAuditExportFileMetadata
from plm_assistant.modules.document.infrastructure.audit_export_storage import LocalAuditExportFileStorage
from plm_assistant.modules.jobs.application.audit_export_complete import AuditExportJobCompletion
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobQueue
from plm_assistant.modules.jobs.infrastructure.audit_export_enqueue_repository import SqlAlchemyAuditExportJobQueueRepository
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.api.read_detail import create_job_detail_router
from plm_assistant.modules.auth.api.user_detail import create_user_detail_router
from plm_assistant.modules.auth.api.user_list import create_user_list_router
from plm_assistant.modules.auth.api.user_create import create_user_create_router
from plm_assistant.modules.auth.api.user_name_patch import create_user_name_patch_router
from plm_assistant.modules.auth.api.user_state import create_user_state_router
from plm_assistant.modules.auth.api.password_change import create_password_change_router
from plm_assistant.modules.auth.api.password_reset import create_password_reset_router
from plm_assistant.modules.auth.application.password_reset import PasswordResetService
from plm_assistant.modules.auth.application.password_reset_replay import PasswordResetReplayVerifier
from plm_assistant.modules.auth.infrastructure.password_reset_access import SqlAlchemyPasswordResetAccess
from plm_assistant.modules.auth.infrastructure.password_reset_repository import SqlAlchemyPasswordResetRepository
from plm_assistant.modules.auth.infrastructure.password_reset_result_repository import SqlAlchemyPasswordResetResults
from plm_assistant.modules.auth.application.password_change import PasswordChangeService
from plm_assistant.modules.auth.application.password_change_replay import PasswordChangeReplayVerifier
from plm_assistant.modules.auth.infrastructure.password_change_access import SqlAlchemyPasswordChangeAccess
from plm_assistant.modules.auth.infrastructure.password_change_repository import SqlAlchemyPasswordChangeRepository
from plm_assistant.modules.auth.infrastructure.password_change_result_repository import SqlAlchemyPasswordChangeResults
from plm_assistant.modules.auth.application.user_state import UserStateService
from plm_assistant.modules.auth.infrastructure.user_state_access import SqlAlchemyUserStateAccess
from plm_assistant.modules.auth.infrastructure.user_state_repository import SqlAlchemyUserStateRepository
from plm_assistant.modules.auth.infrastructure.user_state_result_repository import SqlAlchemyUserStateResultRepository
from plm_assistant.modules.auth.application.user_name_patch import UserNamePatchService
from plm_assistant.modules.auth.infrastructure.user_name_patch_repository import SqlAlchemyUserNamePatchRepository
from plm_assistant.modules.auth.application.managed_user_create import ManagedUserCreateService
from plm_assistant.modules.auth.application.user_create_replay import UserCreateReplayVerifier
from plm_assistant.modules.auth.infrastructure.user_create_result_repository import SqlAlchemyUserCreateResultRepository
from plm_assistant.modules.auth.infrastructure.user_create_access import SqlAlchemyUserCreateAccess
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.auth.application.user_list import AuthorizedUserListService
from plm_assistant.entrypoints.windows_user_list_cursor import create_windows_user_list_cursor_codec
from plm_assistant.modules.auth.application.user_read import AuthorizedUserReadService
from plm_assistant.modules.auth.infrastructure.user_read_repository import SqlAlchemyUserReadRepository
from plm_assistant.modules.jobs.api.cancel import create_project_job_cancel_router
from plm_assistant.modules.jobs.api.retry import create_job_retry_router
from plm_assistant.modules.jobs.application.retry_request import JobRetryRequests
from plm_assistant.modules.audit.application.job_retry_adapter import AuditJobRetryOwner
from plm_assistant.modules.audit.application.request_user_retry import AuditUserRetryService
from plm_assistant.modules.audit.application.user_retry_source import AuditUserRetrySourceReader
from plm_assistant.modules.audit.infrastructure.user_retry_failure_source import SqlAlchemyAuditUserRetryFailureSources
from plm_assistant.modules.audit.infrastructure.retry_generation_repository import SqlAlchemyAuditRetryGenerations
from plm_assistant.modules.jobs.application.audit_user_retry_source import AuditUserRetryJobSources
from plm_assistant.modules.jobs.infrastructure.audit_user_retry_source import SqlAlchemyAuditUserRetryJobSources
from plm_assistant.modules.jobs.application.cancel_request import ProjectJobCancellation
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellation
from plm_assistant.modules.jobs.infrastructure.audit_export_cancel_repository import SqlAlchemyAuditExportCancellationRepository
from plm_assistant.modules.audit.application.job_cancel_adapter import AuditJobCancelOwner
from plm_assistant.modules.audit.application.request_export_cancel import AuditExportCancelRequestService
from plm_assistant.modules.audit.application.export_cancel_authorization import AuditExportCancelAuthorization
from plm_assistant.modules.audit.infrastructure.export_cancel_sources import SqlAlchemyAuditExportCancelSources
from plm_assistant.modules.audit.infrastructure.parse_cancel_sources import SqlAlchemyParseCancelAuditSources
from plm_assistant.modules.document.application.request_parse_cancel import DocumentParseJobCancelOwner
from plm_assistant.modules.jobs.infrastructure.parse_cancel_repository import SqlAlchemyParseCancellationRepository
from plm_assistant.modules.jobs.application.authorized_read import AuthorizedJobReadService
from plm_assistant.modules.jobs.application.authorized_list import AuthorizedJobListService
from plm_assistant.modules.jobs.api.list_jobs import create_job_list_router
from plm_assistant.entrypoints.windows_job_list_cursor import create_windows_job_list_cursor_codec
from plm_assistant.modules.jobs.infrastructure.read_repository import SqlAlchemyJobReadRepository
from plm_assistant.modules.audit.application.job_read_projection import AuditJobReadProjection
from plm_assistant.modules.document.application.job_read_projection import DocumentParseJobReadProjection
from plm_assistant.modules.document.application.parse_job_source import DocumentParseSourceReader
from plm_assistant.modules.document.infrastructure.parse_job_source import SqlAlchemyDocumentParseSources
from plm_assistant.modules.document.application.parse_job_result import DocumentParseJobResults
from plm_assistant.modules.document.infrastructure.parse_job_result import SqlAlchemyDocumentParseJobResults
from plm_assistant.modules.audit.application.upload_commit_source import UploadCommitAuditSources
from plm_assistant.modules.audit.infrastructure.upload_commit_source import SqlAlchemyUploadCommitAuditSources
from plm_assistant.modules.audit.api.submit_export import create_audit_export_submit_router
from plm_assistant.modules.audit.application.submit_export import AuditExportSubmitService
from plm_assistant.modules.audit.application.export_submit_authorization import AuditExportSubmitAuthorization
from plm_assistant.entrypoints.windows_secret_list_cursor import create_windows_secret_list_cursor_codec
from plm_assistant.entrypoints.windows_ai_provider_list_cursor import create_windows_ai_provider_list_cursor_codec
from plm_assistant.modules.ai.api.provider_metadata import create_ai_provider_read_router
from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataService
from plm_assistant.modules.ai.infrastructure.provider_metadata_repository import SqlAlchemyAIProviderMetadataRepository
from plm_assistant.modules.ai.api.create_provider import create_ai_provider_create_router
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateService
from plm_assistant.modules.ai.infrastructure.provider_create_repository import SqlAlchemyAIProviderCreateRepository
from plm_assistant.modules.ai.api.patch_provider import create_ai_provider_patch_router
from plm_assistant.modules.ai.application.append_provider_config import AIProviderAppendService
from plm_assistant.modules.ai.infrastructure.provider_append_repository import SqlAlchemyAIProviderAppendRepository
from plm_assistant.modules.platform.infrastructure.ai_provider_secret_proof import SqlAlchemyAIProviderSecretProof
from plm_assistant.entrypoints.windows_project_member_cursor import create_windows_project_member_cursor_codec
from plm_assistant.entrypoints.windows_project_department_cursor import create_windows_project_department_cursor_codec
from plm_assistant.entrypoints.windows_document_upload_token import create_windows_document_upload_token_issuer
from plm_assistant.entrypoints.windows_document_list_cursor import create_windows_document_list_cursor_codec
from plm_assistant.entrypoints.windows_document_version_cursor import create_windows_document_version_cursor_codec
from plm_assistant.entrypoints.windows_document_parse_cursor import create_windows_document_parse_cursor_codec
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.api.login import create_login_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    create_session_read_router,
    create_session_renew_router,
    create_session_logout_router,
)
from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimiter
from plm_assistant.modules.auth.application.login_service import LoginService
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.login_identity import SqlAlchemyLoginIdentity
from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
from plm_assistant.modules.auth.infrastructure.missing_identity_verifier import ScryptMissingIdentityVerifier
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.platform.api.secret_metadata import (
    create_secret_metadata_detail_router, create_secret_metadata_list_router,
)
from plm_assistant.modules.platform.api.secret_create import create_secret_create_router
from plm_assistant.modules.platform.api.secret_rotate import create_secret_rotate_router
from plm_assistant.modules.platform.api.secret_disable import create_secret_disable_router
from plm_assistant.modules.platform.application.secret_metadata import SecretMetadataService
from plm_assistant.modules.platform.infrastructure.secret_metadata_repository import (
    SqlAlchemySecretMetadataRepository,
)
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime, create_database_runtime
from plm_assistant.modules.platform.infrastructure.maintenance_admission import PostgresMaintenanceAdmission
from plm_assistant.modules.platform.infrastructure.migration import MIGRATION_PACKAGE
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    DEFAULT_TARGET,
    read_database_url,
)
from plm_assistant.modules.project.api.read_projects import create_project_read_router
from plm_assistant.modules.project.application.read_projects import ProjectReadService
from plm_assistant.modules.project.infrastructure.read_repository import SqlAlchemyProjectReadRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.project_create_access import SqlAlchemyProjectCreateAccess
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.project.api.create_project import create_project_create_router
from plm_assistant.modules.project.application.create_project import ProjectCreateService
from plm_assistant.modules.workflow.application.initialize import WorkflowInitializationService
from plm_assistant.modules.workflow.application.read_workflow import WorkflowReadService
from plm_assistant.modules.workflow.application.start_workflow import WorkflowStartService
from plm_assistant.modules.workflow.infrastructure.read_repository import SqlAlchemyWorkflowReadRepository
from plm_assistant.modules.workflow.api.read_workflow import create_workflow_read_router
from plm_assistant.modules.workflow.api.start_workflow import create_workflow_start_router
from plm_assistant.modules.workflow.infrastructure.start_repository import SqlAlchemyWorkflowStartRepository
from plm_assistant.modules.workflow.infrastructure.initialize_repository import SqlAlchemyWorkflowInitializationRepository
from plm_assistant.modules.project.infrastructure.create_repository import SqlAlchemyProjectCreateRepository
from plm_assistant.modules.project.api.patch_project import create_project_patch_router
from plm_assistant.modules.project.api.archive_project import create_project_archive_router
from plm_assistant.modules.project.api.read_members import create_project_member_read_router
from plm_assistant.modules.project.api.create_member import create_project_member_create_router
from plm_assistant.modules.project.api.member_candidates import create_project_member_candidate_router
from plm_assistant.modules.project.api.patch_member import create_project_member_patch_router
from plm_assistant.modules.project.api.change_member_state import create_project_member_state_router
from plm_assistant.modules.project.api.read_departments import create_project_department_read_router
from plm_assistant.modules.project.api.create_department import create_project_department_create_router
from plm_assistant.modules.project.api.patch_department import create_project_department_patch_router
from plm_assistant.modules.project.api.deactivate_department import create_project_department_deactivate_router
from plm_assistant.modules.project.application.read_members import ProjectMemberReadService
from plm_assistant.modules.project.application.create_member import ProjectMemberCreateService
from plm_assistant.modules.project.application.member_candidates import ProjectMemberCandidateService
from plm_assistant.modules.project.application.patch_member import ProjectMemberPatchService
from plm_assistant.modules.project.application.change_member_state import ProjectMemberStateService
from plm_assistant.modules.project.application.read_departments import ProjectDepartmentReadService
from plm_assistant.modules.project.application.create_department import ProjectDepartmentCreateService
from plm_assistant.modules.project.application.patch_department import ProjectDepartmentPatchService
from plm_assistant.modules.project.application.deactivate_department import ProjectDepartmentDeactivateService
from plm_assistant.modules.project.infrastructure.member_read_repository import SqlAlchemyProjectMemberReadRepository
from plm_assistant.modules.project.infrastructure.member_create_repository import SqlAlchemyProjectMemberCreateRepository
from plm_assistant.modules.project.infrastructure.member_patch_repository import SqlAlchemyProjectMemberPatchRepository
from plm_assistant.modules.project.infrastructure.member_state_repository import SqlAlchemyProjectMemberStateRepository
from plm_assistant.modules.project.infrastructure.department_read_repository import SqlAlchemyProjectDepartmentReadRepository
from plm_assistant.modules.project.infrastructure.department_create_repository import SqlAlchemyProjectDepartmentCreateRepository
from plm_assistant.modules.project.infrastructure.department_patch_repository import SqlAlchemyProjectDepartmentPatchRepository
from plm_assistant.modules.project.infrastructure.department_deactivate_repository import SqlAlchemyProjectDepartmentDeactivateRepository
from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames
from plm_assistant.modules.auth.infrastructure.project_member_create_access import SqlAlchemyProjectMemberCreateAccess
from plm_assistant.modules.auth.infrastructure.project_member_candidate_access import SqlAlchemyProjectMemberCandidateAccess
from plm_assistant.modules.project.infrastructure.member_candidate_repository import SqlAlchemyMemberCandidateMembership
from plm_assistant.modules.auth.infrastructure.project_member_patch_access import SqlAlchemyProjectMemberPatchAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.write_project import ProjectWriteService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.write_repository import SqlAlchemyProjectWriteRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.document.api.create_upload import create_document_upload_create_router
from plm_assistant.modules.document.api.read_documents import create_document_read_router
from plm_assistant.modules.document.api.read_versions import create_document_version_read_router
from plm_assistant.modules.document.api.read_parses import create_document_parse_read_router
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.application.prepare_download import PrepareDownloadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.document.application.read_parse_result import DocumentParseResultReadService
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import SqlAlchemyParseResultReadRepository
from plm_assistant.modules.document.infrastructure.parse_result_storage import LocalParseResultStorage
from plm_assistant.modules.evidence.api.create_evidence import create_evidence_create_router
from plm_assistant.modules.evidence.api.read_evidence import create_evidence_read_router
from plm_assistant.modules.evidence.api.view_evidence import create_evidence_viewer_router
from plm_assistant.modules.evidence.api.set_eligibility import create_evidence_eligibility_router
from plm_assistant.modules.evidence.api.lookup_eligibility_operation import create_evidence_eligibility_operation_lookup_router
from plm_assistant.modules.evidence.application.create_access import EvidenceCreateAccess
from plm_assistant.modules.evidence.application.create_evidence import EvidenceCreateService
from plm_assistant.modules.evidence.application.eligibility_access import EvidenceEligibilityAccess
from plm_assistant.modules.evidence.application.set_eligibility import EvidenceEligibilityService
from plm_assistant.modules.evidence.application.lookup_eligibility_operation import EvidenceEligibilityOperationLookupService
from plm_assistant.modules.evidence.application.read_evidence import EvidenceReadService
from plm_assistant.modules.evidence.application.view_evidence import EvidenceViewerService
from plm_assistant.modules.evidence.application.document_source_proof import DocumentEvidenceProofService
from plm_assistant.modules.evidence.application.parsed_node_proof import ParsedNodeEvidenceProofService
from plm_assistant.modules.evidence.infrastructure.create_repository import SqlAlchemyEvidenceCreateRepository
from plm_assistant.modules.evidence.infrastructure.eligibility_repository import SqlAlchemyEvidenceEligibilityRepository
from plm_assistant.modules.evidence.infrastructure.read_repository import SqlAlchemyEvidenceReadRepository
from plm_assistant.entrypoints.windows_evidence_list_cursor import (
    ProductionEvidenceCursorStartupError, create_windows_evidence_list_cursor_codec,
)
from plm_assistant.modules.document.application.create_upload_intent import CreateUploadIntentService
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccess
from plm_assistant.modules.document.infrastructure.upload_intent_repository import SqlAlchemyUploadIntentRepository
from plm_assistant.modules.document.api.upload_content import create_document_upload_content_router
from plm_assistant.modules.document.application.receive_upload_content import ReceiveUploadContentService
from plm_assistant.modules.document.infrastructure.upload_content_repository import SqlAlchemyUploadContentRepository
from plm_assistant.modules.document.infrastructure.content_spool import ValidatedContentSpool
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.upload_operation_gate import LocalUploadOperationGate
from plm_assistant.modules.document.api.finalize_upload import create_document_upload_finalize_router
from plm_assistant.modules.document.application.commit_upload import CommitUploadService
from plm_assistant.modules.document.application.abort_upload import AbortUploadService
from plm_assistant.modules.document.infrastructure.upload_commit_repository import SqlAlchemyUploadCommitRepository
from plm_assistant.modules.document.infrastructure.upload_abort_repository import SqlAlchemyUploadAbortRepository
from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobQueue
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository


class ProductionLoginStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("production login unavailable")


def _schema_current(runtime: DatabaseRuntime) -> bool:
    config = Config()
    config.set_main_option("script_location", str(MIGRATION_PACKAGE))
    expected = ScriptDirectory.from_config(config).get_current_head()
    if expected is None:
        return False
    with runtime.unit_of_work() as transaction:
        versions = transaction.session.execute(text("SELECT version_num FROM plm.alembic_version")).scalars().all()
    return versions == [expected]


def create_production_login_app(
    settings: BootstrapSettings, *, credential_target: str = DEFAULT_TARGET,
) -> FastAPI:
    """Read the current account's credential and wire real PostgreSQL adapters."""

    return _create_production_app(settings, credential_target=credential_target,
                                  include_secret_read=False, include_secret_write=False)


def create_production_platform_app(
    settings: BootstrapSettings, *, credential_target: str = DEFAULT_TARGET,
) -> FastAPI:
    """Mount protected Secret reads only when every production trust source exists."""

    return _create_production_app(settings, credential_target=credential_target,
                                  include_secret_read=True, include_secret_write=False)


def create_production_platform_write_app(
    settings: BootstrapSettings, *, credential_target: str = DEFAULT_TARGET,
) -> FastAPI:
    """Explicit write mode, closed until all read and write trust sources exist."""

    return _create_production_app(settings, credential_target=credential_target,
                                  include_secret_read=True, include_secret_write=True)


def _create_production_app(settings: BootstrapSettings, *, credential_target: str,
                           include_secret_read: bool,
                           include_secret_write: bool) -> FastAPI:

    if not isinstance(settings, BootstrapSettings):
        raise ProductionLoginStartupError()
    try:
        origins = LoginOriginPolicy(settings.trusted_origins)
        database_url = read_database_url(target=credential_target)
        runtime = create_database_runtime(database_url)
    except Exception:
        raise ProductionLoginStartupError() from None
    maintenance_engine = None
    try:
        if not runtime.is_ready() or not _schema_current(runtime):
            raise ProductionLoginStartupError()
        maintenance_engine = create_engine(
            database_url, pool_pre_ping=True, pool_size=20, max_overflow=0,
            pool_timeout=2, pool_recycle=1800,
            pool_reset_on_return="rollback", isolation_level="READ COMMITTED",
            connect_args={"connect_timeout": 2,
                          "application_name": "plm-maintenance-admission"},
            hide_parameters=True,
        )
        maintenance_admission = PostgresMaintenanceAdmission(maintenance_engine)
        audit = AuditService(SqlAlchemyAuditRepository())
        verifier = ScryptPasswordHasher()
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(verifier),
            audit=audit,
            idempotency=SqlAlchemyIdempotencyReceipts(),
        )
        login = LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=LoginRateLimiter(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyLoginRateRepository(),
            ),
            identity=SqlAlchemyLoginIdentity(),
            missing_verifier=ScryptMissingIdentityVerifier(verifier),
            sessions=sessions,
            audit=audit,
        )
        views = SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work,
            projects=SqlAlchemyAuthorizedProjects(),
        )
        router = create_login_router(login=login, origins=origins, views=views)
        session_router = create_session_read_router(sessions=sessions, origins=origins, views=views)
        renew_router = create_session_renew_router(sessions=sessions, origins=origins, views=views)
        logout_router = create_session_logout_router(sessions=sessions, origins=origins)
        secret_detail_router = None
        secret_list_router = None
        secret_create_router = None
        secret_rotate_router = None
        secret_disable_router = None
        ai_provider_read_router = None
        ai_provider_create_router = None
        ai_provider_patch_router = None
        project_read_router = None
        workflow_read_router = None
        workflow_start_router = None
        audit_read_router = None
        audit_export_result_router = None
        audit_export_download_router = None
        audit_export_submit_router = None
        job_detail_router = None
        user_detail_router = None
        user_list_router = None
        user_create_router = None
        user_name_patch_router = None
        user_state_router = None
        password_change_router = None
        password_reset_router = None
        job_list_router = None
        job_cancel_router = None
        job_retry_router = None
        project_create_router = None
        project_patch_router = None
        project_archive_router = None
        project_member_read_router = None
        project_member_create_router = None
        project_member_candidate_router = None
        project_member_patch_router = None
        project_member_state_router = None
        project_department_read_router = None
        project_department_create_router = None
        project_department_patch_router = None
        project_department_deactivate_router = None
        document_upload_create_router = None
        document_upload_content_router = None
        document_upload_finalize_router = None
        document_read_router = None
        document_version_read_router = None
        document_parse_read_router = None
        document_download_router = None
        evidence_create_router = None
        evidence_read_router = None
        evidence_viewer_router = None
        evidence_eligibility_router = None
        evidence_eligibility_operation_lookup_router = None
        if include_secret_read:
            from plm_assistant.entrypoints.windows_license_runtime import (
                create_windows_license_services,
            )
            licenses = create_windows_license_services(runtime, settings)
            user_detail_router = create_user_detail_router(sessions=sessions,origins=origins,
                reads=AuthorizedUserReadService(unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(),repository=SqlAlchemyUserReadRepository(),
                    license_guard=licenses.guard))
            user_list_router = create_user_list_router(sessions=sessions,origins=origins,
                reads=AuthorizedUserListService(unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(),repository=SqlAlchemyUserReadRepository(),
                    license_guard=licenses.guard),cursors=create_windows_user_list_cursor_codec())
            retry_projects = ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository())
            retry_sources = AuditUserRetrySourceReader(
                repository=SqlAlchemyAuditExportSubmitRepository(),
                jobs=AuditUserRetryJobSources(queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),
                    repository=SqlAlchemyAuditUserRetryJobSources()),
                failures=SqlAlchemyAuditUserRetryFailureSources()) if include_secret_write else None
            job_read_owners = {
                ('audit','AUDIT_EXPORT'):AuditJobReadProjection(
                    repository=SqlAlchemyAuditExportSubmitRepository(),
                    queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),
                    results=SqlAlchemyAuditExportResults(),retry_sources=retry_sources,
                    retry_projects=retry_projects if include_secret_write else None),
                ('document','DOCUMENT_PARSE'):DocumentParseJobReadProjection(
                    queue=ParseJobQueue(SqlAlchemyParseJobQueueRepository()),
                    sources=DocumentParseSourceReader(repository=SqlAlchemyDocumentParseSources(),
                        audit_sources=UploadCommitAuditSources(repository=SqlAlchemyUploadCommitAuditSources())),
                    results=DocumentParseJobResults(repository=SqlAlchemyDocumentParseJobResults()))}
            job_reads = AuthorizedJobReadService(
                    unit_of_work=runtime.unit_of_work,
                    project_access=SqlAlchemyProjectReadAccess(),
                    deployment_access=SqlAlchemyDeploymentReadAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository()),
                    license_guard=licenses.guard,repository=SqlAlchemyJobReadRepository(),
                    owners=job_read_owners,
                )
            job_detail_router = create_job_detail_router(reads=job_reads,origins=origins)
            cursors = create_windows_secret_list_cursor_codec()
            ai_provider_cursors = create_windows_ai_provider_list_cursor_codec()
            member_cursors = create_windows_project_member_cursor_codec()
            department_cursors = create_windows_project_department_cursor_codec()
            audit_cursors = create_windows_audit_cursor_codec()
            job_list_router = create_job_list_router(
                reads=AuthorizedJobListService(unit_of_work=runtime.unit_of_work,
                    project_access=SqlAlchemyProjectReadAccess(),deployment_access=SqlAlchemyDeploymentReadAccess(),
                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository()),
                    license_guard=licenses.guard,repository=SqlAlchemyJobReadRepository(),owners=job_read_owners),
                origins=origins,cursors=create_windows_job_list_cursor_codec())
            audit_read_router = create_audit_read_router(
                reads=AuthorizedAuditReadService(
                    unit_of_work=runtime.unit_of_work,
                    project_access=SqlAlchemyProjectReadAccess(),
                    deployment_access=SqlAlchemyDeploymentReadAccess(),
                    projects=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), license_guard=licenses.guard, repository=SqlAlchemyAuditReadRepository(),
                ), origins=origins, cursors=audit_cursors,
            )
            document_cursors = create_windows_document_list_cursor_codec()
            version_cursors = create_windows_document_version_cursor_codec()
            parse_cursors = create_windows_document_parse_cursor_codec()
            document_reads = DocumentReadService(
                unit_of_work=runtime.unit_of_work,
                session_access=SqlAlchemyProjectReadAccess(),
                admin_access=SqlAlchemyDeploymentReadAccess(),
                project_facts=SqlAlchemyProjectAuthorizationRepository(),
                license_guard=licenses.guard,
                repository=SqlAlchemyDocumentReadRepository(),
            )
            document_read_router = create_document_read_router(
                sessions=sessions, documents=document_reads,
                origins=origins, cursors=document_cursors,
            )
            document_version_read_router = create_document_version_read_router(
                sessions=sessions, documents=document_reads,
                origins=origins, cursors=version_cursors,
            )
            document_parse_read_router = create_document_parse_read_router(
                sessions=sessions, documents=document_reads,
                origins=origins, cursors=parse_cursors,
            )
            document_downloads = PrepareDownloadService(
                reader=document_reads, storage=LocalFileStorage(settings.data_root),
                unit_of_work=runtime.unit_of_work, audit=audit,
            )
            document_download_router = create_document_download_router(
                sessions=sessions, downloads=document_downloads, origins=origins,
            )
            evidence_reads = EvidenceReadService(
                unit_of_work=runtime.unit_of_work,
                session_access=SqlAlchemyProjectReadAccess(),
                admin_access=SqlAlchemyDeploymentReadAccess(),
                project_facts=SqlAlchemyProjectAuthorizationRepository(),
                license_guard=licenses.guard,
                repository=SqlAlchemyEvidenceReadRepository(),
            )
            evidence_results_for_viewer = DocumentParseResultReadService(
                documents=document_downloads,
                metadata=SqlAlchemyParseResultReadRepository(),
                storage=LocalParseResultStorage(settings.data_root),
                unit_of_work=runtime.unit_of_work,
            )
            evidence_viewer_router = create_evidence_viewer_router(
                sessions=sessions, origins=origins,
                viewer=EvidenceViewerService(
                    evidence=evidence_reads, versions=document_reads,
                    document_proof=DocumentEvidenceProofService(
                        document_snapshots=document_downloads,
                    ),
                    node_proof=ParsedNodeEvidenceProofService(
                        results=evidence_results_for_viewer,
                    ),
                ),
            )
            try:
                evidence_cursors = create_windows_evidence_list_cursor_codec()
            except ProductionEvidenceCursorStartupError:
                evidence_cursors = None
            if evidence_cursors is not None:
                evidence_read_router = create_evidence_read_router(
                    sessions=sessions, origins=origins, cursors=evidence_cursors,
                    evidence=evidence_reads,
                )
            export_reads = AuditExportContentReader(
                unit_of_work=runtime.unit_of_work,
                project_access=SqlAlchemyProjectReadAccess(),
                deployment_access=SqlAlchemyDeploymentReadAccess(),
                projects=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                license_guard=licenses.guard,
                repository=SqlAlchemyAuditExportSubmitRepository(),
                results=SqlAlchemyAuditExportResults(), plans=SqlAlchemyAuditRenderPlans(),
                files=SqlAlchemyAuditExportFileMetadata(),
                completion=AuditExportJobCompletion(
                    queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()), leases=SqlAlchemyJobLeaseRepository(),
                ),
                audit=audit,
            )
            audit_export_result_router = create_audit_export_result_router(reads=export_reads, origins=origins)
            audit_export_download_router = create_audit_export_download_router(
                downloads=PrepareAuditExportContent(reader=export_reads,
                    storage=LocalAuditExportFileStorage(LocalFileStorage(settings.data_root))),
                origins=origins,
            )
            metadata = SecretMetadataService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyDeploymentReadAccess(),
                license_guard=licenses.guard,
                repository=SqlAlchemySecretMetadataRepository(),
            )
            secret_detail_router = create_secret_metadata_detail_router(
                sessions=sessions, metadata=metadata, origins=origins,
            )
            secret_list_router = create_secret_metadata_list_router(
                sessions=sessions, metadata=metadata, origins=origins, cursors=cursors,
            )
            ai_provider_read_router = create_ai_provider_read_router(
                sessions=sessions, origins=origins,
                providers=AIProviderMetadataService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyDeploymentReadAccess(),
                    license_guard=licenses.guard,
                    repository=SqlAlchemyAIProviderMetadataRepository(),
                    cursors=ai_provider_cursors,
                ),
            )
            project_reads = ProjectReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectReadAccess(),
                license_guard=licenses.guard,
                repository=SqlAlchemyProjectReadRepository(),
            )
            project_read_router = create_project_read_router(
                sessions=sessions, projects=project_reads, origins=origins,
            )
            workflow_read_router = create_workflow_read_router(
                sessions=sessions, origins=origins,
                workflows=WorkflowReadService(
                    unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectReadAccess(),
                    projects=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ), license_guard=licenses.guard, repository=SqlAlchemyWorkflowReadRepository(),
                ),
            )
            workflow_start_reader = SqlAlchemyWorkflowReadRepository()
            workflow_start_router = create_workflow_start_router(
                sessions=sessions, origins=origins,
                workflows=WorkflowStartService(
                    unit_of_work=runtime.unit_of_work,
                    sessions=SqlAlchemyProjectWriteAccess(),
                    projects=ProjectAuthorizationService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyProjectAuthorizationRepository(),
                    ),
                    license_guard=licenses.guard,
                    starter=SqlAlchemyWorkflowStartRepository(reader=workflow_start_reader),
                    reader=workflow_start_reader,
                    receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                ),
            )
            project_creates = ProjectCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectCreateAccess(),
                license_guard=licenses.guard,
                repository=SqlAlchemyProjectCreateRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
                workflow_initializer=WorkflowInitializationService(
                    repository=SqlAlchemyWorkflowInitializationRepository(), audit=audit,
                ),
            )
            project_create_router = create_project_create_router(
                sessions=sessions, projects=project_creates, origins=origins,
            )
            project_writes = ProjectWriteService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectWriteRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            project_patch_router = create_project_patch_router(
                sessions=sessions, writes=project_writes, origins=origins,
            )
            project_archive_router = create_project_archive_router(
                sessions=sessions, writes=project_writes, origins=origins,
            )
            member_reads = ProjectMemberReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectMemberNames(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectMemberReadRepository(),
            )
            project_member_read_router = create_project_member_read_router(
                sessions=sessions, members=member_reads,
                origins=origins, cursors=member_cursors,
            )
            member_creates = ProjectMemberCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectMemberCreateAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectMemberCreateRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            project_member_create_router = create_project_member_create_router(
                sessions=sessions, members=member_creates, origins=origins,
            )
            member_candidates = ProjectMemberCandidateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectMemberCandidateAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                membership=SqlAlchemyMemberCandidateMembership(),
                rate=SqlAlchemyLoginRateRepository(),
            )
            project_member_candidate_router = create_project_member_candidate_router(
                sessions=sessions, candidates=member_candidates, origins=origins,
            )
            member_patches = ProjectMemberPatchService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectMemberPatchAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectMemberPatchRepository(),
                audit=audit,
            )
            project_member_patch_router = create_project_member_patch_router(
                sessions=sessions, members=member_patches, origins=origins,
            )
            member_states = ProjectMemberStateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectMemberPatchAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectMemberStateRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            project_member_state_router = create_project_member_state_router(
                sessions=sessions, members=member_states, origins=origins,
            )
            department_reads = ProjectDepartmentReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectReadAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectDepartmentReadRepository(),
            )
            project_department_read_router = create_project_department_read_router(
                sessions=sessions, departments=department_reads,
                origins=origins, cursors=department_cursors,
            )
            department_creates = ProjectDepartmentCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectDepartmentCreateRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            project_department_create_router = create_project_department_create_router(
                sessions=sessions, departments=department_creates, origins=origins,
            )
            department_patches = ProjectDepartmentPatchService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectDepartmentPatchRepository(),
                audit=audit,
            )
            project_department_patch_router = create_project_department_patch_router(
                sessions=sessions, departments=department_patches, origins=origins,
            )
            department_deactivates = ProjectDepartmentDeactivateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectWriteAccess(),
                license_guard=licenses.guard,
                authorization=ProjectAuthorizationService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyProjectAuthorizationRepository(),
                ),
                repository=SqlAlchemyProjectDepartmentDeactivateRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
            )
            project_department_deactivate_router = create_project_department_deactivate_router(
                sessions=sessions, departments=department_deactivates, origins=origins,
            )
            if include_secret_write:
                evidence_downloads = PrepareDownloadService(
                    reader=document_reads, storage=LocalFileStorage(settings.data_root),
                    unit_of_work=runtime.unit_of_work, audit=audit,
                )
                evidence_results = DocumentParseResultReadService(
                    documents=evidence_downloads,
                    metadata=SqlAlchemyParseResultReadRepository(),
                    storage=LocalParseResultStorage(settings.data_root),
                    unit_of_work=runtime.unit_of_work,
                )

                def evidence_service(token: bytes, csrf: bytes) -> EvidenceCreateService:
                    return EvidenceCreateService(
                        unit_of_work=runtime.unit_of_work,
                        access=EvidenceCreateAccess(
                            session_token=token, csrf_token=csrf,
                            session_access=SqlAlchemyProjectWriteAccess(),
                            admin_access=SqlAlchemyLicenseImportAccess(),
                            project_facts=SqlAlchemyProjectAuthorizationRepository(),
                        ),
                        versions=document_reads,
                        document_proof=DocumentEvidenceProofService(
                            document_snapshots=evidence_downloads,
                        ),
                        node_proof=ParsedNodeEvidenceProofService(results=evidence_results),
                        repository=SqlAlchemyEvidenceCreateRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                    )

                evidence_create_router = create_evidence_create_router(
                    sessions=sessions, origins=origins, service_factory=evidence_service,
                )

                def eligibility_service(token: bytes, csrf: bytes) -> EvidenceEligibilityService:
                    return EvidenceEligibilityService(
                        unit_of_work=runtime.unit_of_work,
                        access=EvidenceEligibilityAccess(
                            session_token=token, csrf_token=csrf,
                            session_access=SqlAlchemyProjectWriteAccess(),
                            admin_access=SqlAlchemyLicenseImportAccess(),
                            project_facts=SqlAlchemyProjectAuthorizationRepository(),
                        ),
                        source_facts=document_reads,
                        repository=SqlAlchemyEvidenceEligibilityRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        license_guard=licenses.guard, audit=audit,
                    )

                evidence_eligibility_router = create_evidence_eligibility_router(
                    sessions=sessions, origins=origins,
                    service_factory=eligibility_service,
                )

                def eligibility_lookup_service(token: bytes, csrf: bytes) -> EvidenceEligibilityOperationLookupService:
                    return EvidenceEligibilityOperationLookupService(
                        unit_of_work=runtime.unit_of_work,
                        access=EvidenceEligibilityAccess(
                            session_token=token, csrf_token=csrf,
                            session_access=SqlAlchemyProjectWriteAccess(),
                            admin_access=SqlAlchemyLicenseImportAccess(),
                            project_facts=SqlAlchemyProjectAuthorizationRepository(),
                        ),
                        evidence=SqlAlchemyEvidenceEligibilityRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        license_guard=licenses.guard,
                    )

                evidence_eligibility_operation_lookup_router = create_evidence_eligibility_operation_lookup_router(
                    sessions=sessions, origins=origins,
                    service_factory=eligibility_lookup_service,
                )
                password_capacity = get_process_password_capacity(slots=settings.password_kdf_slots)
                password_reset_results = SqlAlchemyPasswordResetResults(verifier=verifier)
                password_reset_router = create_password_reset_router(sessions=sessions, origins=origins,
                    writes=PasswordResetService(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyPasswordResetAccess(verifier=verifier),
                        repository=SqlAlchemyPasswordResetRepository(), results=password_reset_results,
                        replay_verifier=PasswordResetReplayVerifier(source=password_reset_results), hasher=verifier,
                        audit=audit, receipts=SqlAlchemyIdempotencyReceipts(), license_guard=licenses.guard,
                        capacity=password_capacity))
                password_change_results = SqlAlchemyPasswordChangeResults(verifier=verifier)
                password_change_router = create_password_change_router(sessions=sessions,origins=origins,
                    writes=PasswordChangeService(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyPasswordChangeAccess(verifier=verifier),
                        repository=SqlAlchemyPasswordChangeRepository(),results=password_change_results,
                        replay_verifier=PasswordChangeReplayVerifier(source=password_change_results),hasher=verifier,
                        audit=audit,receipts=SqlAlchemyIdempotencyReceipts(),capacity=password_capacity))
                user_state_router = create_user_state_router(sessions=sessions, origins=origins,
                    writes=UserStateService(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyUserStateAccess(),repository=SqlAlchemyUserStateRepository(),
                        results=SqlAlchemyUserStateResultRepository(),audit=audit,
                        receipts=SqlAlchemyIdempotencyReceipts(),license_guard=licenses.guard))
                user_name_patch_router = create_user_name_patch_router(sessions=sessions, origins=origins,
                    writes=UserNamePatchService(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyUserCreateAccess(), license_guard=licenses.guard,
                        repository=SqlAlchemyUserNamePatchRepository(), audit=audit))
                user_create_results = SqlAlchemyUserCreateResultRepository(verifier=verifier)
                user_create_router = create_user_create_router(sessions=sessions,origins=origins,
                    writes=ManagedUserCreateService(unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyUserCreateAccess(),license_guard=licenses.guard,
                        users=SqlAlchemyUserRepository(),results=user_create_results,
                        replay_verifier=UserCreateReplayVerifier(source=user_create_results),hasher=verifier,
                        audit=audit,receipts=SqlAlchemyIdempotencyReceipts()))
                job_retry_router = create_job_retry_router(
                    sessions=sessions,origins=origins,
                    retries=JobRetryRequests(reads=job_reads,sessions=sessions,license_guard=licenses.guard,
                        owners={('audit','AUDIT_EXPORT'):AuditJobRetryOwner(requests=AuditUserRetryService(
                            unit_of_work=runtime.unit_of_work,repository=SqlAlchemyAuditExportSubmitRepository(),
                            authorization=AuditExportSubmitAuthorization(
                                project_access=SqlAlchemyProjectWriteAccess(),deployment_access=SqlAlchemyLicenseImportAccess(),
                                projects=retry_projects,license_guard=licenses.guard),
                            sources=retry_sources,generations=SqlAlchemyAuditRetryGenerations(),
                            receipts=SqlAlchemyIdempotencyReceipts(),queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),
                            audit=audit))}))
                job_cancel_router = create_project_job_cancel_router(
                    sessions=sessions,origins=origins,
                    cancellations=ProjectJobCancellation(
                        unit_of_work=runtime.unit_of_work,repository=SqlAlchemyJobReadRepository(),
                        sessions=sessions,license_guard=licenses.guard,
                        owners={('audit','AUDIT_EXPORT'):AuditJobCancelOwner(
                            requests=AuditExportCancelRequestService(
                                unit_of_work=runtime.unit_of_work,repository=SqlAlchemyAuditExportSubmitRepository(),
                                authorization=AuditExportCancelAuthorization(
                                    project_access=SqlAlchemyProjectWriteAccess(),deployment_access=SqlAlchemyLicenseImportAccess(),
                                    projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,
                                        repository=SqlAlchemyProjectAuthorizationRepository()),license_guard=licenses.guard),
                                cancellations=AuditExportCancellation(repository=SqlAlchemyAuditExportCancellationRepository()),
                                receipts=SqlAlchemyIdempotencyReceipts(),sources=SqlAlchemyAuditExportCancelSources(),audit=audit,
                            )),
                            ('document','DOCUMENT_PARSE'):DocumentParseJobCancelOwner(
                                unit_of_work=runtime.unit_of_work,
                                queue=ParseJobQueue(SqlAlchemyParseJobQueueRepository()),
                                sources=DocumentParseSourceReader(
                                    repository=SqlAlchemyDocumentParseSources(),
                                    audit_sources=UploadCommitAuditSources(
                                        repository=SqlAlchemyUploadCommitAuditSources())),
                                project_access=SqlAlchemyProjectWriteAccess(),
                                projects=ProjectAuthorizationService(
                                    unit_of_work=runtime.unit_of_work,
                                    repository=SqlAlchemyProjectAuthorizationRepository()),
                                license_guard=licenses.guard,
                                cancellations=SqlAlchemyParseCancellationRepository(),
                                receipts=SqlAlchemyIdempotencyReceipts(),
                                audit_sources=SqlAlchemyParseCancelAuditSources(), audit=audit,
                            )},
                    ),
                )
                audit_export_submit_router = create_audit_export_submit_router(
                    sessions=sessions,origins=origins,
                    exports=AuditExportSubmitService(
                        unit_of_work=runtime.unit_of_work,
                        authorization=AuditExportSubmitAuthorization(
                            project_access=SqlAlchemyProjectWriteAccess(),deployment_access=SqlAlchemyLicenseImportAccess(),
                            projects=ProjectAuthorizationService(unit_of_work=runtime.unit_of_work,
                                repository=SqlAlchemyProjectAuthorizationRepository()),license_guard=licenses.guard),
                        repository=SqlAlchemyAuditExportSubmitRepository(),receipts=SqlAlchemyIdempotencyReceipts(),
                        queue=AuditExportJobQueue(SqlAlchemyAuditExportJobQueueRepository()),audit=audit,
                    ),
                )
                from plm_assistant.entrypoints.windows_secret_write import (
                    create_windows_secret_write_service,
                )
                writes = create_windows_secret_write_service(
                    runtime, license_guard=licenses.guard,
                )
                ai_provider_create_router = create_ai_provider_create_router(
                    sessions=sessions, origins=origins,
                    providers=AIProviderCreateService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyLicenseImportAccess(),
                        license_guard=licenses.guard,
                        secret_proof=SqlAlchemyAIProviderSecretProof(),
                        repository=SqlAlchemyAIProviderCreateRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        audit=audit,
                    ),
                )
                ai_provider_patch_router = create_ai_provider_patch_router(
                    sessions=sessions, origins=origins,
                    providers=AIProviderAppendService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyLicenseImportAccess(),
                        license_guard=licenses.guard,
                        secret_proof=SqlAlchemyAIProviderSecretProof(),
                        repository=SqlAlchemyAIProviderAppendRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        audit=audit,
                    ),
                )
                secret_create_router = create_secret_create_router(
                    sessions=sessions, writes=writes, origins=origins,
                )
                secret_rotate_router = create_secret_rotate_router(
                    sessions=sessions, writes=writes, origins=origins,
                )
                secret_disable_router = create_secret_disable_router(
                    sessions=sessions, writes=writes, origins=origins,
                )
                upload_issuer = create_windows_document_upload_token_issuer()
                upload_repository = SqlAlchemyUploadIntentRepository()

                def upload_service(token: bytes, csrf: bytes) -> CreateUploadIntentService:
                    return CreateUploadIntentService(
                        unit_of_work=runtime.unit_of_work,
                        access=DocumentUploadAccess(
                            session_token=token, csrf_token=csrf,
                            session_access=SqlAlchemyProjectWriteAccess(),
                            admin_access=SqlAlchemyLicenseImportAccess(),
                            project_facts=SqlAlchemyProjectAuthorizationRepository(),
                            upload_owner=upload_repository,
                        ),
                        repository=upload_repository,
                        receipts=SqlAlchemyIdempotencyReceipts(), audit=audit,
                        token_issuer=upload_issuer,
                    )

                document_upload_create_router = create_document_upload_create_router(
                    sessions=sessions, origins=origins, license_guard=licenses.guard,
                    service_factory=upload_service,
                )
                upload_storage = LocalFileStorage(settings.data_root)
                upload_operation_gate = LocalUploadOperationGate(settings.data_root)
                upload_spool = ValidatedContentSpool(
                    storage=upload_storage, max_bytes=100_000_000,
                    allowed_extensions=frozenset({
                        ".pdf", ".docx", ".xlsx", ".pptx", ".png", ".jpg", ".jpeg",
                        ".tif", ".tiff", ".txt", ".csv",
                    }),
                )

                def content_service(token: bytes, csrf: bytes) -> ReceiveUploadContentService:
                    return ReceiveUploadContentService(
                        unit_of_work=runtime.unit_of_work,
                        access=DocumentUploadAccess(
                            session_token=token, csrf_token=csrf,
                            session_access=SqlAlchemyProjectWriteAccess(),
                            admin_access=SqlAlchemyLicenseImportAccess(),
                            project_facts=SqlAlchemyProjectAuthorizationRepository(),
                            upload_owner=upload_repository,
                        ),
                        repository=SqlAlchemyUploadContentRepository(), audit=audit,
                        spool=upload_spool, storage=upload_storage,
                        operation_gate=upload_operation_gate,
                        license_guard=licenses.guard,
                    )

                document_upload_content_router = create_document_upload_content_router(
                    sessions=sessions, origins=origins, service_factory=content_service,
                )

                def finalize_access(token: bytes, csrf: bytes) -> DocumentUploadAccess:
                    return DocumentUploadAccess(
                        session_token=token, csrf_token=csrf,
                        session_access=SqlAlchemyProjectWriteAccess(),
                        admin_access=SqlAlchemyLicenseImportAccess(),
                        project_facts=SqlAlchemyProjectAuthorizationRepository(),
                        upload_owner=upload_repository,
                    )

                def commit_service(token: bytes, csrf: bytes) -> CommitUploadService:
                    return CommitUploadService(
                        unit_of_work=runtime.unit_of_work,
                        access=finalize_access(token, csrf),
                        repository=SqlAlchemyUploadCommitRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        jobs=ParseJobQueue(SqlAlchemyParseJobQueueRepository()),
                        audit=audit, storage=upload_storage,
                        license_guard=licenses.guard,
                        operation_gate=upload_operation_gate,
                    )

                def abort_service(token: bytes, csrf: bytes) -> AbortUploadService:
                    return AbortUploadService(
                        unit_of_work=runtime.unit_of_work,
                        access=finalize_access(token, csrf),
                        repository=SqlAlchemyUploadAbortRepository(),
                        receipts=SqlAlchemyIdempotencyReceipts(),
                        audit=audit, license_guard=licenses.guard,
                        operation_gate=upload_operation_gate,
                    )

                document_upload_finalize_router = create_document_upload_finalize_router(
                    sessions=sessions, origins=origins,
                    commit_factory=commit_service, abort_factory=abort_service,
                )
        def shutdown() -> None:
            try:
                maintenance_engine.dispose()
            finally:
                runtime.dispose()

        return create_app(
            readiness_checks=(runtime.is_ready,),
            login_router=router,
            session_router=session_router,
            session_renew_router=renew_router,
            session_logout_router=logout_router,
            secret_metadata_router=secret_detail_router,
            secret_metadata_list_router=secret_list_router,
            secret_create_router=secret_create_router,
            secret_rotate_router=secret_rotate_router,
            secret_disable_router=secret_disable_router,
            ai_provider_read_router=ai_provider_read_router,
            ai_provider_create_router=ai_provider_create_router,
            ai_provider_patch_router=ai_provider_patch_router,
            project_read_router=project_read_router,
            workflow_read_router=workflow_read_router,
            workflow_start_router=workflow_start_router,
            audit_read_router=audit_read_router,
            audit_export_result_router=audit_export_result_router,
            audit_export_download_router=audit_export_download_router,
            audit_export_submit_router=audit_export_submit_router,
            job_detail_router=job_detail_router,
            user_detail_router=user_detail_router,
            user_list_router=user_list_router,
            user_create_router=user_create_router,
            user_name_patch_router=user_name_patch_router,
            user_state_router=user_state_router,
            password_change_router=password_change_router,
            password_reset_router=password_reset_router,
            job_list_router=job_list_router,
            job_cancel_router=job_cancel_router,
            job_retry_router=job_retry_router,
            project_create_router=project_create_router,
            project_patch_router=project_patch_router,
            project_archive_router=project_archive_router,
            project_member_read_router=project_member_read_router,
            project_member_create_router=project_member_create_router,
            project_member_candidate_router=project_member_candidate_router,
            project_member_patch_router=project_member_patch_router,
            project_member_state_router=project_member_state_router,
            project_department_read_router=project_department_read_router,
            project_department_create_router=project_department_create_router,
            project_department_patch_router=project_department_patch_router,
            project_department_deactivate_router=project_department_deactivate_router,
            document_upload_create_router=document_upload_create_router,
            document_upload_content_router=document_upload_content_router,
            document_upload_finalize_router=document_upload_finalize_router,
            document_read_router=document_read_router,
            document_version_read_router=document_version_read_router,
            document_parse_read_router=document_parse_read_router,
            document_download_router=document_download_router,
            evidence_create_router=evidence_create_router,
            evidence_read_router=evidence_read_router,
            evidence_viewer_router=evidence_viewer_router,
            evidence_eligibility_router=evidence_eligibility_router,
            evidence_eligibility_operation_lookup_router=evidence_eligibility_operation_lookup_router,
            maintenance_admission=maintenance_admission,
            shutdown_callback=shutdown,
        )
    except Exception:
        if maintenance_engine is not None:
            maintenance_engine.dispose()
        runtime.dispose()
        raise ProductionLoginStartupError() from None
