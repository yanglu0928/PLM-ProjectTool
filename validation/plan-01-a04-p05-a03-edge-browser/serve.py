"""Disposable Win11 Edge + PostgreSQL proof of the Plan identity UI."""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import httpx
import psycopg
import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_plan import (
    create_windows_plan_create_router, create_windows_plan_read_routers,
)
from plm_assistant.modules.auth.api.login import create_login_router
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import create_session_read_router
from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimiter
from plm_assistant.modules.auth.application.login_service import LoginService
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.login_identity import SqlAlchemyLoginIdentity
from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
from plm_assistant.modules.auth.infrastructure.missing_identity_verifier import ScryptMissingIdentityVerifier
from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
from plm_assistant.modules.project.api.read_projects import create_project_read_router
from plm_assistant.modules.project.application.read_projects import ProjectReadService
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.project.infrastructure.read_repository import SqlAlchemyProjectReadRepository


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "plan_browser_fixture",
    ROOT / "validation/sol-02-a04-outline-create-http-pg/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
DIST = ROOT / "apps/frontend/dist"
PASSWORD = "Synthetic-Plan-Browser-Only-2026"
MANAGER = "Browser Plan Manager"
CUSTOMER = "Browser Plan Customer"


def on_created(*, port, runtime, audit, license_guard, project, other_project,
               manager,
               **_unused) -> int:
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build apps/frontend before Plan browser proof")
    hasher = ScryptPasswordHasher()
    clear = bytearray(PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            hashed = hasher.hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        department = db.execute("SELECT department_id FROM plm.prj_departments "
                                "WHERE project_id=%s AND department_code='REF'",
                                (project,)).fetchone()[0]
        for username, role in ((MANAGER, "PROJECT_MANAGER"),
                               (CUSTOMER, "CUSTOMER_MANAGER")):
            actor = db.execute("INSERT INTO plm.auth_users"
                               "(username_display,username_normalized) VALUES (%s,%s) "
                               "RETURNING user_id", (username, username.casefold())).fetchone()[0]
            credential = db.execute(
                "INSERT INTO plm.auth_password_credentials"
                "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
                "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
                (actor, hashed.password_hash, hashed.algorithm_id,
                 '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
            db.execute("UPDATE plm.auth_users SET credential_version=1,"
                       "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                       (credential, actor))
            db.execute("INSERT INTO plm.prj_project_members"
                       "(project_id,user_id,department_id,project_role) "
                       "VALUES (%s,%s,%s,%s)", (project, actor, department, role))
    # Exactly 50 older disposable identities force a second page after browser CREATE.
    seed_time = datetime.now(timezone.utc) - timedelta(days=1)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres") as db:
        for index in range(50):
            identity, name = uuid.uuid4(), f"Seed Plan {index:02d}"
            db.execute(
                "INSERT INTO plm.pln_plans "
                "(plan_id,project_id,name,created_by,created_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (identity, project, name, manager, seed_time))
            db.execute(
                "INSERT INTO plm.pln_plan_create_results "
                "(plan_id,project_id,name,created_at) VALUES (%s,%s,%s,%s)",
                (identity, project, name, seed_time))
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = LoginOriginPolicy([origin])
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(hasher), audit=audit,
            idempotency=SqlAlchemyIdempotencyReceipts())
        login = LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyLoginRateRepository()),
            identity=SqlAlchemyLoginIdentity(),
            missing_verifier=ScryptMissingIdentityVerifier(hasher),
            sessions=sessions, audit=audit)
        views = SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work,
            projects=SqlAlchemyAuthorizedProjects())
        detail, listing = create_windows_plan_read_routers(
            runtime=runtime, sessions=sessions, origins=origins,
            license_guard=license_guard, cursors=PlanListCursorCodec(b"p" * 32))
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            project_read_router=create_project_read_router(
                sessions=sessions, origins=origins,
                projects=ProjectReadService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectReadAccess(),
                    license_guard=license_guard,
                    repository=SqlAlchemyProjectReadRepository())),
            plan_create_router=create_windows_plan_create_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard, audit=audit),
            plan_read_router=detail, plan_list_router=listing,
        )
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="frontend-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend(frontend_path: str):
            if frontend_path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(DIST / "index.html", media_type="text/html")

        server = uvicorn.Server(uvicorn.Config(
            app, log_level="critical", access_log=False,
            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5))
        worker = Thread(target=lambda: server.run(sockets=[reservation]), daemon=False)
        worker.start()
        try:
            deadline = monotonic() + 15
            while not server.started:
                if not worker.is_alive() or monotonic() > deadline:
                    raise RuntimeError("Owned Plan preview did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project)],
                check=False, timeout=150, capture_output=True, text=True,
                encoding="utf-8", env={**os.environ,
                    "PLM_BROWSER_SYNTHETIC_PASSWORD": PASSWORD,
                    "PLM_BROWSER_MANAGER_NAME": MANAGER,
                    "PLM_BROWSER_CUSTOMER_NAME": CUSTOMER})
            if result.returncode:
                raise RuntimeError(
                    "Plan browser proof failed: "
                    f"{result.stdout[-4000:]} {result.stderr[-4000:]}")
            print(result.stdout.strip(), flush=True)
            with httpx.Client(base_url=origin, timeout=20) as customer_client:
                customer_login = customer_client.post(
                    "/api/v1/auth/login", headers={"Origin": origin},
                    json={"username": CUSTOMER, "password": PASSWORD})
                assert customer_login.status_code == 200, customer_login.text
                denied = customer_client.post(
                    f"/api/v1/projects/{project}/plans",
                    headers={"Origin": origin,
                             "X-CSRF-Token": customer_login.json()["data"]["csrf_token"],
                             "Idempotency-Key": "customer-denied-plan-0001"},
                    json={"name": "Denied Plan"})
                assert denied.status_code == 404 and denied.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned Plan preview did not stop")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        assert db.execute("SELECT count(*) FROM plm.pln_plans WHERE project_id=%s",
                          (project,)).fetchone()[0] == 51
        assert db.execute("SELECT count(*) FROM plm.pln_plans WHERE project_id=%s "
                          "AND name='Browser Plan'", (project,)).fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM plm.aud_events "
                          "WHERE action='PLAN_CREATED' AND target_project_id=%s",
                          (project,)).fetchone()[0] == 1
    return 0


if __name__ == "__main__":
    fixture.prior.main(on_created=on_created)
    print("PLAN_01_A04_P05_A03_EDGE_PG_PASS: synthetic Win11 Edge/Vue/Uvicorn/PG")
