"""Disposable PostgreSQL 18 proof for Parser sweep-and-step admission."""

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
from unit.test_parser_worker_loop import _Step, _Sweep

from plm_assistant.modules.parser.application.worker_loop import ParserWorkerLoop
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY, MaintenanceAdmissionError, PostgresMaintenanceAdmission,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55432"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def verify():
    name = "plt_parser_loop_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                             host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url, pool_size=1, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                step, sweep = _Step(), _Sweep()
                step.release.set()
                entered, release = threading.Event(), threading.Event()
                original = sweep.run_next

                def scan():
                    entered.set()
                    assert release.wait(5), "synthetic scan wait expired"
                    return original()

                sweep.run_next = scan
                loop = ParserWorkerLoop(step=step, sweep=sweep, poll_seconds=.05,
                    maintenance_admission=PostgresMaintenanceAdmission(engine))
                with connect(name) as control, ThreadPoolExecutor(max_workers=1) as pool:
                    original_step = step.step
                    def checked_step():
                        assert control.execute("SELECT pg_try_advisory_lock(%s)",
                            (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                        return original_step()
                    step.step = checked_step
                    future = pool.submit(loop.run, max_cycles=1)
                    try:
                        assert entered.wait(5), "Parser scan did not enter"
                        assert control.execute("SELECT pg_try_advisory_lock(%s)",
                            (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                    finally:
                        release.set()
                    assert future.result(timeout=5).cycles == 1
                    assert (sweep.calls, step.calls) == (1, 1)
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    control.execute("UPDATE plm.plt_maintenance_state SET "
                        "state='MAINTENANCE',lock_version=1 WHERE state_id=1")
                    try:
                        loop.run(max_cycles=1)
                    except MaintenanceAdmissionError:
                        pass
                    else:
                        raise AssertionError("Parser cycle entered maintenance")
                    assert (sweep.calls, step.calls) == (1, 1)
                print("PLT-MAINT-01-A05-P03 PASS: PG18 Parser sweep and step "
                      "share one lock, exclusive waits, maintenance refuses before scan")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
