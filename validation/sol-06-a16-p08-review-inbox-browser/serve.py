"""Win11 Edge/Vue/FastAPI/PG proof of project Review inbox discovery."""

from __future__ import annotations

import importlib.util
import os
import socket
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import psycopg
import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_list_router,
    create_windows_project_review_read_router,
    create_windows_project_review_router,
)
from plm_assistant.entrypoints.windows_review_list_cursor import (
    create_windows_review_list_cursor_codec,
)
from plm_assistant.modules.project.api.read_projects import create_project_read_router
from plm_assistant.modules.project.application.read_projects import ProjectReadService
from plm_assistant.modules.project.infrastructure.read_repository import (
    SqlAlchemyProjectReadRepository,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_reviewer_for_inbox_browser",
    ROOT / "validation/sol-06-a15-p06-structured-spec-review-browser/serve.py",
)
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


class _CursorResolver:
    def resolve_key(self, key_ref: str) -> bytes:
        assert key_ref == "review-list-cursor-v1"
        return b"r" * 32


def on_browser(*, port, runtime, project, other_project, draft, audit,
               license_guard, documents, downloads, parse_results, **context):
    # Existing manager Edge proof submits the fixed SOL-06 version. Leave it active.
    prior.prior.on_browser(
        port=port, runtime=runtime, project=project,
        other_project=other_project, draft=draft, audit=audit,
        license_guard=license_guard, documents=documents,
        downloads=downloads, parse_results=parse_results, **context,
    )
    review_id, round_id, reviewer = prior._review_context(port, project, draft)
    hasher = prior.prior.ScryptPasswordHasher()

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0)); reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = prior.prior.LoginOriginPolicy([origin])
        sessions = prior.prior.SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=prior.prior.SqlAlchemySessionRepository(),
            issue_access=prior.prior.SqlAlchemyPasswordIssueAccess(hasher),
            audit=audit,
            idempotency=prior.prior.SqlAlchemyIdempotencyReceipts(),
        )
        login = prior.prior.LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=prior.prior.LoginRateLimiter(
                unit_of_work=runtime.unit_of_work,
                repository=prior.prior.SqlAlchemyLoginRateRepository(),
            ),
            identity=prior.prior.SqlAlchemyLoginIdentity(),
            missing_verifier=prior.prior.ScryptMissingIdentityVerifier(hasher),
            sessions=sessions, audit=audit,
        )
        views = prior.prior.SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work,
            projects=prior.prior.SqlAlchemyAuthorizedProjects(),
        )
        common = dict(
            runtime=runtime, origins=origins, license_guard=license_guard,
            audit=audit, documents=documents, downloads=downloads,
            parse_results=parse_results,
        )
        app = create_app(
            login_router=prior.prior.create_login_router(
                login=login, origins=origins, views=views,
            ),
            session_router=prior.prior.create_session_read_router(
                sessions=sessions, origins=origins, views=views,
            ),
            project_read_router=create_project_read_router(
                sessions=sessions, origins=origins,
                projects=ProjectReadService(
                    unit_of_work=runtime.unit_of_work,
                    access=prior.prior.SqlAlchemyProjectReadAccess(),
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
            review_read_router=create_windows_project_review_read_router(
                **common,
            ),
            review_command_router=create_windows_project_review_router(
                **common, sessions=sessions,
            ),
            solution_structured_spec_read_router=(
                prior.prior.create_windows_structured_spec_read_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=license_guard,
                )
            ),
        )
        app.mount("/assets", prior.prior.StaticFiles(
            directory=prior.prior.DIST / "assets"), name="frontend-assets",
        )

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend(frontend_path: str):
            if frontend_path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(prior.prior.DIST / "index.html", media_type="text/html")

        server = uvicorn.Server(uvicorn.Config(
            app, log_level="critical", access_log=False, proxy_headers=False,
            lifespan="on", timeout_graceful_shutdown=5,
        ))
        worker = Thread(target=lambda: server.run(sockets=[reservation]), daemon=False)
        worker.start()
        try:
            deadline = monotonic() + 15
            while not server.started:
                if not worker.is_alive() or monotonic() > deadline:
                    raise RuntimeError("Review inbox browser server did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(review_id),
                 str(round_id), str(reviewer)],
                check=False, timeout=150, capture_output=True, text=True,
                encoding="utf-8", env={
                    **os.environ,
                    "PLM_BROWSER_SYNTHETIC_PASSWORD": prior.prior.PASSWORD,
                    "PLM_BROWSER_MEMBER_NAME": prior.prior.MEMBER_NAME,
                },
            )
            if result.returncode:
                raise RuntimeError(
                    "Review inbox browser proof failed: "
                    f"{result.stdout[-5000:]} {result.stderr[-5000:]}",
                )
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True; worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Review inbox browser server did not stop")

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        state = database.execute(
            "SELECT review_state FROM plm.rvw_reviews WHERE review_id=%s",
            (review_id,),
        ).fetchone()
        decisions = database.execute(
            "SELECT count(*) FROM plm.rvw_review_decisions WHERE review_id=%s "
            "AND review_round_id=%s AND reviewer_id=%s AND decision='APPROVE'",
            (review_id, round_id, reviewer),
        ).fetchone()[0]
        assert state == ("APPROVED",) and decisions == 1, (state, decisions)
    print(
        "SOL_06_A16_P08_REVIEW_INBOX_BROWSER_PASS: Win11 Edge production Vue/"
        "FastAPI/PG18.6 server-discovered pending, one decision, pending gone, "
        "history retained and cross-project cleared",
    )


def after_specs(*, created: dict[str, object], **specs) -> None:
    prior.prior.prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.prior.prior.on_review(
            **review, on_submit=on_browser,
        ),
    )


if __name__ == "__main__":
    prior.prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                after_specs(created=created, **specs),
            ),
        ),
    )
