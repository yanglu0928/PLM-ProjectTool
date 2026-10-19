"""Win11 Edge/production Vue/FastAPI/PG proof for SOL-06 Reviewer UI."""

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
from fastapi.staticfiles import StaticFiles

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_project_review import (
    create_windows_project_review_read_router,
    create_windows_project_review_router,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sol06_submit_for_reviewer_browser",
    ROOT / "validation/sol-06-a14-p09-structured-spec-submit-browser/serve.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)


def _review_context(port, project, draft):
    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        review_id, round_id = database.execute(
            "SELECT review_ref,review_round_ref FROM plm.sol_structured_specs "
            "WHERE structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        reviewer = database.execute(
            "SELECT user_id FROM plm.auth_users WHERE username_normalized=%s",
            (prior.MEMBER_NAME.casefold(),)).fetchone()[0]
    return review_id, round_id, reviewer


def on_browser(*, port, runtime, project, other_project, draft, audit,
               license_guard, documents, downloads, parse_results, **context):
    # First prove the actual manager validation/submit page and leave one IN_REVIEW fact.
    prior.on_browser(
        port=port, runtime=runtime, project=project,
        other_project=other_project, draft=draft, audit=audit,
        license_guard=license_guard, documents=documents,
        downloads=downloads, parse_results=parse_results, **context)
    review_id, round_id, reviewer = _review_context(port, project, draft)
    hasher = prior.ScryptPasswordHasher()

    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0)); reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = prior.LoginOriginPolicy([origin])
        sessions = prior.SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=prior.SqlAlchemySessionRepository(),
            issue_access=prior.SqlAlchemyPasswordIssueAccess(hasher), audit=audit,
            idempotency=prior.SqlAlchemyIdempotencyReceipts())
        login = prior.LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=prior.LoginRateLimiter(
                unit_of_work=runtime.unit_of_work,
                repository=prior.SqlAlchemyLoginRateRepository()),
            identity=prior.SqlAlchemyLoginIdentity(),
            missing_verifier=prior.ScryptMissingIdentityVerifier(hasher),
            sessions=sessions, audit=audit)
        views = prior.SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work,
            projects=prior.SqlAlchemyAuthorizedProjects())
        common = dict(
            runtime=runtime, origins=origins, license_guard=license_guard,
            audit=audit, documents=documents, downloads=downloads,
            parse_results=parse_results)
        app = create_app(
            login_router=prior.create_login_router(
                login=login, origins=origins, views=views),
            session_router=prior.create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            review_read_router=create_windows_project_review_read_router(
                **common),
            review_command_router=create_windows_project_review_router(
                **common, sessions=sessions),
            solution_structured_spec_read_router=(
                prior.create_windows_structured_spec_read_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=license_guard)),
        )
        app.mount("/assets", prior.StaticFiles(directory=prior.DIST / "assets"),
                  name="frontend-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend(frontend_path: str):
            if frontend_path.startswith("api/"):
                raise HTTPException(404)
            return FileResponse(prior.DIST / "index.html", media_type="text/html")

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
                    raise RuntimeError("SOL-06 Reviewer browser server did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(review_id),
                 str(round_id), str(draft.structured_solution_spec_id),
                 str(reviewer)],
                check=False, timeout=150, capture_output=True, text=True,
                encoding="utf-8", env={
                    **os.environ,
                    "PLM_BROWSER_SYNTHETIC_PASSWORD": prior.PASSWORD,
                    "PLM_BROWSER_MEMBER_NAME": prior.MEMBER_NAME,
                })
            if result.returncode:
                raise RuntimeError(
                    "SOL-06 Reviewer browser proof failed: "
                    f"{result.stdout[-5000:]} {result.stderr[-5000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True; worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("SOL-06 Reviewer browser server did not stop")

    with psycopg.connect(
        host="127.0.0.1", port=port, user="poc_admin", dbname="postgres",
    ) as database:
        state = database.execute(
            "SELECT s.version_state,r.review_state,rr.round_state,rr.lock_version "
            "FROM plm.sol_structured_specs s JOIN plm.rvw_reviews r "
            "ON r.review_id=s.review_ref JOIN plm.rvw_review_rounds rr "
            "ON rr.review_round_id=s.review_round_ref "
            "WHERE s.structured_solution_spec_id=%s",
            (draft.structured_solution_spec_id,)).fetchone()
        assert state == ("APPROVED", "APPROVED", "APPROVED", 1), state
        counts = database.execute(
            "SELECT "
            "(SELECT count(*) FROM plm.rvw_review_decisions WHERE "
            "review_id=%s AND review_round_id=%s AND reviewer_id=%s "
            "AND decision='APPROVE'),"
            "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE "
            "actor_id=%s AND project_id=%s AND operation='V1_REVIEW_DECIDE' "
            "AND result_ref_type='V1_REVIEW_TRANSITION' AND result_ref_id IN "
            "(SELECT round_event_id FROM plm.rvw_round_events WHERE "
            "review_id=%s AND review_round_id=%s "
            "AND event_type='DECISION_RECORDED')),"
            "(SELECT count(*) FROM plm.sol_spec_review_state_results WHERE "
            "structured_solution_spec_id=%s AND event_type IN ('START','APPROVED')),"
            "(SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
            "AND action='REVIEW_DECISION_RECORDED'),"
            "(SELECT count(*) FROM plm.aud_events WHERE target_object_id=%s "
            "AND target_version_id=%s "
            "AND action='STRUCTURED_SPEC_VERSION_APPROVED')",
            (review_id, round_id, reviewer,
             reviewer, project, review_id, round_id,
             draft.structured_solution_spec_id, round_id,
             draft.spec_series_id, draft.structured_solution_spec_id)).fetchone()
        assert counts == (1, 1, 2, 1, 1), counts
    print(
        "SOL_06_A15_P06_REVIEW_BROWSER_PASS: Win11 Edge production Vue/"
        "FastAPI/PG18.6 known receipt, assigned reviewer, offline exact retry, "
        "APPROVED terminal reread, cross-project clear and unique facts")


def after_specs(*, created: dict[str, object], **specs) -> None:
    prior.prior.prior.on_trace(
        **specs, csrf=created["csrf"], member_csrf=created["member_csrf"],
        audit=created["audit"], license_guard=created["license_guard"],
        documents=created["documents"], downloads=created["downloads"],
        parse_results=created["parse_results"], evidence=created["evidence"],
        on_review=lambda **review: prior.prior.on_review(
            **review, on_submit=on_browser))


if __name__ == "__main__":
    prior.prior.prior.prior.prior.prior.prior.main(
        on_created=lambda **kwargs:
        prior.prior.prior.prior.prior.prior.on_created(
            **kwargs, on_http=lambda **created:
            prior.prior.prior.prior.prior.on_created(
                **created, on_http=lambda **specs:
                after_specs(created=created, **specs))))
