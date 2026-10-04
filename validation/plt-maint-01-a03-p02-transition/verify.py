"""Disposable PG18 proof for atomic internal transition plus Audit."""

from __future__ import annotations

import os
import uuid
import hashlib

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MaintenanceAdmissionError, PostgresMaintenanceAdmission,
)
from plm_assistant.modules.platform.infrastructure.maintenance_transition import (
    PostgresMaintenanceTransition,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config
from plm_assistant.modules.auth.infrastructure.license_import_access import SqlAlchemyLicenseImportAccess
from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def verify():
    name = "plt_maint_trans_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url, pool_size=2, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                gate = PostgresMaintenanceAdmission(engine)
                transition = PostgresMaintenanceTransition(
                    engine, access=SqlAlchemyLicenseImportAccess())
                token, csrf = b"a" * 32, b"b" * 32
                with connect(name) as control:
                    operator = control.execute("INSERT INTO plm.auth_users(username_display,"
                        "username_normalized,deployment_role) VALUES ('Synthetic Admin',"
                        "'synthetic admin','DEPLOYMENT_ADMIN') RETURNING user_id").fetchone()[0]
                    credential = control.execute("INSERT INTO plm.auth_password_credentials("
                        "user_id,credential_version,password_hash,algorithm_id,parameter_set) "
                        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
                        "RETURNING password_credential_id", (operator,)).fetchone()[0]
                    control.execute("UPDATE plm.auth_users SET credential_version=1,"
                        "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                        (credential, operator))
                    control.execute("INSERT INTO plm.auth_sessions(session_token_digest,"
                        "csrf_digest,user_id,credential_version,idle_expires_at,"
                        "absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+"
                        "interval '15 minutes',statement_timestamp()+interval '1 hour')",
                        (hashlib.sha256(token).digest(), hashlib.sha256(csrf).digest(), operator))
                    proof = {"session_token": token, "csrf_token": csrf}
                    with gate.admit():
                        try:
                            transition.change(target="MAINTENANCE", expected_version=0,
                                              **proof, wait_ms=50)
                        except MaintenanceAdmissionError as exc:
                            assert exc.code == "MAINTENANCE_BUSY", exc.code
                        else:
                            raise AssertionError("exclusive bypassed shared admission")
                    assert control.execute("SELECT state,lock_version FROM "
                        "plm.plt_maintenance_state").fetchone() == ("RUNNING", 0)
                    first = transition.change(target="MAINTENANCE", expected_version=0,
                                              **proof)
                    assert (first.state, first.lock_version) == ("MAINTENANCE", 1)
                    try:
                        with gate.admit():
                            raise AssertionError("admission entered maintenance")
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_ACTIVE", exc.code
                    try:
                        transition.change(target="MAINTENANCE", expected_version=0,
                                          **proof)
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_STATE_CONFLICT", exc.code
                    else:
                        raise AssertionError("stale transition succeeded")
                    second = transition.change(target="RUNNING", expected_version=1,
                                               **proof)
                    assert (second.state, second.lock_version) == ("RUNNING", 2)
                    with gate.admit() as snapshot:
                        assert snapshot.lock_version == 2
                    rows = control.execute("SELECT action,before_state,after_state,actor_type,"
                        "actor_id FROM plm.aud_events WHERE action LIKE 'MAINTENANCE_%' "
                        "ORDER BY occurred_at").fetchall()
                    assert rows == [
                        ("MAINTENANCE_ENTER", "RUNNING", "MAINTENANCE", "USER", operator),
                        ("MAINTENANCE_EXIT", "MAINTENANCE", "RUNNING", "USER", operator),
                    ], rows

                    class BrokenAudit:
                        def append(self, *_):
                            raise RuntimeError("synthetic audit failure")

                    transition._audit = BrokenAudit()
                    try:
                        transition.change(target="MAINTENANCE", expected_version=2,
                                          **proof)
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_UNAVAILABLE", exc.code
                    else:
                        raise AssertionError("state survived audit failure")
                    assert control.execute("SELECT state,lock_version FROM "
                        "plm.plt_maintenance_state").fetchone() == ("RUNNING", 2)
                    assert control.execute("SELECT count(*) FROM plm.aud_events WHERE "
                        "action LIKE 'MAINTENANCE_%'").fetchone()[0] == 2
                    with gate.admit():
                        pass  # Failed transition released its exclusive lock.
                    transition._audit = AuditService(SqlAlchemyAuditRepository())
                    for denied in (
                        {"session_token": b"?" * 32, "csrf_token": csrf},
                        {"session_token": token, "csrf_token": b"?" * 32},
                    ):
                        try:
                            transition.change(target="MAINTENANCE", expected_version=2,
                                              **denied)
                        except MaintenanceAdmissionError as exc:
                            assert exc.code == "MAINTENANCE_ACCESS_DENIED", exc.code
                        else:
                            raise AssertionError("invalid operator proof accepted")
                    other_token, other_csrf = b"c" * 32, b"d" * 32
                    other = control.execute("INSERT INTO plm.auth_users(username_display,"
                        "username_normalized,deployment_role) VALUES ('Synthetic Nonadmin',"
                        "'synthetic nonadmin','NONE') RETURNING user_id").fetchone()[0]
                    other_credential = control.execute("INSERT INTO plm.auth_password_credentials("
                        "user_id,credential_version,password_hash,algorithm_id,parameter_set) "
                        "VALUES (%s,1,'$synthetic$not-for-login','TEST_ONLY','{}'::jsonb) "
                        "RETURNING password_credential_id", (other,)).fetchone()[0]
                    control.execute("UPDATE plm.auth_users SET credential_version=1,"
                        "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                        (other_credential, other))
                    control.execute("INSERT INTO plm.auth_sessions(session_token_digest,"
                        "csrf_digest,user_id,credential_version,idle_expires_at,"
                        "absolute_expires_at) VALUES (%s,%s,%s,1,statement_timestamp()+"
                        "interval '15 minutes',statement_timestamp()+interval '1 hour')",
                        (hashlib.sha256(other_token).digest(),
                         hashlib.sha256(other_csrf).digest(), other))
                    other_proof = {"session_token": other_token, "csrf_token": other_csrf}
                    for state, role in (("ENABLED", "NONE"),
                                        ("DISABLED", "DEPLOYMENT_ADMIN")):
                        control.execute("UPDATE plm.auth_users SET state=%s,"
                            "deployment_role=%s WHERE user_id=%s", (state, role, other))
                        try:
                            transition.change(target="MAINTENANCE", expected_version=2,
                                              **other_proof)
                        except MaintenanceAdmissionError as exc:
                            assert exc.code == "MAINTENANCE_ACCESS_DENIED", exc.code
                        else:
                            raise AssertionError("ineligible operator accepted")
                    control.execute("UPDATE plm.auth_sessions SET revoked_at="
                        "statement_timestamp(),revoke_reason='TEST_REVOKED',"
                        "lock_version=lock_version+1 WHERE user_id=%s", (operator,))
                    try:
                        transition.change(target="MAINTENANCE", expected_version=2,
                                          **proof)
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_ACCESS_DENIED", exc.code
                    else:
                        raise AssertionError("revoked operator accepted")
                    assert control.execute("SELECT state,lock_version FROM "
                        "plm.plt_maintenance_state").fetchone() == ("RUNNING", 2)
                    assert control.execute("SELECT count(*) FROM plm.aud_events WHERE "
                        "action LIKE 'MAINTENANCE_%'").fetchone()[0] == 2
                print("PLT-MAINT-01-A03-P02 PASS: PG18 bounded contention, "
                      "atomic state/audit, current admin denial, rollback and no lock leak")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
