"""Disposable Win11 Edge + PG18 proof for PROJECT Reference revision UI."""

from __future__ import annotations

import importlib.util
import secrets
import socket
import subprocess
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
from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_project_reference_eligibility_router,
    create_windows_project_reference_read_router,
    create_windows_project_reference_revise_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.login import create_login_router
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
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.document.api.read_documents import create_document_read_router
from plm_assistant.modules.document.api.read_versions import create_document_version_read_router
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "reference_project_fixture", ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
DIST = ROOT / "apps/frontend/dist"
PASSWORD = secrets.token_urlsafe(32)  # Disposable synthetic browser fixture only.


def on_created(*, port, runtime, audit, license_guard, project, created,
               document_version, documents, downloads, parse_results,
               browser_script=None, include_eligibility=False,
               expect_revision=True, **_unused) -> None:
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build apps/frontend before PROJECT Reference revise browser proof")
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
        for username, role in (("Browser Reference Manager", "PROJECT_MANAGER"),
                               ("Browser Reference Customer", "CUSTOMER_MANAGER")):
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
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(128)
        origin = f"http://127.0.0.1:{reservation.getsockname()[1]}"
        origins = LoginOriginPolicy([origin])
        receipts = SqlAlchemyIdempotencyReceipts()
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(hasher), audit=audit,
            idempotency=receipts)
        login = LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyLoginRateRepository()),
            identity=SqlAlchemyLoginIdentity(),
            missing_verifier=ScryptMissingIdentityVerifier(hasher),
            sessions=sessions, audit=audit)
        views = SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work, projects=SqlAlchemyAuthorizedProjects())
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            project_reference_read_router=create_windows_project_reference_read_router(
                runtime=runtime, sessions=sessions, origins=origins, license_guard=license_guard),
            project_reference_revise_router=create_windows_project_reference_revise_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard, audit=audit,
                documents=documents, downloads=downloads, parse_results=parse_results),
            project_reference_eligibility_router=(create_windows_project_reference_eligibility_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard, audit=audit,
                documents=documents, downloads=downloads,
                parse_results=parse_results) if include_eligibility else None),
            document_read_router=create_document_read_router(
                sessions=sessions, documents=documents, origins=origins,
                cursors=DocumentListCursorCodec(b"d" * 32)),
            document_version_read_router=create_document_version_read_router(
                sessions=sessions, documents=documents, origins=origins,
                cursors=VersionListCursorCodec(b"v" * 32)),
            document_download_router=create_document_download_router(
                sessions=sessions, downloads=downloads, origins=origins),
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
                    raise RuntimeError("Owned frontend/API startup failed")
                sleep(.05)
            command = ["node", str(browser_script or Path(__file__).with_name("run-edge-browser.mjs")),
                       origin, str(project), str(created.reference_solution_id),
                       str(document_version), PASSWORD]
            result = subprocess.run(command, check=False, timeout=140,
                                    capture_output=True, text=True, encoding="utf-8")
            if result.returncode != 0:
                raise RuntimeError(
                    f"Edge browser proof failed: {result.stdout[-3500:]} {result.stderr[-3500:]}")
            print(result.stdout.strip())
            if expect_revision:
                with httpx.Client(base_url=origin, timeout=15) as client:
                    path = (f"/api/v1/projects/{project}/reference-solutions/"
                            f"{created.reference_solution_id}:revise")
                    denied = client.post(path, cookies={"plm_session": (b"u" * 32).hex()},
                                         headers={"Origin": origin, "X-CSRF-Token": (b"v" * 32).hex(),
                                                  "If-Match": '"v1"',
                                                  "Idempotency-Key": "customer-revise-denied-0001"},
                                         json={"document_version_ids": [str(document_version)],
                                               "evidence_ids": [], "source_project_class": "PLM",
                                               "deidentification_class": "PROJECT_INTERNAL",
                                               "applicability": {}})
                    assert denied.status_code in (403, 404), denied.text
                with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                                     dbname="postgres", autocommit=True) as db:
                    row = db.execute(
                        "SELECT v.version_no,r.lock_version FROM plm.sol_reference_solutions r "
                        "JOIN plm.sol_reference_versions v "
                        "ON v.reference_version_id=r.current_version_ref "
                        "WHERE r.reference_solution_id=%s",
                        (created.reference_solution_id,)).fetchone()
                    assert row == (2, 1), row
                    assert db.execute(
                        "SELECT count(*) FROM plm.aud_events WHERE action='SOL_REFERENCE_REVISED' "
                        "AND target_object_id=%s", (created.reference_solution_id,)
                    ).fetchone()[0] == 1
                print("SOL_01_A12_P03_PROJECT_REVISE_EDGE_PG_PASS")
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned frontend/API server did not stop")


if __name__ == "__main__":
    fixture.main(on_created=on_created)
