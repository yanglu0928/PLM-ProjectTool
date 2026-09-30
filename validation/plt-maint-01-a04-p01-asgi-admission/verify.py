"""Disposable PG18 + ASGI proof of request-wide shared admission."""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
from alembic import command
from fastapi import Request
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.platform.infrastructure.maintenance_admission import (
    MAINTENANCE_LOCK_KEY, PostgresMaintenanceAdmission,
)
from plm_assistant.modules.platform.infrastructure.migration import create_migration_config


PORT = int(os.environ.get("PLM_POC_PG_PORT", "55434"))


def connect(name):
    return psycopg.connect(host="127.0.0.1", port=PORT, user="poc_admin",
                           dbname=name, autocommit=True)


def verify():
    name = "plt_asgi_admit_" + uuid.uuid4().hex[:9]
    with connect("postgres") as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            url = URL.create("postgresql+psycopg", username="poc_admin",
                host="127.0.0.1", port=PORT, database=name)
            command.upgrade(create_migration_config(url), "head")
            engine = create_engine(url, pool_size=2, max_overflow=0,
                                   pool_timeout=2, pool_pre_ping=True)
            try:
                entered, release = threading.Event(), threading.Event()
                app = create_app(maintenance_admission=PostgresMaintenanceAdmission(engine))
                calls = []

                @app.post("/probe")
                async def write_probe(request: Request):
                    import asyncio
                    body = await request.body()
                    entered.set()
                    if not await asyncio.to_thread(release.wait, 5):
                        raise RuntimeError("synthetic wait expired")
                    calls.append(body)
                    return {"ok": True}

                @app.get("/probe")
                async def read_probe():
                    return {"ok": True}

                with TestClient(app) as client, connect(name) as control:
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        response = pool.submit(client.post, "/probe", content=b"synthetic")
                        try:
                            assert entered.wait(5), "request did not enter"
                            assert control.execute("SELECT pg_try_advisory_lock(%s)",
                                (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is False
                        finally:
                            release.set()
                        accepted = response.result(timeout=5)
                    assert accepted.status_code == 200 and calls == [b"synthetic"]
                    assert control.execute("SELECT pg_try_advisory_lock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    assert control.execute("SELECT pg_advisory_unlock(%s)",
                        (MAINTENANCE_LOCK_KEY,)).fetchone()[0] is True
                    control.execute("UPDATE plm.plt_maintenance_state SET "
                        "state='MAINTENANCE',lock_version=1 WHERE state_id=1")
                    blocked = client.post("/probe", content=b"blocked")
                    assert blocked.status_code == 503
                    assert blocked.json()["error"]["code"] == "SYSTEM_UNAVAILABLE"
                    assert calls == [b"synthetic"]
                    assert client.get("/probe").status_code == 200
                    assert client.get("/health/live").status_code == 200
                print("PLT-MAINT-01-A04-P01 PASS: real PG18 ASGI write window, "
                      "exclusive contention, maintenance refusal and GET bypass")
            finally:
                engine.dispose()
        finally:
            admin.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                          "WHERE datname=%s AND pid<>pg_backend_pid()", (name,))
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


if __name__ == "__main__":
    verify()
