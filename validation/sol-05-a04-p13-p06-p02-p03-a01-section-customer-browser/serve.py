"""Disposable Win11 Edge/PG18.6 synthetic Section customer Review proof."""

from __future__ import annotations

import importlib.util
import os
import secrets
import socket
import subprocess
import uuid
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import psycopg
import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.api.read_projects import create_project_read_router
from plm_assistant.modules.project.application.read_projects import ProjectReadService
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.project.infrastructure.read_repository import SqlAlchemyProjectReadRepository
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "apps/frontend/dist"
SPEC = importlib.util.spec_from_file_location(
    "section_submit_for_customer_edge",
    ROOT / "validation/sol-05-a04-p13-p05-p03-section-review-submit-windows/verify.py",
)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
PASSWORD = secrets.token_urlsafe(24)
MEMBER_NAME = "Synthetic Section Customer Browser"


class _CursorResolver:
    def resolve_key(self, key_ref: str) -> bytes:
        assert key_ref == "review-list-cursor-v1"
        return b"r" * 32


def _make_customer_login(port, project):
    hasher = ScryptPasswordHasher()
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        section, version, review, round_id = db.execute(
            "SELECT solution_section_id,solution_section_version_id,"
            "review_ref,review_round_ref FROM plm.sol_section_versions "
            "WHERE project_id=%s AND version_state='IN_REVIEW' "
            "ORDER BY version_no DESC LIMIT 1", (project,),
        ).fetchone()
        reviewer = db.execute(
            "SELECT reviewer_id FROM plm.rvw_review_assignments "
            "WHERE review_round_id=%s", (round_id,),
        ).fetchone()[0]
    return hasher, section, version, review, round_id, reviewer


def _seed_customer(*, db, project):
    """Replace only the disposable fixture's dummy hash before its INSERT."""
    reviewer, credential = uuid.uuid4(), uuid.uuid4()
    department = db.execute(
        "SELECT department_id FROM plm.prj_departments "
        "WHERE project_id=%s LIMIT 1", (project,),
    ).fetchone()
    department_id = department[0] if department else uuid.uuid4()
    clear = bytearray(PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            hashed = ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    with db.transaction():
        db.execute("SET LOCAL session_replication_role='replica'")
        if department is None:
            db.execute(
                "INSERT INTO plm.prj_departments(department_id,project_id,"
                "department_code,department_code_normalized,name) "
                "VALUES (%s,%s,'CUSTOMER','customer','Customer Team')",
                (department_id, project),
            )
        db.execute(
            "INSERT INTO plm.auth_users(user_id,username_display,"
            "username_normalized,state,credential_version,"
            "active_password_credential_id) VALUES (%s,%s,%s,'ENABLED',1,%s)",
            (reviewer, MEMBER_NAME, MEMBER_NAME.casefold(), credential),
        )
        db.execute(
            "INSERT INTO plm.auth_password_credentials("
            "password_credential_id,user_id,credential_version,password_hash,"
            "algorithm_id,parameter_set) VALUES (%s,%s,1,%s,%s,%s::jsonb)",
            (credential, reviewer, hashed.password_hash, hashed.algorithm_id,
             '{"n":131072,"r":8,"p":1,"dklen":32}'),
        )
        db.execute(
            "INSERT INTO plm.prj_project_members(project_id,user_id,"
            "department_id,project_role) VALUES (%s,%s,%s,'CUSTOMER_MEMBER')",
            (project, reviewer, department_id),
        )
    return reviewer


def on_customer(*, port, runtime, project, other_project, audit,
                license_guard, documents, downloads, parse_results, **context):
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before Section customer browser proof")
    prior._after_submit(
        port=port, runtime=runtime, project=project,
        other_project=other_project, audit=audit,
        license_guard=license_guard, documents=documents,
        downloads=downloads, parse_results=parse_results, **context,
    )
    hasher, section, version, review, round_id, reviewer = _make_customer_login(
        port, project,
    )
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0)); reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = LoginOriginPolicy([origin])
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(hasher), audit=audit,
            idempotency=SqlAlchemyIdempotencyReceipts(),
        )
        login = LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=LoginRateLimiter(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyLoginRateRepository(),
            ),
            identity=SqlAlchemyLoginIdentity(),
            missing_verifier=ScryptMissingIdentityVerifier(hasher),
            sessions=sessions, audit=audit,
        )
        views = SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work,
            projects=SqlAlchemyAuthorizedProjects(),
        )
        common = dict(
            runtime=runtime, origins=origins, license_guard=license_guard,
            audit=audit, documents=documents, downloads=downloads,
            parse_results=parse_results,
        )
        app = create_app(
            login_router=create_login_router(
                login=login, origins=origins, views=views,
            ),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views,
            ),
            project_read_router=create_project_read_router(
                sessions=sessions, origins=origins,
                projects=ProjectReadService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectReadAccess(),
                    license_guard=license_guard,
                    repository=SqlAlchemyProjectReadRepository(),
                ),
            ),
            review_list_router=create_windows_project_review_list_router(
                **common,
                cursors=create_windows_review_list_cursor_codec(
                    resolver=_CursorResolver(),
                ),
            ),
            review_read_router=create_windows_project_review_read_router(**common),
            review_command_router=create_windows_project_review_router(
                **common, sessions=sessions,
            ),
            solution_section_read_router=create_windows_section_read_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard,
            ),
            solution_section_version_read_router=create_windows_section_version_read_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard,
                cursors=SectionVersionListCursorCodec(b"h" * 32),
            ),
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
            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5,
        ))
        worker = Thread(target=lambda: server.run(sockets=[reservation]),
                        daemon=False)
        worker.start()
        try:
            deadline = monotonic() + 15
            while not server.started:
                if not worker.is_alive() or monotonic() > deadline:
                    raise RuntimeError("Section customer browser server did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(review),
                 str(round_id), str(section), str(version), str(reviewer)],
                check=False, timeout=150, capture_output=True, text=True,
                encoding="utf-8", env={
                    **os.environ,
                    "PLM_BROWSER_SYNTHETIC_PASSWORD": PASSWORD,
                    "PLM_BROWSER_MEMBER_NAME": MEMBER_NAME,
                },
            )
            if result.returncode:
                raise RuntimeError(
                    "Section customer browser proof failed: "
                    f"{result.stdout[-5000:]} {result.stderr[-5000:]}",
                )
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True; worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Section customer browser server did not stop")
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as db:
        state = db.execute(
            "SELECT v.version_state,s.current_approved_version_ref,"
            "r.review_state,rr.round_state FROM plm.sol_section_versions v "
            "JOIN plm.sol_sections s ON s.solution_section_id=v.solution_section_id "
            "JOIN plm.rvw_reviews r ON r.review_id=v.review_ref "
            "JOIN plm.rvw_review_rounds rr ON rr.review_round_id=v.review_round_ref "
            "WHERE v.solution_section_version_id=%s", (version,),
        ).fetchone()
        assert state == ("APPROVED", version, "APPROVED", "APPROVED"), state
        decisions = db.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s "
            "AND review_round_id=%s AND reviewer_id=%s AND decision='APPROVE'",
            (review, round_id, reviewer),
        ).fetchone()[0]
        assert decisions == 1, decisions
    print("SOL_05_A04_P13_P06_P02_P03_A01_SECTION_CUSTOMER_BROWSER_PASS")


if __name__ == "__main__":
    prior._seed_customer = _seed_customer
    fixture = prior.prior.fixture
    fixture._after_submit = on_customer
    fixture.prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        fixture.prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            fixture.prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                fixture._after_specs(created=created, **specs))))
