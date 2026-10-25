"""Disposable PostgreSQL 18 proof check; synthetic password and user only."""

from __future__ import annotations

import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.session_service import PasswordIssueProof, SessionError, SessionService
from plm_assistant.modules.auth.application.user_commands import CreateUser, UserCommandService
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ALGORITHM_ID, ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def conn(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class CreateSyntheticUser:
    def can_create_user(self, transaction, actor_id):
        return True


def main():
    name = f"aut02a05_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                audit = AuditService(SqlAlchemyAuditRepository())
                hasher = ScryptPasswordHasher()
                user = UserCommandService(
                    unit_of_work=runtime.unit_of_work, repository=SqlAlchemyUserRepository(),
                    access=CreateSyntheticUser(), hasher=hasher, audit=audit,
                    accepted_algorithms=frozenset({ALGORITHM_ID}),
                ).create_user(CreateUser(uuid.uuid4(), uuid.uuid4(), "Synthetic Password Proof User", bytearray(b"synthetic-proof-password")))
                service = SessionService(unit_of_work=runtime.unit_of_work,
                                         repository=SqlAlchemySessionRepository(),
                                         issue_access=SqlAlchemyPasswordIssueAccess(hasher), audit=audit)
                trace = uuid.uuid4()
                wrong = PasswordIssueProof(bytearray(b"incorrect-password"))
                try:
                    service.issue(user_id=user.user_id, trace_id=trace, proof=wrong)
                    raise AssertionError("wrong password accepted")
                except SessionError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                assert wrong.password == bytearray(len(wrong.password))
                with conn(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 0
                correct = PasswordIssueProof(bytearray(b"synthetic-proof-password"))
                issued = service.issue(user_id=user.user_id, trace_id=trace, proof=correct)
                assert correct.password == bytearray(len(correct.password))
                assert service.validate(issued.token).user_id == user.user_id
                with conn(name) as db:
                    db.execute("UPDATE plm.auth_users SET state='DISABLED',lock_version=lock_version+1 WHERE user_id=%s", (user.user_id,))
                disabled = PasswordIssueProof(bytearray(b"synthetic-proof-password"))
                try:
                    service.issue(user_id=user.user_id, trace_id=trace, proof=disabled)
                    raise AssertionError("disabled user accepted")
                except SessionError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                assert disabled.password == bytearray(len(disabled.password))
                with conn(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_sessions").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events WHERE action='SESSION_ISSUED'").fetchone()[0] == 1
                print("PASS: real password proof, wrong/disabled refusal, input erase and no failed Session write")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
