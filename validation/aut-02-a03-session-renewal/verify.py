"""Disposable PostgreSQL 18 atomic renewal check; synthetic records only."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.auth.application.user_commands import CreateUser, UserCommandService
from plm_assistant.modules.auth.infrastructure.scrypt_password import ALGORITHM_ID, ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def conn(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class SyntheticAccess:
    def can_create_user(self, transaction, actor_id):
        return True

    def can_issue(self, transaction, user_id, credential_version, proof):
        return proof is True


class FailAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def main():
    name = f"aut02a03_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                audit = AuditService(SqlAlchemyAuditRepository())
                user = UserCommandService(
                    unit_of_work=runtime.unit_of_work, repository=SqlAlchemyUserRepository(),
                    access=SyntheticAccess(), hasher=ScryptPasswordHasher(), audit=audit,
                    accepted_algorithms=frozenset({ALGORITHM_ID}),
                ).create_user(CreateUser(uuid.uuid4(), uuid.uuid4(), "Synthetic Renew User", bytearray(b"synthetic-renew-password")))
                service = SessionService(unit_of_work=runtime.unit_of_work,
                                         repository=SqlAlchemySessionRepository(),
                                         issue_access=SyntheticAccess(), audit=audit)
                trace = uuid.uuid4()
                old = service.issue(user_id=user.user_id, trace_id=trace, proof=True)
                try:
                    service.renew(token=old.token, csrf_token=b"z" * 32, trace_id=trace)
                    raise AssertionError("wrong CSRF accepted")
                except SessionError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                failed = SessionService(unit_of_work=runtime.unit_of_work,
                                        repository=SqlAlchemySessionRepository(),
                                        issue_access=SyntheticAccess(), audit=FailAudit())
                try:
                    failed.renew(token=old.token, csrf_token=old.csrf_token, trace_id=trace)
                    raise AssertionError("failed Audit accepted")
                except RuntimeError as exc:
                    assert str(exc) == "synthetic audit failure"
                assert service.validate(old.token).user_id == user.user_id
                with conn(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 1
                new = service.renew(token=old.token, csrf_token=old.csrf_token, trace_id=trace)
                assert old.token != new.token and old.csrf_token != new.csrf_token
                assert new.absolute_expires_at == old.absolute_expires_at
                assert service.validate(new.token, csrf_token=new.csrf_token, require_csrf=True).user_id == user.user_id
                try:
                    service.validate(old.token)
                    raise AssertionError("old token still valid")
                except SessionError as exc:
                    assert exc.code == "AUTH_SESSION_EXPIRED"
                with conn(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 2
                    assert db.execute("SELECT revoke_reason FROM plm.auth_sessions WHERE session_id=%s", (old.session_id,)).fetchone()[0] == "RENEWED"
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_RENEWED'").fetchone()[0] == 1
                print("PASS: renewal rotates both secrets, retires old session, rejects CSRF and rolls back Audit failure")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
