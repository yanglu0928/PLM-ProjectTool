"""Fail-closed Windows production composition for the frozen login endpoint."""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from sqlalchemy import text

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_secret_list_cursor import create_windows_secret_list_cursor_codec
from plm_assistant.entrypoints.windows_project_member_cursor import create_windows_project_member_cursor_codec
from plm_assistant.entrypoints.windows_project_department_cursor import create_windows_project_department_cursor_codec
from plm_assistant.entrypoints.windows_document_upload_token import create_windows_document_upload_token_issuer
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
from plm_assistant.modules.project.infrastructure.create_repository import SqlAlchemyProjectCreateRepository
from plm_assistant.modules.project.api.patch_project import create_project_patch_router
from plm_assistant.modules.project.api.archive_project import create_project_archive_router
from plm_assistant.modules.project.api.read_members import create_project_member_read_router
from plm_assistant.modules.project.api.create_member import create_project_member_create_router
from plm_assistant.modules.project.api.patch_member import create_project_member_patch_router
from plm_assistant.modules.project.api.change_member_state import create_project_member_state_router
from plm_assistant.modules.project.api.read_departments import create_project_department_read_router
from plm_assistant.modules.project.api.create_department import create_project_department_create_router
from plm_assistant.modules.project.api.patch_department import create_project_department_patch_router
from plm_assistant.modules.project.api.deactivate_department import create_project_department_deactivate_router
from plm_assistant.modules.project.application.read_members import ProjectMemberReadService
from plm_assistant.modules.project.application.create_member import ProjectMemberCreateService
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
from plm_assistant.modules.auth.infrastructure.project_member_patch_access import SqlAlchemyProjectMemberPatchAccess
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.write_project import ProjectWriteService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.write_repository import SqlAlchemyProjectWriteRepository
from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.document.api.create_upload import create_document_upload_create_router
from plm_assistant.modules.document.application.create_upload_intent import CreateUploadIntentService
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccess
from plm_assistant.modules.document.infrastructure.upload_intent_repository import SqlAlchemyUploadIntentRepository
from plm_assistant.modules.document.api.upload_content import create_document_upload_content_router
from plm_assistant.modules.document.application.receive_upload_content import ReceiveUploadContentService
from plm_assistant.modules.document.infrastructure.upload_content_repository import SqlAlchemyUploadContentRepository
from plm_assistant.modules.document.infrastructure.content_spool import ValidatedContentSpool
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage


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
    try:
        if not runtime.is_ready() or not _schema_current(runtime):
            raise ProductionLoginStartupError()
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
        project_read_router = None
        project_create_router = None
        project_patch_router = None
        project_archive_router = None
        project_member_read_router = None
        project_member_create_router = None
        project_member_patch_router = None
        project_member_state_router = None
        project_department_read_router = None
        project_department_create_router = None
        project_department_patch_router = None
        project_department_deactivate_router = None
        document_upload_create_router = None
        document_upload_content_router = None
        if include_secret_read:
            from plm_assistant.entrypoints.windows_license_runtime import (
                create_windows_license_services,
            )
            licenses = create_windows_license_services(runtime, settings)
            cursors = create_windows_secret_list_cursor_codec()
            member_cursors = create_windows_project_member_cursor_codec()
            department_cursors = create_windows_project_department_cursor_codec()
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
            project_reads = ProjectReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectReadAccess(),
                license_guard=licenses.guard,
                repository=SqlAlchemyProjectReadRepository(),
            )
            project_read_router = create_project_read_router(
                sessions=sessions, projects=project_reads, origins=origins,
            )
            project_creates = ProjectCreateService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectCreateAccess(),
                license_guard=licenses.guard,
                repository=SqlAlchemyProjectCreateRepository(),
                audit=audit,
                receipts=SqlAlchemyIdempotencyReceipts(),
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
                from plm_assistant.entrypoints.windows_secret_write import (
                    create_windows_secret_write_service,
                )
                writes = create_windows_secret_write_service(
                    runtime, license_guard=licenses.guard,
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
                        license_guard=licenses.guard,
                    )

                document_upload_content_router = create_document_upload_content_router(
                    sessions=sessions, origins=origins, service_factory=content_service,
                )
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
            project_read_router=project_read_router,
            project_create_router=project_create_router,
            project_patch_router=project_patch_router,
            project_archive_router=project_archive_router,
            project_member_read_router=project_member_read_router,
            project_member_create_router=project_member_create_router,
            project_member_patch_router=project_member_patch_router,
            project_member_state_router=project_member_state_router,
            project_department_read_router=project_department_read_router,
            project_department_create_router=project_department_create_router,
            project_department_patch_router=project_department_patch_router,
            project_department_deactivate_router=project_department_deactivate_router,
            document_upload_create_router=document_upload_create_router,
            document_upload_content_router=document_upload_content_router,
            shutdown_callback=runtime.dispose,
        )
    except Exception:
        runtime.dispose()
        raise ProductionLoginStartupError() from None
