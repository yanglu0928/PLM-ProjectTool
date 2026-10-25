"""Disposable Win11 Edge/PG18.6 manager Section submit-review proof."""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
import uuid

import psycopg
import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import create_windows_project_review_read_router
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_read_router,
    create_windows_section_version_read_router,
    create_windows_section_version_validate_router,
    create_windows_section_review_submission_router,
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
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "apps/frontend/dist"


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prior = _load("section_submit_for_manager_edge",
              "validation/sol-05-a04-p13-p05-p03-section-review-submit-windows/verify.py")
login_fixture = _load("sol06_login_for_section_manager_edge",
                      "validation/sol-06-a14-p09-structured-spec-submit-browser/serve.py")


def on_manager(*, port, runtime, project, other_project, draft, token, csrf,
               audit, license_guard, documents, downloads, parse_results,
               **context):
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before Section manager browser proof")
    prior.prior._fit_owner(
        port=port, runtime=runtime, project=project, draft=draft,
        token=token, csrf=csrf, audit=audit, license_guard=license_guard,
        documents=documents, downloads=downloads,
        parse_results=parse_results, other_project=other_project, **context,
    )
    connection = dict(host="127.0.0.1", port=port,
                      user="poc_admin", dbname="postgres")
    with psycopg.connect(**connection) as db:
        section, version, requirement, req_version = db.execute(
            "SELECT v.solution_section_id,v.solution_section_version_id,"
            "r.requirement_id,r.requirement_version_id "
            "FROM plm.sol_section_versions v JOIN plm.sol_section_spec_refs s "
            "ON s.solution_section_version_id=v.solution_section_version_id "
            "JOIN plm.sol_section_requirement_refs r "
            "ON r.solution_section_version_id=v.solution_section_version_id "
            "WHERE v.project_id=%s AND s.fit_rationale IS NOT NULL "
            "ORDER BY v.version_no DESC LIMIT 1", (project,),
        ).fetchone()
        customer = prior._seed_customer(db=db, project=project)
    creator, _ = prior._trace_services(
        runtime=runtime, license_guard=license_guard, audit=audit)
    creator.create_refs(prior.CreateTraceLinkRefs(
        token, csrf, uuid.uuid4(), project,
        prior.TraceResourceVersionRef("REQ-03", requirement, req_version),
        prior.TraceResourceVersionRef("SOL-05", section, version),
        "IMPLEMENTS"), idempotency_key="section-manager-edge-trace-0001")
    hasher, _ = login_fixture._login_users(port, project)

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0)); reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = LoginOriginPolicy([origin])
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=login_fixture.SqlAlchemySessionRepository(),
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
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository())
        member_reads = ProjectMemberReadService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyProjectMemberNames(), license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyProjectMemberReadRepository())
        common = dict(runtime=runtime, sessions=sessions, origins=origins,
                      license_guard=license_guard)
        proof = dict(common, audit=audit, documents=documents,
                     downloads=downloads, parse_results=parse_results)
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            project_member_read_router=create_project_member_read_router(
                sessions=sessions, members=member_reads, origins=origins,
                cursors=MemberListCursorCodec(b"m" * 32)),
            solution_section_read_router=create_windows_section_read_router(**common),
            solution_section_version_read_router=create_windows_section_version_read_router(
                **common, cursors=SectionVersionListCursorCodec(b"h" * 32)),
            solution_section_version_validate_router=create_windows_section_version_validate_router(
                **proof),
            solution_section_review_submission_router=create_windows_section_review_submission_router(
                **proof),
            review_read_router=create_windows_project_review_read_router(
                runtime=runtime, origins=origins, license_guard=license_guard,
                audit=audit, documents=documents, downloads=downloads,
                parse_results=parse_results),
        )
        app.mount("/assets", StaticFiles(directory=DIST / "assets"),
                  name="frontend-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend(frontend_path: str):
            if frontend_path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(DIST / "index.html", media_type="text/html")

        server = uvicorn.Server(uvicorn.Config(
            app, log_level="critical", access_log=False, proxy_headers=False,
            lifespan="on", timeout_graceful_shutdown=5))
        worker = Thread(target=lambda: server.run(sockets=[reservation]),
                        daemon=False)
        worker.start()
        try:
            deadline = monotonic() + 15
            while not server.started:
                if not worker.is_alive() or monotonic() > deadline:
                    raise RuntimeError("Section manager browser server did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(section),
                 str(version), str(customer)],
                check=False, timeout=150, capture_output=True, text=True,
                encoding="utf-8", env={
                    **os.environ,
                    "PLM_BROWSER_SYNTHETIC_PASSWORD": login_fixture.PASSWORD,
                    "PLM_BROWSER_MANAGER_NAME": login_fixture.MANAGER_NAME,
                })
            if result.returncode:
                raise RuntimeError("Section manager browser proof failed: "
                                   f"{result.stdout[-5000:]} {result.stderr[-5000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True; worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Section manager browser server did not stop")
    with psycopg.connect(**connection) as db:
        state = db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_section_versions WHERE solution_section_version_id=%s",
            (version,)).fetchone()
        assert state[0] == "IN_REVIEW" and state[1] and state[2], state
        review, round_id = state[1:]
        counts = db.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s),"
            "(SELECT count(*) FROM plm.rvw_review_rounds WHERE review_round_id=%s),"
            "(SELECT count(*) FROM plm.sol_section_review_state_results "
            " WHERE solution_section_version_id=%s AND event_type='START'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            " operation='V1_SOL_SECTION_VERSION_SUBMIT_REVIEW' AND result_ref_id=%s),"
            "(SELECT count(*) FROM plm.aud_events WHERE action='REVIEW_STARTED' "
            " AND target_object_id=%s)",
            (review, round_id, version, round_id, round_id),
        ).fetchone()
        assert counts == (1, 1, 1, 1, 1), counts
    print("SOL_05_A04_P13_P06_P02_P03_A02_SECTION_MANAGER_BROWSER_PASS")


if __name__ == "__main__":
    fixture = prior.prior.fixture
    fixture._after_submit = on_manager
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
