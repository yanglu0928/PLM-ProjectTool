"""Isolated PostgreSQL 18 acceptance for internal User creation and Audit atomicity."""

from __future__ import annotations

import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.user_commands import (
    CreateUser, PasswordHashResult, UserCommandError, UserCommandService,
)
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"
ACTOR_ID = uuid.uuid4()


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class Access:
    def __init__(self, allowed: bool) -> None:
        self.allowed = allowed

    def can_create_user(self, transaction, actor_id):
        return self.allowed and actor_id == ACTOR_ID


class SyntheticHasher:
    """Test double only; not a password hashing implementation."""

    def hash_password(self, password):
        assert len(password) > 0
        return PasswordHashResult("$synthetic$not-for-login", "TEST_ONLY", {})


class BrokenAudit:
    def append(self, transaction, event):
        raise RuntimeError("synthetic audit outage")


def command_for(name: str) -> CreateUser:
    return CreateUser(ACTOR_ID, uuid.uuid4(), name, bytearray(b"synthetic-passphrase"))


def main() -> None:
    name = f"aut01a02_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            raise RuntimeError("probe database already exists")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url(name)), "head")
            runtime = create_database_runtime(url(name))
            try:
                def service(*, access=True, audit=None):
                    return UserCommandService(
                        unit_of_work=runtime.unit_of_work,
                        repository=SqlAlchemyUserRepository(),
                        access=Access(access), hasher=SyntheticHasher(),
                        audit=audit or AuditService(SqlAlchemyAuditRepository()),
                        accepted_algorithms=frozenset({"TEST_ONLY"}),
                    )

                first = command_for("  Stra\u00dfe  ")
                result = service().create_user(first)
                assert first.password == bytearray(len(first.password))
                assert result.credential_version == 1 and result.lock_version == 1
                with conn(name) as db:
                    row = db.execute("SELECT username_display,username_normalized,state,credential_version FROM plm.auth_users WHERE user_id=%s", (result.user_id,)).fetchone()
                    assert row == ("Stra\u00dfe", "strasse", "ENABLED", 1)
                    credential = db.execute("SELECT password_hash,algorithm_id,parameter_set FROM plm.auth_password_credentials WHERE user_id=%s", (result.user_id,)).fetchone()
                    assert credential[0] == "$synthetic$not-for-login" and credential[1] == "TEST_ONLY"
                    assert db.execute("SELECT action,outcome,target_object_id FROM plm.aud_events").fetchone() == ("USER_CREATED", "SUCCESS", result.user_id)

                duplicate = command_for("STRASSE")
                try:
                    service().create_user(duplicate)
                except UserCommandError as exc:
                    assert exc.code == "AUTH_USERNAME_CONFLICT"
                else:
                    raise AssertionError("canonical duplicate accepted")
                assert duplicate.password == bytearray(len(duplicate.password))

                denied = command_for("denied")
                try:
                    service(access=False).create_user(denied)
                except UserCommandError as exc:
                    assert exc.code == "AUTH_ACCESS_DENIED"
                else:
                    raise AssertionError("unauthorized create accepted")
                assert denied.password == bytearray(len(denied.password))

                failed = command_for("audit-failure")
                try:
                    service(audit=BrokenAudit()).create_user(failed)
                except RuntimeError as exc:
                    assert str(exc) == "synthetic audit outage"
                else:
                    raise AssertionError("audit failure accepted")
                assert failed.password == bytearray(len(failed.password))
                with conn(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.auth_password_credentials").fetchone()[0] == 1
                    assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
            finally:
                runtime.dispose()
            print("PASS: canonical create, duplicate/denied failure, same-transaction Audit rollback, password buffer cleanup, no raw password persistence")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
