"""Disposable PostgreSQL 18 verification of one-time trusted-time initialization."""

from __future__ import annotations

import hashlib
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.license.application.trusted_time_initialization import (
    InitializeTrustedTime, TrustedTimeInitializationError,
    TrustedTimeInitializationService,
)
from plm_assistant.modules.license.infrastructure.trusted_time_initialization_repository import (
    SqlAlchemyTrustedTimeInitializationRepository,
)
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


class FailedAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit failure")


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


def main():
    name = "lic03a03_" + uuid.uuid4().hex[:12]
    token, csrf = b"s" * 32, b"c" * 32
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            with connect(name) as db:
                user_id = db.execute("INSERT INTO plm.auth_users(username_display,username_normalized,deployment_role) VALUES ('Synthetic Time Admin','synthetic time admin','DEPLOYMENT_ADMIN') RETURNING user_id").fetchone()[0]
                credential_id = db.execute("INSERT INTO plm.auth_password_credentials(user_id,credential_version,password_hash,algorithm_id,parameter_set) VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) RETURNING password_credential_id", (user_id,)).fetchone()[0]
                db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s", (credential_id, user_id))
                db.execute("INSERT INTO plm.auth_sessions(session_token_digest,csrf_digest,user_id,credential_version,idle_expires_at,absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+interval '15 minutes',statement_timestamp()+interval '1 hour')", (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), user_id))
            runtime = create_database_runtime(url)
            try:
                def service(audit):
                    return TrustedTimeInitializationService(
                        unit_of_work=runtime.unit_of_work,
                        access=SqlAlchemyLicenseImportAccess(),
                        repository=SqlAlchemyTrustedTimeInitializationRepository(),
                        audit=audit, clock=lambda: datetime.now(timezone.utc),
                    )
                def request(csrf_value=csrf):
                    return InitializeTrustedTime(token, csrf_value, uuid.uuid4())
                real_audit = AuditService(SqlAlchemyAuditRepository())
                try:
                    service(real_audit).initialize_once(request(b"x" * 32))
                except TrustedTimeInitializationError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("invalid CSRF allowed")
                try:
                    service(FailedAudit()).initialize_once(request())
                except TrustedTimeInitializationError as exc:
                    assert exc.code == "TRUST_STATE_INVALID"
                else:
                    raise AssertionError("audit failure allowed")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.lic_trusted_time_states").fetchone()[0] == 0

                def create(_):
                    try:
                        return ("CREATED", service(real_audit).initialize_once(request()))
                    except TrustedTimeInitializationError as exc:
                        return (exc.code, None)
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(create, range(2)))
                assert sorted(result[0] for result in results) == ["CREATED", "TRUST_STATE_CONFLICT"], results
                with connect(name) as db:
                    row = db.execute("SELECT last_successful_time,state_version,integrity_metadata,last_success_event_ref FROM plm.lic_trusted_time_states").fetchone()
                    assert row == (None, 0, None, None), row
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='LICENSE_TRUSTED_TIME_INITIALIZED'").fetchone()[0] == 1
                print("PASS: PostgreSQL first initialization, CSRF denial, audit rollback and concurrent no-reset")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
