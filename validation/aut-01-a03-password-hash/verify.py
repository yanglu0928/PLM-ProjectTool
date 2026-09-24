"""Disposable PostgreSQL 18 round-trip for the production scrypt profile."""

from __future__ import annotations

import time
import uuid

from alembic import command
import psycopg
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.user_commands import CreateUser, UserCommandService
from plm_assistant.modules.auth.infrastructure.scrypt_password import (
    ALGORITHM_ID, PARAMETERS, ScryptPasswordHasher,
)
from plm_assistant.modules.auth.infrastructure.user_repository import SqlAlchemyUserRepository
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def url(name: str) -> URL:
    return URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)


def conn(name: str) -> psycopg.Connection:
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class AllowedAccess:
    def can_create_user(self, transaction, actor_id):
        return True  # disposable test database only; not a production authorization adapter


def main() -> None:
    name = f"aut01a03_{uuid.uuid4().hex[:12]}"
    with conn("postgres") as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            raise RuntimeError("probe database already exists")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            command.upgrade(create_migration_config(url(name)), "head")
            runtime = create_database_runtime(url(name))
            try:
                hasher = ScryptPasswordHasher()
                service = UserCommandService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyUserRepository(), access=AllowedAccess(),
                    hasher=hasher, audit=AuditService(SqlAlchemyAuditRepository()),
                    accepted_algorithms=frozenset({ALGORITHM_ID}),
                )
                request = CreateUser(uuid.uuid4(), uuid.uuid4(), "Synthetic Account", bytearray(b"synthetic-only-password"))
                started = time.perf_counter()
                result = service.create_user(request)
                elapsed_ms = (time.perf_counter() - started) * 1000
                assert request.password == bytearray(len(request.password))
                with conn(name) as db:
                    encoded, algorithm_id, parameter_set = db.execute(
                        "SELECT password_hash,algorithm_id,parameter_set FROM plm.auth_password_credentials WHERE user_id=%s",
                        (result.user_id,),
                    ).fetchone()
                    assert algorithm_id == ALGORITHM_ID and parameter_set == PARAMETERS
                    assert "synthetic-only-password" not in encoded
                    assert db.execute("SELECT count(*) FROM plm.aud_events").fetchone()[0] == 1
                correct = bytearray(b"synthetic-only-password")
                wrong = bytearray(b"incorrect-password")
                try:
                    assert hasher.verify_password(
                        memoryview(correct), password_hash=encoded,
                        algorithm_id=algorithm_id, parameter_set=parameter_set,
                    )
                    assert not hasher.verify_password(
                        memoryview(wrong), password_hash=encoded,
                        algorithm_id=algorithm_id, parameter_set=parameter_set,
                    )
                    assert not hasher.verify_password(
                        memoryview(correct), password_hash=encoded,
                        algorithm_id=algorithm_id, parameter_set={**parameter_set, "n": 1 << 20},
                    )
                finally:
                    correct[:] = b"\x00" * len(correct)
                    wrong[:] = b"\x00" * len(wrong)
            finally:
                runtime.dispose()
            print(f"PASS: scrypt stored round-trip, correct/wrong verification, fixed profile, Audit, buffer cleanup; local create elapsed {elapsed_ms:.0f} ms (not a release benchmark)")
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
