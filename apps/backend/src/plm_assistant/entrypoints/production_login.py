"""Fail-closed Windows production composition for the frozen login endpoint."""

from __future__ import annotations

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import FastAPI
from sqlalchemy import text

from plm_assistant.entrypoints.api import create_app
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
from plm_assistant.modules.platform.infrastructure.bootstrap_config import BootstrapSettings
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime, create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import MIGRATION_PACKAGE
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.platform.infrastructure.windows_database_credential import (
    DEFAULT_TARGET,
    read_database_url,
)
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects


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
        return create_app(
            readiness_checks=(runtime.is_ready,),
            login_router=router,
            session_router=session_router,
            session_renew_router=renew_router,
            session_logout_router=logout_router,
            shutdown_callback=runtime.dispose,
        )
    except Exception:
        runtime.dispose()
        raise ProductionLoginStartupError() from None
