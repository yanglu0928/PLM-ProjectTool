"""Disposable PG18 proof of Provider Worker maintenance admission."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from alembic import command
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.modules.ai.application.provider_probe_worker import ProviderProbeWorkerCycle
from plm_assistant.modules.ai.application.provider_probe_worker_loop import ProviderProbeWorkerLoop
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY, MaintenanceAdmissionError, PostgresMaintenanceAdmission,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55432"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


class Worker:
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()
        self.calls = 0

    def run_once(self, *, worker_ref):
        assert worker_ref == "ai-probe-pg18"
        self.entered.set()
        assert self.release.wait(5), "synthetic worker wait expired"
        self.calls += 1
        return ProviderProbeWorkerCycle("IDLE")


def verify():
    name = "ai_probe_loop_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                             host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url, pool_size=1, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                worker = Worker()
                loop = ProviderProbeWorkerLoop(
                    worker=worker, worker_ref="ai-probe-pg18",
                    maintenance_admission=PostgresMaintenanceAdmission(engine),
                    poll_seconds=.05,
                )
                with connect(name) as control, ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(loop.run, max_cycles=1)
                    try:
                        assert worker.entered.wait(5), "Provider worker did not enter"
                        assert control.execute("SELECT pg_try_advisory_lock(%s)",
                            (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                    finally:
                        worker.release.set()
                    assert future.result(timeout=5).cycles == 1
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    control.execute("UPDATE plm.plt_maintenance_state SET "
                        "state='MAINTENANCE',lock_version=1 WHERE state_id=1")
                    try:
                        loop.run(max_cycles=1)
                    except MaintenanceAdmissionError as exc:
                        assert exc.code == "MAINTENANCE_ACTIVE"
                    else:
                        raise AssertionError("Worker entered maintenance")
                    assert worker.calls == 1
                print("PASS: PG18 Provider Worker holds admission over cycle, "
                      "releases on exit and refuses maintenance")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
