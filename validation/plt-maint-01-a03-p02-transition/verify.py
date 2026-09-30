"""Disposable PG18 proof for atomic internal transition plus Audit."""

from __future__ import annotations

import os
import uuid

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
                transition = PostgresMaintenanceTransition(engine)
                operator = uuid.uuid4()
                with connect(name) as control:
                    with gate.admit():
                        try:
                            transition.change(target="MAINTENANCE", expected_version=0,
                                              operator_id=operator, wait_ms=50)
                        except MaintenanceAdmissionError as exc:
                            assert exc.code == "MAINTENANCE_BUSY", exc.code
                        else:
                            raise AssertionError("exclusive bypassed shared admission")
                    assert control.execute("SELECT state,lock_version FROM "
                        "plm.plt_maintenance_state").fetchone() == ("RUNNING", 0)
                    first = transition.change(target="MAINTENANCE", expected_version=0,
                                              operator_id=operator)
                    assert (first.state, first.lock_version) == ("MAINTENANCE", 1)
                    try:
                        with gate.admit():
                            raise AssertionError("admission entered maintenance")
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_ACTIVE", exc.code
                    try:
                        transition.change(target="MAINTENANCE", expected_version=0,
                                          operator_id=operator)
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_STATE_CONFLICT", exc.code
                    else:
                        raise AssertionError("stale transition succeeded")
                    second = transition.change(target="RUNNING", expected_version=1,
                                               operator_id=operator)
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
                                          operator_id=operator)
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
                print("PLT-MAINT-01-A03-P02 PASS: PG18 bounded contention, "
                      "atomic state/audit, stale refusal, rollback and no lock leak")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
