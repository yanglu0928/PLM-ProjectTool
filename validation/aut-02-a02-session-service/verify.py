"""Disposable PostgreSQL 18 integration check; synthetic identity only."""

from __future__ import annotations

import hashlib
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


def conn(name: str):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class AllowSynthetic:
    def can_create_user(self, transaction, actor_id):
        return True

    def can_issue(self, transaction, user_id, credential_version, proof):
        return proof is True


class FailAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit failure")


def main() -> None:
    name = f"aut02a02_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                audit = AuditService(SqlAlchemyAuditRepository())
                create = UserCommandService(
                    unit_of_work=runtime.unit_of_work, repository=SqlAlchemyUserRepository(),
                    access=AllowSynthetic(), hasher=ScryptPasswordHasher(), audit=audit,
                    accepted_algorithms=frozenset({ALGORITHM_ID}),
                )
                user = create.create_user(CreateUser(uuid.uuid4(), uuid.uuid4(), "Synthetic Session User", bytearray(b"synthetic-session-password")))
                service = SessionService(unit_of_work=runtime.unit_of_work,
                                         repository=SqlAlchemySessionRepository(),
                                         issue_access=AllowSynthetic(), audit=audit)
                trace = uuid.uuid4()
                issued = service.issue(user_id=user.user_id, trace_id=trace, proof=True)
                with conn(name) as db:
                    stored = db.execute("SELECT session_token_digest,csrf_digest FROM plm.auth_sessions WHERE session_id=%s", (issued.session_id,)).fetchone()
                    assert stored == (hashlib.sha256(issued.token).digest(), hashlib.sha256(issued.csrf_token).digest())
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_ISSUED'").fetchone()[0] == 1
                assert service.validate(issued.token).user_id == user.user_id
                try:
                    service.revoke(token=issued.token, csrf_token=b"x" * 32, trace_id=trace)
                    raise AssertionError("wrong CSRF was accepted")
                except SessionError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                failed = SessionService(unit_of_work=runtime.unit_of_work,
                                        repository=SqlAlchemySessionRepository(),
                                        issue_access=AllowSynthetic(), audit=FailAudit())
                try:
                    failed.revoke(token=issued.token, csrf_token=issued.csrf_token, trace_id=trace)
                    raise AssertionError("audit failure was accepted")
                except RuntimeError as exc:
                    assert str(exc) == "synthetic audit failure"
                assert service.validate(issued.token).user_id == user.user_id
                assert service.revoke(token=issued.token, csrf_token=issued.csrf_token, trace_id=trace)
                try:
                    service.validate(issued.token)
                    raise AssertionError("revoked session was accepted")
                except SessionError as exc:
                    assert exc.code == "AUTH_SESSION_EXPIRED"
                second = service.issue(user_id=user.user_id, trace_id=trace, proof=True)
                with conn(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", (user.user_id,))
                try:
                    service.validate(second.token)
                    raise AssertionError("disabled user session was accepted")
                except SessionError as exc:
                    assert exc.code == "AUTH_SESSION_EXPIRED"
                print("PASS: digest-only issue, validation, CSRF, rollback, revocation and user disable")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
