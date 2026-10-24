"""Disposable Win11 Edge/PG18 SOL-03 manager-to-customer Review proof."""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
import uuid

import psycopg
import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_list_router,
    create_windows_project_review_read_router,
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_review_list_cursor import (
    create_windows_review_list_cursor_codec,
)
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_review_subject,
    create_windows_outline_review_submission_router,
    create_windows_outline_version_create_router,
    create_windows_outline_version_read_router,
    create_windows_outline_version_validate_router,
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
from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.api.member_list_cursor import MemberListCursorCodec
from plm_assistant.modules.project.api.read_members import create_project_member_read_router
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.application.read_members import ProjectMemberReadService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.project.infrastructure.member_read_repository import SqlAlchemyProjectMemberReadRepository
from plm_assistant.modules.solution.api.outline_version_list_cursor import OutlineVersionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "apps/frontend/dist"


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


full = _load("outline_full_for_edge",
             "validation/sol-03-a06-p03-a05-p03-a05-p02-full-source-pg/verify.py")
login_fixture = _load("sol06_login_for_outline_edge",
                      "validation/sol-06-a14-p09-structured-spec-submit-browser/serve.py")


class _CursorResolver:
    def resolve_key(self, key_ref: str) -> bytes:
        assert key_ref == "review-list-cursor-v1"
        return b"r" * 32


def on_browser(*, port, runtime, project, other_project, audit,
               license_guard, documents, downloads, parse_results,
               token, csrf, **context):
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before SOL-03 Edge proof")
    outline, section, requirement, requirement_version = (
        full._approved_section_v2(port=port, runtime=runtime, project=project,
                                  other_project=other_project, audit=audit,
                                  license_guard=license_guard,
                                  documents=documents, downloads=downloads,
                                  parse_results=parse_results,
                                  token=token, csrf=csrf, **context))
    with tempfile.TemporaryDirectory(prefix="plm-outline-review-edge-source-") as root:
        storage = Path(root)
        origins_preflight = LoginOriginPolicy(["https://plm.example.test"])
        preflight_sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(), issue_access=object(),
            audit=audit)
        proof = dict(runtime=runtime, sessions=preflight_sessions,
                     origins=origins_preflight, license_guard=license_guard,
                     audit=audit, document_storage_root=storage,
                     parse_result_storage_root=storage,
                     documents=documents, downloads=downloads,
                     parse_results=parse_results)
        path = f"/api/v1/projects/{project}/solution-outlines/{outline}/versions"
        payload = {
            "section_ids": [str(section)],
            "requirement_refs": [{
                "requirement_id": str(requirement),
                "requirement_version_id": str(requirement_version),
            }],
            "reference_refs": [], "missing_declarations": [],
            "conflict_declarations": [],
        }
        with TestClient(create_app(
                solution_outline_version_create_router=(
                    create_windows_outline_version_create_router(
                        runtime=runtime, sessions=preflight_sessions,
                        origins=origins_preflight, license_guard=license_guard,
                        audit=audit, document_storage_root=storage,
                        parse_result_storage_root=storage)),
                solution_outline_version_validate_router=(
                    create_windows_outline_version_validate_router(**proof))),
                base_url="https://plm.example.test") as app:
            created = app.post(path, headers=full._headers(
                token, csrf, "outline-edge-create-0001"), json=payload)
            assert created.status_code == 201, created.text
            version = uuid.UUID(
                created.json()["data"]["solution_outline_version_id"])
            validated = app.post(f"{path}/{version}:validate",
                                 headers=full._headers(
                                     token, csrf, "outline-edge-validate-0001"))
            assert validated.status_code == 200, validated.text
            assert validated.json()["data"]["facts"] == {
                "order": "PASS", "source": "PASS", "coverage": "PASS"}

        hasher, customer = login_fixture._login_users(port, project)
        connection = full._connection(port)
        with psycopg.connect(**connection) as db:
            db.execute(
                "UPDATE plm.prj_project_members SET project_role='CUSTOMER_MEMBER' "
                "WHERE project_id=%s AND user_id=%s AND state='ACTIVE'",
                (project, customer))
            assert db.execute(
                "SELECT project_role FROM plm.prj_project_members "
                "WHERE project_id=%s AND user_id=%s",
                (project, customer)).fetchone()[0] == "CUSTOMER_MEMBER"

        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0)); reservation.listen(128)
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
                rate=LoginRateLimiter(
                    unit_of_work=runtime.unit_of_work,
                    repository=SqlAlchemyLoginRateRepository()),
                identity=SqlAlchemyLoginIdentity(),
                missing_verifier=ScryptMissingIdentityVerifier(hasher),
                sessions=sessions, audit=audit)
            views = SqlAlchemySessionView(
                unit_of_work=runtime.unit_of_work,
                projects=SqlAlchemyAuthorizedProjects())
            authorization = ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository())
            member_reads = ProjectMemberReadService(
                unit_of_work=runtime.unit_of_work,
                access=SqlAlchemyProjectMemberNames(),
                license_guard=license_guard, authorization=authorization,
                repository=SqlAlchemyProjectMemberReadRepository())
            common = dict(runtime=runtime, origins=origins,
                          license_guard=license_guard, audit=audit,
                          documents=documents, downloads=downloads,
                          parse_results=parse_results)
            owner = create_windows_outline_review_subject(
                runtime=runtime, license_guard=license_guard, audit=audit,
                document_storage_root=storage,
                parse_result_storage_root=storage,
                documents=documents, downloads=downloads,
                parse_results=parse_results, terminal_context=True)
            app = create_app(
                login_router=create_login_router(
                    login=login, origins=origins, views=views),
                session_router=create_session_read_router(
                    sessions=sessions, origins=origins, views=views),
                project_member_read_router=create_project_member_read_router(
                    sessions=sessions, members=member_reads, origins=origins,
                    cursors=MemberListCursorCodec(b"m" * 32)),
                solution_outline_version_read_router=(
                    create_windows_outline_version_read_router(
                        runtime=runtime, sessions=sessions, origins=origins,
                        license_guard=license_guard,
                        cursors=OutlineVersionListCursorCodec(b"o" * 32))),
                solution_outline_review_submission_router=(
                    create_windows_outline_review_submission_router(
                        runtime=runtime, sessions=sessions, origins=origins,
                        license_guard=license_guard, audit=audit,
                        document_storage_root=storage,
                        parse_result_storage_root=storage,
                        documents=documents, downloads=downloads,
                        parse_results=parse_results)),
                review_list_router=create_windows_project_review_list_router(
                    **common, cursors=create_windows_review_list_cursor_codec(
                        resolver=_CursorResolver()), outline_subject=owner),
                review_read_router=create_windows_project_review_read_router(
                    **common, outline_subject=owner),
                review_command_router=create_windows_project_review_router(
                    **common, sessions=sessions, outline_subject=owner),
            )
            app.mount("/assets", StaticFiles(directory=DIST / "assets"),
                      name="frontend-assets")

            @app.get("/{frontend_path:path}", include_in_schema=False)
            async def frontend(frontend_path: str):
                if frontend_path.startswith("api/"):
                    raise HTTPException(404)
                return FileResponse(DIST / "index.html", media_type="text/html")

            server = uvicorn.Server(uvicorn.Config(
                app, log_level="critical", access_log=False,
                proxy_headers=False, lifespan="on",
                timeout_graceful_shutdown=5))
            worker = Thread(target=lambda: server.run(sockets=[reservation]),
                            daemon=False)
            worker.start()
            try:
                deadline = monotonic() + 15
                while not server.started:
                    if not worker.is_alive() or monotonic() > deadline:
                        raise RuntimeError("SOL-03 Edge server did not start")
                    sleep(.05)
                result = subprocess.run(
                    ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                     origin, str(project), str(other_project), str(outline),
                     str(version), str(customer)],
                    check=False, timeout=180, capture_output=True, text=True,
                    encoding="utf-8", env={
                        **os.environ,
                        "PLM_BROWSER_SYNTHETIC_PASSWORD": login_fixture.PASSWORD,
                        "PLM_BROWSER_MANAGER_NAME": login_fixture.MANAGER_NAME,
                        "PLM_BROWSER_CUSTOMER_NAME": login_fixture.MEMBER_NAME,
                    })
                if result.returncode:
                    raise RuntimeError("SOL-03 Edge proof failed: "
                                       f"{result.stdout[-5000:]} {result.stderr[-5000:]}")
                print(result.stdout.strip(), flush=True)
            finally:
                server.should_exit = True; worker.join(timeout=15)
                if worker.is_alive():
                    raise RuntimeError("SOL-03 Edge server did not stop")
        with psycopg.connect(**connection) as db:
            state = db.execute(
                "SELECT v.version_state,v.review_ref,v.review_round_ref,"
                "o.current_approved_version_ref FROM plm.sol_outline_versions v "
                "JOIN plm.sol_outlines o ON o.solution_outline_id=v.solution_outline_id "
                "WHERE v.solution_outline_version_id=%s", (version,)).fetchone()
            assert state[0] == "APPROVED" and state[3] == version, state
            review, round_id = state[1:3]
            counts = db.execute(
                "SELECT "
                "(SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s),"
                "(SELECT count(*) FROM plm.rvw_review_decisions WHERE review_round_id=%s),"
                "(SELECT count(*) FROM plm.sol_outline_review_state_results "
                " WHERE solution_outline_version_id=%s),"
                "(SELECT count(*) FROM plm.aud_events "
                " WHERE action='SOLUTION_OUTLINE_VERSION_APPROVED' "
                " AND target_version_id=%s)",
                (review, round_id, version, version)).fetchone()
            assert counts == (1, 1, 2, 1), counts
    print("SOL_03_A06_P04_P03_A05_P02_A03_OUTLINE_EDGE_BROWSER_PASS")


if __name__ == "__main__":
    def hooked(case: str, **context):
        assert case == "APPROVE"
        full.original_terminal(case, **context)
        on_browser(**context)

    full.terminal._terminal = hooked
    full.terminal._run("APPROVE")
