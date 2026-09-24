"""Disposable PostgreSQL proof of one-time administrator creation."""

from __future__ import annotations

import concurrent.futures
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy.engine import URL

from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.initial_admin import (
    InitializeAdmin, InitialAdminError, InitialAdminService,
)
from plm_assistant.modules.auth.infrastructure.initial_admin import SqlAlchemyInitialAdminRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


HOST, PORT, USER = "127.0.0.1", 55432, "poc_admin"


def connect(name):
    return psycopg.connect(host=HOST, port=PORT, user=USER, dbname=name, autocommit=True)


class FailingAudit:
    def append(self, *_):
        raise RuntimeError("synthetic audit failure")


def make_service(runtime, audit):
    return InitialAdminService(unit_of_work=runtime.unit_of_work,
                               repository=SqlAlchemyInitialAdminRepository(),
                               hasher=ScryptPasswordHasher(), audit=audit)


def try_create(service):
    password = bytearray(b"synthetic-long-admin-passphrase")
    try:
        return service.initialize(InitializeAdmin("First Admin", password, uuid.uuid4()))
    except InitialAdminError as exc:
        return exc.code
    finally:
        assert password == bytearray(len(password))


def main():
    name = "aut03a06_" + uuid.uuid4().hex[:12]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username=USER, host=HOST, port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            try:
                failed = make_service(runtime, FailingAudit())
                try:
                    try_create(failed)
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("audit failure accepted")
                with connect(name) as db:
                    assert db.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 0
                service = make_service(runtime, AuditService(SqlAlchemyAuditRepository()))
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(try_create, (service, service)))
                assert len([item for item in results if isinstance(item, uuid.UUID)]) == 1, results
                assert results.count("AUTH_INITIALIZATION_CLOSED") == 1, results
                user_id = next(item for item in results if isinstance(item, uuid.UUID))
                with connect(name) as db:
                    user = db.execute("SELECT state,deployment_role,credential_version,active_password_credential_id FROM plm.auth_users WHERE user_id=%s", (user_id,)).fetchone()
                    assert user[:3] == ("ENABLED", "DEPLOYMENT_ADMIN", 1) and user[3] is not None
                    credential = db.execute("SELECT password_hash,algorithm_id,parameter_set FROM plm.auth_password_credentials WHERE user_id=%s", (user_id,)).fetchone()
                    assert credential[0] != "synthetic-long-admin-passphrase" and credential[1] == "SCRYPT"
                    proof = memoryview(b"synthetic-long-admin-passphrase")
                    try:
                        assert ScryptPasswordHasher().verify_password(
                            proof, password_hash=credential[0], algorithm_id=credential[1],
                            parameter_set=credential[2],
                        )
                    finally:
                        proof.release()
                    assert db.execute("SELECT count(*) FROM plm.auth_users").fetchone()[0] == 1
                    assert db.execute("SELECT action,actor_type FROM plm.aud_events").fetchall() == [("AUTH_INITIAL_ADMIN_CREATED", "UNRESOLVED")]
                print("PASS: audit rollback, concurrent single winner, scrypt credential and one admin")
            finally:
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    main()
