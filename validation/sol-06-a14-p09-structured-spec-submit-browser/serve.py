"""Win11 Edge/production Vue/FastAPI/PG proof for SOL-06 submit-review."""

from __future__ import annotations

import importlib.util
import os
import secrets
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
    create_windows_structured_spec_read_router,
    create_windows_structured_spec_review_submission_router,
    create_windows_structured_spec_validate_router,
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
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
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


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "apps/frontend/dist"
SPEC = importlib.util.spec_from_file_location(
    "sol06_review_for_submit_browser",
    ROOT / "validation/sol-06-a14-p04-structured-spec-review/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
PASSWORD = secrets.token_urlsafe(24)
MANAGER_NAME = "Solution Review Browser Manager"
MEMBER_NAME = "Solution Review Browser Member"


def _hash(hasher: ScryptPasswordHasher):
    clear = bytearray(PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            return hasher.hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)


def _login_users(port, project):
    hasher = ScryptPasswordHasher()
    manager_hash, member_hash = _hash(hasher), _hash(hasher)
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin",
        dbname="postgres", autocommit=True,
    ) as db:
        department = db.execute(
            "SELECT department_id FROM plm.prj_departments "
            "WHERE project_id=%s ORDER BY department_id LIMIT 1",
            (project,)).fetchone()[0]
        browser_manager = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id",
            (MANAGER_NAME, MANAGER_NAME.casefold())).fetchone()[0]
        manager_credential = db.execute(
            "INSERT INTO plm.auth_password_credentials("
            "user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
            (browser_manager, manager_hash.password_hash,
             manager_hash.algorithm_id,
             '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,"
            "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
            (manager_credential, browser_manager))
        db.execute(
            "INSERT INTO plm.prj_project_members("
            "project_id,user_id,department_id,project_role) "
            "VALUES (%s,%s,%s,'PROJECT_MANAGER')",
            (project, browser_manager, department))
        member = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES (%s,%s) RETURNING user_id",
            (MEMBER_NAME, MEMBER_NAME.casefold())).fetchone()[0]
        member_credential = db.execute(
            "INSERT INTO plm.auth_password_credentials("
            "user_id,credential_version,password_hash,algorithm_id,parameter_set) "
            "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
            (member, member_hash.password_hash, member_hash.algorithm_id,
             '{"n":131072,"r":8,"p":1,"dklen":32}')).fetchone()[0]
        db.execute(
            "UPDATE plm.auth_users SET credential_version=1,"
            "active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
            (member_credential, member))
        db.execute(
            "INSERT INTO plm.prj_project_members("
            "project_id,user_id,department_id,project_role) "
            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
            (project, member, department))
    return hasher, member


def on_browser(
    *, port, runtime, project, other_project, manager, draft, audit,
    license_guard, documents, downloads, parse_results, **_unused,
) -> None:
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before SOL-06 submit browser proof")
    hasher, reviewer = _login_users(port, project)
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        before = db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        assert before == ("DRAFT", None, None), before
        assert db.execute(
            "SELECT count(*) FROM plm.rvw_reviews r JOIN plm.rvw_review_rounds rr "
            "ON rr.review_id=r.review_id WHERE r.subject_type='SOL-06' "
            "AND rr.subject_version_id=%s", (draft.structured_solution_spec_id,)
        ).fetchone()[0] == 0

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
            access=SqlAlchemyProjectMemberNames(), license_guard=license_guard,
            authorization=authorization,
            repository=SqlAlchemyProjectMemberReadRepository())
        common = dict(runtime=runtime, sessions=sessions, origins=origins,
                      license_guard=license_guard)
        app = create_app(
            login_router=create_login_router(
                login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            project_member_read_router=create_project_member_read_router(
                sessions=sessions, members=member_reads, origins=origins,
                cursors=MemberListCursorCodec(b"m" * 32)),
            solution_structured_spec_read_router=(
                create_windows_structured_spec_read_router(**common)),
            solution_structured_spec_validate_router=(
                create_windows_structured_spec_validate_router(
                    **common, audit=audit, documents=documents,
                    downloads=downloads, parse_results=parse_results)),
            solution_structured_spec_review_submission_router=(
                create_windows_structured_spec_review_submission_router(
                    **common, audit=audit, documents=documents,
                    downloads=downloads, parse_results=parse_results)),
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
                    raise RuntimeError("SOL-06 submit browser preview did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project),
                 str(draft.structured_solution_spec_id),
                 str(draft.spec_series_id), str(reviewer)],
                check=False, timeout=150, capture_output=True, text=True,
                encoding="utf-8", env={
                    **os.environ,
                    "PLM_BROWSER_SYNTHETIC_PASSWORD": PASSWORD,
                    "PLM_BROWSER_MANAGER_NAME": MANAGER_NAME,
                    "PLM_BROWSER_MEMBER_NAME": MEMBER_NAME,
                })
            if result.returncode:
                raise RuntimeError(
                    "SOL-06 submit browser proof failed: "
                    f"{result.stdout[-5000:]} {result.stderr[-5000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True; worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("SOL-06 submit browser preview did not stop")

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        state = db.execute(
            "SELECT version_state,review_ref,review_round_ref FROM "
            "plm.sol_structured_specs WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        assert state[0] == "IN_REVIEW" and state[1] and state[2], state
        counts = db.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_reviews WHERE review_id=%s "
            "AND subject_type='SOL-06' AND subject_id=%s),"
            "(SELECT count(*) FROM plm.rvw_review_rounds WHERE review_round_id=%s "
            "AND subject_version_id=%s),"
            "(SELECT count(*) FROM plm.sol_spec_review_state_results WHERE "
            "structured_solution_spec_id=%s AND event_type='START'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "operation='V1_SOL_SPEC_SUBMIT_REVIEW'),"
            "(SELECT count(*) FROM plm.aud_events WHERE target_object_id IN (%s,%s) "
            "AND action IN ('REVIEW_CREATED','REVIEW_STARTED'))",
            (state[1], draft.spec_series_id, state[2],
             draft.structured_solution_spec_id,
             draft.structured_solution_spec_id, state[1], state[2])
        ).fetchone()
        assert counts == (1, 1, 1, 1, 2), counts
    print(
        "SOL_06_A14_P09_SUBMIT_BROWSER_PASS: Win11 Edge production Vue/FastAPI/"
        "PG18.6 manager-only current validation, active reviewer, exact pending "
        "Key/body, 201/replay, cross-project clear and unique database facts")


def after_specs(*, created: dict[str, object], **specs) -> None:
    prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"],
        on_review=lambda **review: prior.on_review(
            **review, on_submit=on_browser))


if __name__ == "__main__":
    prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs: prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                after_specs(created=created, **specs))))
