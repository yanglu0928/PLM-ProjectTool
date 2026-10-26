"""Run a real Edge/HTTP/PG18 PlanVersion flow over owned synthetic fixtures."""

from __future__ import annotations

import argparse
import importlib.util
import socket
import threading
import time
import uuid
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "plan_version_edge_owner_fixture",
    ROOT / "validation/plan-02-a04-p03-owner-transaction-pg/verify.py",
)
assert SPEC and SPEC.loader
owner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owner)
full = owner.full
RUN_ROOT: Path | None = None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve(context: dict[str, object], host_port: int):
    from fastapi import APIRouter
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles
    from plm_assistant.entrypoints.api import create_app
    from plm_assistant.entrypoints.windows_plan import create_windows_plan_read_routers
    from plm_assistant.entrypoints.windows_plan_cursor import create_windows_plan_list_cursor_codec
    from plm_assistant.entrypoints.windows_plan_version import (
        create_windows_plan_version_create_router,
        create_windows_plan_version_list_router,
        create_windows_plan_version_read_router,
        create_windows_plan_version_validation_composition,
        create_windows_plan_version_review_submission_router,
    )
    from plm_assistant.entrypoints.windows_plan_cursor import create_windows_plan_version_list_cursor_codec
    from plm_assistant.entrypoints.windows_solution_outline import (
        create_windows_outline_list_router, create_windows_outline_read_router,
        create_windows_outline_version_read_router,
        create_windows_section_read_router, create_windows_section_version_read_router,
        create_windows_structured_spec_read_router, create_windows_structured_spec_list_router,
    )
    from plm_assistant.entrypoints.windows_solution_outline_cursor import create_windows_outline_list_cursor_codec
    from plm_assistant.entrypoints.windows_solution_outline_version_cursor import create_windows_outline_version_list_cursor_codec
    from plm_assistant.entrypoints.windows_solution_section_version_cursor import create_windows_section_version_list_cursor_codec
    from plm_assistant.entrypoints.windows_solution_structured_spec_cursor import create_windows_structured_spec_list_cursor_codec
    from plm_assistant.entrypoints.windows_requirement import create_windows_requirement_routers
    from plm_assistant.entrypoints.windows_project_review import create_windows_project_review_read_router
    from plm_assistant.entrypoints.windows_project_member_cursor import create_windows_project_member_cursor_codec
    from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
    from plm_assistant.modules.auth.api.login import create_login_router
    from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimiter
    from plm_assistant.modules.auth.application.login_service import LoginService
    from plm_assistant.modules.auth.application.session_service import SessionService
    from plm_assistant.modules.auth.infrastructure.login_identity import SqlAlchemyLoginIdentity
    from plm_assistant.modules.auth.infrastructure.login_rate_repository import SqlAlchemyLoginRateRepository
    from plm_assistant.modules.auth.infrastructure.missing_identity_verifier import ScryptMissingIdentityVerifier
    from plm_assistant.modules.auth.infrastructure.password_issue_access import SqlAlchemyPasswordIssueAccess
    from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
    from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
    from plm_assistant.modules.auth.api.session import create_session_read_router
    from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
    from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
    from plm_assistant.modules.project.application.read_members import ProjectMemberReadService
    from plm_assistant.modules.project.infrastructure.member_read_repository import SqlAlchemyProjectMemberReadRepository
    from plm_assistant.modules.auth.infrastructure.project_member_names import SqlAlchemyProjectMemberNames
    from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
    from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
    from plm_assistant.modules.project.api.read_members import create_project_member_read_router
    from plm_assistant.modules.project.api.read_projects import create_project_read_router
    from plm_assistant.modules.project.application.read_projects import ProjectReadService
    from plm_assistant.modules.project.infrastructure.read_repository import SqlAlchemyProjectReadRepository
    from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess

    runtime, guard, audit = (context[key] for key in ("runtime", "license_guard", "audit"))
    origin = f"http://127.0.0.1:{host_port}"
    origins = LoginOriginPolicy([origin])
    hasher = ScryptPasswordHasher()
    sessions = SessionService(
        unit_of_work=runtime.unit_of_work,
        repository=SqlAlchemySessionRepository(),
        issue_access=SqlAlchemyPasswordIssueAccess(hasher), audit=audit,
    )
    resolver = type("SyntheticKeyResolver", (), {"resolve_key": lambda self, _ref: b"k" * 32})()
    plan_read, plan_list = create_windows_plan_read_routers(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        cursors=create_windows_plan_list_cursor_codec(resolver=resolver),
    )
    plan_version_list = create_windows_plan_version_list_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        cursors=create_windows_plan_version_list_cursor_codec(resolver=resolver),
    )
    plan_version_read = create_windows_plan_version_read_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
    )
    evidence = (context["documents"], context["downloads"], context["parse_results"])
    validation_router, validation_service = create_windows_plan_version_validation_composition(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        audit=audit, document_storage_root=Path(context["run_root"]),
        parse_result_storage_root=Path(context["run_root"]),
        documents=evidence[0], downloads=evidence[1], parse_results=evidence[2],
    )
    validation_router.include_router(create_windows_plan_version_review_submission_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        audit=audit, validation_service=validation_service,
    ))
    plan_version_create = create_windows_plan_version_create_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        audit=audit, document_storage_root=Path(context["run_root"]),
        parse_result_storage_root=Path(context["run_root"]),
        documents=evidence[0], downloads=evidence[1], parse_results=evidence[2],
    )
    outline_list = create_windows_outline_list_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        cursors=create_windows_outline_list_cursor_codec(resolver=resolver),
    )
    outline_read = create_windows_outline_read_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
    )
    outline_versions = create_windows_outline_version_read_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        cursors=create_windows_outline_version_list_cursor_codec(resolver=resolver),
    )
    section_read = create_windows_section_read_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
    )
    section_versions = create_windows_section_version_read_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        cursors=create_windows_section_version_list_cursor_codec(resolver=resolver),
    )
    spec_read = create_windows_structured_spec_read_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
    )
    spec_list = create_windows_structured_spec_list_router(
        runtime=runtime, sessions=sessions, origins=origins, license_guard=guard,
        cursors=create_windows_structured_spec_list_cursor_codec(resolver=resolver),
    )
    requirements = create_windows_requirement_routers(
        runtime, sessions=sessions, origins=origins, license_guard=guard,
        audit=audit, include_write=False, resolver=resolver,
    )
    member_reads = ProjectMemberReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectMemberNames(),
        license_guard=guard,
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ), repository=SqlAlchemyProjectMemberReadRepository(),
    )
    members = create_project_member_read_router(
        sessions=sessions, members=member_reads, origins=origins,
        cursors=create_windows_project_member_cursor_codec(resolver=resolver),
    )
    project_reads = ProjectReadService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectReadAccess(),
        license_guard=guard, repository=SqlAlchemyProjectReadRepository(),
    )
    projects = create_project_read_router(
        sessions=sessions, projects=project_reads, origins=origins,
    )
    from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
    from plm_assistant.modules.plan.application.plan_review_readiness import PlanVersionReviewReadinessService
    from plm_assistant.modules.plan.application.plan_version_review_terminal import PlanVersionReviewSubjectOwner
    from plm_assistant.modules.plan.infrastructure.plan_review_readiness_repository import SqlAlchemyPlanVersionReviewReadinessRepository
    from plm_assistant.modules.plan.infrastructure.plan_review_subject_repository import SqlAlchemyPlanReviewSubjectRepository
    from plm_assistant.modules.project.application.reviewers import ProjectReviewerQualificationService
    from plm_assistant.modules.auth.infrastructure.review_user_access import SqlAlchemyReviewUserAccess
    from plm_assistant.modules.review.application.subject_registry import ProjectReviewSubjectRegistry
    from plm_assistant.modules.review.application.read_service import ReviewReadService
    from plm_assistant.modules.review.infrastructure.read_repository import SqlAlchemyReviewSnapshotReadRepository
    from plm_assistant.modules.review.api.read import create_review_read_router
    project_repository = SqlAlchemyProjectAuthorizationRepository()
    reviewers = ProjectReviewerQualificationService(
        users=SqlAlchemyReviewUserAccess(), projects=project_repository,
    )
    review_owner = PlanVersionReviewSubjectOwner(
        repository=SqlAlchemyPlanReviewSubjectRepository(), reviewers=reviewers,
        readiness=PlanVersionReviewReadinessService(
            repository=SqlAlchemyPlanVersionReviewReadinessRepository(),
            evaluator=validation_service,
        ), audit=audit,
    )
    review_reads = ReviewReadService(
        unit_of_work=runtime.unit_of_work, sessions=SqlAlchemyProjectReadAccess(),
        projects=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work, repository=project_repository,
        ), license_guard=guard, repository=SqlAlchemyReviewSnapshotReadRepository(),
        subjects=review_owner,
    )
    review_read = create_review_read_router(origins=origins, reads=review_reads)
    session_read = create_session_read_router(
        sessions=sessions,
        views=SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work, projects=SqlAlchemyAuthorizedProjects(),
        ), origins=origins,
    )
    login = LoginService(
        unit_of_work=runtime.unit_of_work,
        rate=LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                              repository=SqlAlchemyLoginRateRepository()),
        identity=SqlAlchemyLoginIdentity(),
        missing_verifier=ScryptMissingIdentityVerifier(hasher),
        sessions=sessions, audit=audit,
    )
    routers = APIRouter()
    for router in (plan_read, plan_list, plan_version_list, plan_version_read,
                   validation_router, plan_version_create, outline_list, outline_read,
                   outline_versions, section_read, section_versions, spec_read, spec_list,
                   requirements.requirements, requirements.versions,
                   projects, members, review_read):
        routers.include_router(router)
    session_views = SqlAlchemySessionView(
        unit_of_work=runtime.unit_of_work, projects=SqlAlchemyAuthorizedProjects(),
    )
    app = create_app(
        login_router=create_login_router(login=login, origins=origins, views=session_views),
        session_router=session_read,
    )
    app.include_router(routers)
    dist = ROOT / "apps/frontend/dist"
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="frontend-assets")

    @app.get("/{frontend_path:path}", include_in_schema=False)
    async def frontend(frontend_path: str):
        if frontend_path.startswith("api/"):
            raise HTTPException(404)
        return FileResponse(dist / "index.html", media_type="text/html")

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=host_port,
                                           log_level="error", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        raise RuntimeError("synthetic PlanVersion HTTP server failed to start")
    return server, thread


def _edge_fixture(context: dict[str, object]) -> None:
    import json
    import psycopg
    from plm_assistant.modules.auth.infrastructure.project_write_access import SqlAlchemyProjectWriteAccess
    from plm_assistant.modules.plan.application.create_plan import CreatePlan, PlanCreateService
    from plm_assistant.modules.plan.infrastructure.create_repository import SqlAlchemyPlanCreateRepository
    from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
    from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
    from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
    from plm_assistant.modules.plan.application.create_plan import PlanCreateError
    from plm_assistant.modules.plan.api.list_cursor import PlanListCursorCodec
    from plm_assistant.modules.plan.infrastructure.read_repository import SqlAlchemyPlanReadRepository
    from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess

    project, runtime = context["project"], context["runtime"]
    # Disposable identities let the real Vue login establish its in-memory CSRF state.
    password = "Synthetic-PlanVersion-Edge-Only-2026"
    from plm_assistant.modules.auth.infrastructure.scrypt_password import ScryptPasswordHasher
    clear = bytearray(password.encode("ascii"))
    try:
        hashed = ScryptPasswordHasher().hash_password(memoryview(clear))
    finally:
        clear[:] = b"\x00" * len(clear)
    with psycopg.connect(**owner._connection(context["port"]), autocommit=True) as db:
        department = db.execute(
            "SELECT department_id FROM plm.prj_departments WHERE project_id=%s ORDER BY department_id LIMIT 1",
            (project,),
        ).fetchone()[0]
        for username, role in (("Edge PlanVersion Manager", "PROJECT_MANAGER"),
                               ("Edge PlanVersion Reviewer", "CUSTOMER_MANAGER")):
            user_id = db.execute(
                "INSERT INTO plm.auth_users (username_display,username_normalized) VALUES (%s,%s) RETURNING user_id",
                (username, username.casefold()),
            ).fetchone()[0]
            credential_id = db.execute(
                "INSERT INTO plm.auth_password_credentials "
                "(user_id,credential_version,password_hash,algorithm_id,parameter_set) "
                "VALUES (%s,1,%s,%s,%s::jsonb) RETURNING password_credential_id",
                (user_id, hashed.password_hash, hashed.algorithm_id,
                 json.dumps({"n": 131072, "r": 8, "p": 1, "dklen": 32})),
            ).fetchone()[0]
            db.execute("UPDATE plm.auth_users SET credential_version=1,active_password_credential_id=%s,state='ENABLED' WHERE user_id=%s",
                       (credential_id, user_id))
            db.execute("INSERT INTO plm.prj_project_members (project_id,user_id,department_id,project_role) VALUES (%s,%s,%s,%s)",
                       (project, user_id, department, role))
    trace = uuid.uuid4()
    plan_service = PlanCreateService(
        unit_of_work=runtime.unit_of_work, access=SqlAlchemyProjectWriteAccess(),
        license_guard=context["license_guard"],
        authorization=ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        ), repository=SqlAlchemyPlanCreateRepository(),
        receipts=SqlAlchemyIdempotencyReceipts(), audit=context["audit"],
    )
    plan = plan_service.create(CreatePlan(
        context["token"], context["csrf"], trace, project,
        "合成Edge闭环计划", "plan-version-edge-create-plan-0001",
    ))
    port = _free_port()
    context["run_root"] = context["owned_run_root"]
    server, thread = _serve(context, port)
    try:
        import os
        from subprocess import run
        env = dict(os.environ)
        env["PLM_BROWSER_TEMP_ROOT"] = r"D:\PLM-Test-Temp"
        env["PLM_BROWSER_SYNTHETIC_USERNAME"] = "Edge PlanVersion Manager"
        env["PLM_BROWSER_SYNTHETIC_PASSWORD"] = password
        env["PLM_BROWSER_SYNTHETIC_REVIEWER"] = "Edge PlanVersion Reviewer"
        result = run([
            "node", str(ROOT / "validation/plan-version-edge-postgres/run-planversion-edge.mjs"),
            f"http://127.0.0.1:{port}", str(project), str(plan.plan_id), context["token"].hex(),
        ], cwd=ROOT, env=env, check=False, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180)
        print(result.stdout or "")
        if result.returncode != 0:
            raise AssertionError(
                f"Edge harness failed ({result.returncode}): {(result.stderr or '')[-4000:]}"
            )
        review_id = None
        with owner.psycopg.connect(**owner._connection(context["port"])) as db:
            version_id = db.execute(
                "SELECT plan_version_id FROM plm.pln_plan_versions WHERE plan_id=%s ORDER BY version_no DESC LIMIT 1",
                (plan.plan_id,),
            ).fetchone()[0]
            state = db.execute(
                "SELECT version_state FROM plm.pln_plan_versions WHERE plan_version_id=%s", (version_id,),
            ).fetchone()[0]
            counts = db.execute(
                "SELECT (SELECT count(*) FROM plm.pln_wbs_items WHERE plan_version_id=%s),"
                "(SELECT count(*) FROM plm.pln_item_requirement_refs WHERE plan_version_id=%s),"
                "(SELECT count(*) FROM plm.pln_plan_version_validation_results WHERE plan_version_id=%s)",
                (version_id, version_id, version_id),
            ).fetchone()
            review = db.execute(
                "SELECT review_ref FROM plm.pln_plan_versions WHERE plan_version_id=%s",
                (version_id,),
            ).fetchone()
            review_state = db.execute(
                "SELECT review_state, active_round_id FROM plm.rvw_reviews WHERE review_id=%s",
                (review[0],),
            ).fetchone() if review and review[0] else None
            round_id = review_state[1] if review_state else None
            round_state = db.execute(
                "SELECT round_state FROM plm.rvw_review_rounds WHERE review_round_id=%s",
                (round_id,),
            ).fetchone() if round_id else None
            review_counts = db.execute(
                "SELECT (SELECT count(*) FROM plm.rvw_review_assignments WHERE review_round_id=%s),"
                "(SELECT count(*) FROM plm.rvw_review_decisions WHERE review_round_id=%s),"
                "(SELECT count(*) FROM plm.rvw_round_events WHERE review_round_id=%s AND event_type='STARTED'),"
                "(SELECT count(*) FROM plm.aud_events WHERE target_object_id IN (%s,%s)),"
                "(SELECT count(*) FROM plm.plt_idempotency_receipts WHERE operation='V1_PLAN_VERSION_SUBMIT_REVIEW' AND state='COMPLETED' AND result_ref_id=%s)",
                (round_id, round_id, round_id, review[0], round_id, round_id),
            ).fetchone() if round_id else None
        if (not review or state != "IN_REVIEW" or counts[0] != 2 or counts[1] != 2
                or counts[2] < 1 or not review_state or review_state[0] != "IN_REVIEW"
                or not round_state or round_state[0] != "IN_REVIEW"
                or review_counts != (1, 0, 1, 2, 1)):
            raise AssertionError(
                f"PostgreSQL readback mismatch: plan={state}, children={counts}, "
                f"review={review_state}, round={round_state}, totals={review_counts}"
            )
        print(f"PLAN_VERSION_EDGE_POSTGRESQL_PASS: version={version_id}; state={state}; "
              f"WBS/requirement/validation={counts}; Review/Round={review_state[0]}/{round_state[0]}; "
              f"assignments/decisions/started-events/audits/receipts={review_counts}")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            raise RuntimeError("temporary Uvicorn server did not stop")


def _terminal(case: str, **context) -> None:
    assert case == "APPROVE"
    full.original_terminal(case, **context)
    full._outline_full(**context)
    owner.verify_owner(context)
    if RUN_ROOT is None:
        raise RuntimeError("D-drive test root was not initialized")
    context["owned_run_root"] = RUN_ROOT
    _edge_fixture(context)


def main(run_root: Path) -> None:
    global RUN_ROOT
    runner = owner._main_fixture()
    runner.helper.PG_SOURCE = Path(r"D:\POC-02\postgresql-18.6\pgsql")
    runner.helper.VECTOR_SOURCE = ROOT / "artifacts/poc-02/windows/source/pgvector-0.8.6"
    safe_root = (r"d:\plm-test-temp" + "\\").lower()
    if not run_root.is_absolute() or not str(run_root).lower().startswith(safe_root):
        raise ValueError("Owned PG fixture root must be under D:\\PLM-Test-Temp")
    RUN_ROOT = run_root
    full.terminal._terminal = _terminal
    full.terminal._run("APPROVE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    args = parser.parse_args()
    main(args.run_root)
