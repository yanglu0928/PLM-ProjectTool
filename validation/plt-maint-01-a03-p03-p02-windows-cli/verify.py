"""Disposable PG18 genuine Auth proof for local maintenance command composition."""

from __future__ import annotations

import os
import secrets
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.maintenance_windows import (
    MaintenanceCommandError, execute_maintenance,
)
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.auth.application.initial_admin import InitializeAdmin, InitialAdminService
from plm_assistant.modules.auth.infrastructure.initial_admin import SqlAlchemyInitialAdminRepository
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.database import create_database_runtime
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))
PASSWORD = secrets.token_urlsafe(24).encode("ascii")  # Ephemeral test-only input.


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def verify():
    name = "plt_maint_cli_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            runtime = create_database_runtime(url)
            engine = create_engine(url, pool_size=2, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                initial = InitialAdminService(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyInitialAdminRepository(),
                    hasher=ScryptPasswordHasher(),
                    audit=AuditService(SqlAlchemyAuditRepository()),
                )
                initial.initialize(InitializeAdmin("Synthetic Admin", bytearray(PASSWORD),
                                                uuid.uuid4()))

                def run(password, target, version, *, expect_failure=False):
                    value = bytearray(password)
                    try:
                        result = execute_maintenance(
                            runtime=runtime, engine=engine, username="Synthetic Admin",
                            password=value, target=target, expected_version=version)
                    except MaintenanceCommandError:
                        if not expect_failure:
                            raise
                        result = None
                    else:
                        if expect_failure:
                            raise AssertionError("invalid maintenance command accepted")
                    assert value == bytearray(len(value)), "password not erased"
                    return result

                with connect(name) as db:
                    run(PASSWORD + b"x", "MAINTENANCE", 0, expect_failure=True)
                    assert db.execute("SELECT state,lock_version FROM "
                        "plm.plt_maintenance_state").fetchone() == ("RUNNING", 0)
                    first = run(PASSWORD, "MAINTENANCE", 0)
                    assert (first.state, first.lock_version) == ("MAINTENANCE", 1)
                    run(PASSWORD, "MAINTENANCE", 0, expect_failure=True)
                    second = run(PASSWORD, "RUNNING", 1)
                    assert (second.state, second.lock_version) == ("RUNNING", 2)
                    events = db.execute("SELECT action,outcome,actor_type,before_state,"
                        "after_state FROM plm.aud_events WHERE action LIKE "
                        "'MAINTENANCE_%' ORDER BY occurred_at").fetchall()
                    assert events == [
                        ("MAINTENANCE_ENTER", "SUCCESS", "USER", "RUNNING", "MAINTENANCE"),
                        ("MAINTENANCE_EXIT", "SUCCESS", "USER", "MAINTENANCE", "RUNNING"),
                    ], events
                    assert db.execute("SELECT count(*) FROM plm.auth_sessions WHERE "
                        "revoked_at IS NULL").fetchone()[0] == 0
                    assert db.execute("SELECT state,lock_version FROM "
                        "plm.plt_maintenance_state").fetchone() == ("RUNNING", 2)
                print("PLT-MAINT-01-A03-P03-P02 internal PASS: real scrypt login, "
                      "bounded session, audited enter/exit, refusal and revocation")
            finally:
                engine.dispose()
                runtime.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
