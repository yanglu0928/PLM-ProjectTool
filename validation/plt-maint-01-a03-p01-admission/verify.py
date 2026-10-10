"""Disposable PG18 dual-connection shared maintenance admission proof."""

from __future__ import annotations

import os
import uuid

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY, MaintenanceAdmissionError,
    PostgresMaintenanceAdmission,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def reject(gate, code):
    try:
        with gate.admit():
            raise AssertionError("admission accepted")
    except MaintenanceAdmissionError as exc:
        assert exc.code == code, (exc.code, code)
    else:
        raise AssertionError("admission accepted")


def verify():
    name = "plt_maint_admit_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=name)
            config = create_migration_config(url)
            command.upgrade(config, "20260930_0050")
            engine = create_engine(url, pool_size=2, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                gate = PostgresMaintenanceAdmission(engine)
                reject(gate, "MAINTENANCE_UNAVAILABLE")
                command.upgrade(config, "head")
                with connect(name) as control:
                    with gate.admit() as first:
                        assert first.lock_version == 0
                        holder_state = control.execute(
                            "SELECT a.state FROM pg_locks l JOIN pg_stat_activity a "
                            "ON a.pid=l.pid WHERE l.locktype='advisory' "
                            "AND l.mode='ShareLock' AND l.granted AND l.database="
                            "(SELECT oid FROM pg_database WHERE datname=current_database())"
                        ).fetchone()[0]
                        assert holder_state == "idle", holder_state
                        with gate.admit() as second:
                            assert second.lock_version == 0
                            assert control.execute("SELECT pg_try_advisory_lock(%s)",
                                (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                        assert control.execute("SELECT pg_try_advisory_lock(%s)",
                            (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    reject(gate, "MAINTENANCE_BUSY")
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    try:
                        with gate.admit():
                            raise ValueError("caller failure")
                    except ValueError as exc:
                        assert str(exc) == "caller failure"
                    else:
                        raise AssertionError("caller exception masked")
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    control.execute("UPDATE plm.plt_maintenance_state SET "
                        "state='MAINTENANCE',lock_version=1 WHERE state_id=1")
                    reject(gate, "MAINTENANCE_ACTIVE")
                    control.execute("UPDATE plm.plt_maintenance_state SET "
                        "state='RUNNING',lock_version=2 WHERE state_id=1")
                    with gate.admit() as resumed:
                        assert resumed.lock_version == 2
                    try:
                        with gate.admit():
                            holder = control.execute(
                                "SELECT pid FROM pg_locks WHERE locktype='advisory' "
                                "AND mode='ShareLock' AND granted AND database="
                                "(SELECT oid FROM pg_database WHERE datname=current_database())"
                            ).fetchone()[0]
                            assert control.execute("SELECT pg_terminate_backend(%s)",
                                (holder,)).fetchone()[0] is True
                    except MaintenanceAdmissionError:
                        pass  # Connection loss is detected, not a quiescence proof.
                    else:
                        raise AssertionError("lost admission connection was accepted")
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                print("PLT-MAINT-01-A03-P01 PASS: PG18 shared admission, "
                      "exclusive contention, durable state refusal, connection-loss "
                      "reporting, no pooled lock leak")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
