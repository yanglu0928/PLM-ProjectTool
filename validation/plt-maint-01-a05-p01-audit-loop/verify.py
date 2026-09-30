"""Disposable PG18 proof for Audit loop step-wide maintenance admission."""

from __future__ import annotations

import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/backend/tests"))
from unit import test_audit_worker_step as fixture
from plm_assistant.modules.audit.application.worker_capture import AuditExportWorkerError
from plm_assistant.modules.audit.application.worker_loop import AuditExportWorkerLoop
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY, PostgresMaintenanceAdmission,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def verify():
    name = "plt_audit_loop_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url, pool_size=2, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                t = fixture.WorkerStepTests()
                t.setUp()
                t.admission.claim_next.return_value = None
                entered, release = threading.Event(), threading.Event()
                original = t.step.step

                def step():
                    entered.set()
                    assert release.wait(5), "synthetic step wait expired"
                    return original()

                t.step.step = step
                loop = AuditExportWorkerLoop(step=t.step, poll_seconds=.05,
                    maintenance_admission=PostgresMaintenanceAdmission(engine))
                with connect(name) as control, ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(loop.run, max_steps=1)
                    try:
                        assert entered.wait(5), "worker step did not enter"
                        assert control.execute("SELECT pg_try_advisory_lock(%s)",
                            (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                    finally:
                        release.set()
                    assert future.result(timeout=5).idle == 1
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    before = t.admission.claim_next.call_count
                    control.execute("UPDATE plm.plt_maintenance_state SET "
                        "state='MAINTENANCE',lock_version=1 WHERE state_id=1")
                    try:
                        loop.run(max_steps=1)
                    except AuditExportWorkerError:
                        pass
                    else:
                        raise AssertionError("Audit step entered maintenance")
                    assert t.admission.claim_next.call_count == before
                print("PLT-MAINT-01-A05-P01 PASS: PG18 Audit step-wide shared "
                      "admission, exclusive contention and maintenance refusal")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
