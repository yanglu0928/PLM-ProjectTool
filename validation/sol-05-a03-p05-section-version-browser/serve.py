"""Disposable Win11 Edge/PG proof of SectionVersion history navigation."""

from __future__ import annotations

import importlib.util
import socket
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import psycopg
import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_read_router,
    create_windows_section_version_read_router,
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
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_history_fixture_for_browser",
    ROOT / "validation/sol-05-a03-p02-section-version-read-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
DIST = ROOT / "apps/frontend/dist"
PASSWORD = "Synthetic-Section-History-Browser-Only-2026"


def _reader(port, project):
    hasher = ScryptPasswordHasher()
    clear = bytearray(PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            hashed = hasher.hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        department = db.execute(
            "SELECT department_id FROM plm.prj_departments WHERE "
            "project_id=%s LIMIT 1", (project,)).fetchone()[0]
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Section History Reader','section history reader') RETURNING user_id"
        ).fetchone()[0]
        credential = db.execute(
            "INSERT INTO plm.auth_password_credentials"
            "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
            (actor, hashed.password_hash, hashed.algorithm_id,
             '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,"
            "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
            (credential, actor))
        db.execute(
            "INSERT INTO plm.prj_project_members"
            "(project_id,user_id,department_id,project_role) "
            "VALUES (%s,%s,%s,'CUSTOMER_MEMBER')",
            (project, actor, department))
    return hasher


def on_browser(*, port, runtime, audit, license_guard, project, other_project,
               section, **_unused):
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before SectionVersion browser proof")
    hasher = _reader(port, project)
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
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            solution_section_read_router=create_windows_section_read_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard),
            solution_section_version_read_router=create_windows_section_version_read_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard,
                cursors=SectionVersionListCursorCodec(b"h" * 32)),
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
                    raise RuntimeError("Owned SectionVersion preview did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(section), PASSWORD],
                check=False, timeout=120, capture_output=True, text=True,
                encoding="utf-8")
            if result.returncode:
                raise RuntimeError("SectionVersion browser proof failed: "
                                   f"{result.stdout[-3000:]} {result.stderr[-3000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned SectionVersion preview did not stop")
    return 0


if __name__ == "__main__":
    prior.prior.prior.main(on_created=lambda **kwargs: prior.prior.on_created(
        **kwargs, on_http=on_browser))
    print("SOL_05_A03_P05_SECTION_VERSION_BROWSER_PASS: Win11 Edge/PG member history")
