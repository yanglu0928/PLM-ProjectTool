"""Disposable Win11 Edge/PG proof of project GLOBAL candidate DRAFT creation."""

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
from plm_assistant.entrypoints.windows_requirement import create_windows_requirement_routers
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_outline_read_router,
    create_windows_outline_version_create_router,
    create_windows_section_list_router,
)
from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_project_global_reference_candidate_router,
    create_windows_project_reference_list_router,
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
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.application.global_reference_candidate_cursor import (
    GlobalReferenceCandidateCursorCodec,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "global_candidate_browser_fixture",
    ROOT / "validation/sol-03-a04-p03-p03-p06-a03-p05-a05-global-candidate-windows/verify.py")
assert SPEC and SPEC.loader
factory_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(factory_fixture)
SPEC_OWNER = importlib.util.spec_from_file_location(
    "global_candidate_browser_outline_helper",
    ROOT / "validation/sol-03-a04-p03-p03-p04-a03-outline-dual-scope-owner/verify.py")
assert SPEC_OWNER and SPEC_OWNER.loader
outline_helper = importlib.util.module_from_spec(SPEC_OWNER)
SPEC_OWNER.loader.exec_module(outline_helper)

DIST = ROOT / "apps/frontend/dist"
PASSWORD = "Synthetic-Global-Candidate-Browser-Only-2026"


class TestOnlyKeyResolver:
    def resolve_key(self, reference):
        assert isinstance(reference, str) and reference.endswith("-v1")
        return b"g" * 32


def on_http(*, runtime, port, project, other_project, initial,
            license_guard, document_storage_root, parse_result_storage_root,
            **facts) -> None:
    factory_fixture.on_http(
        runtime=runtime, port=port, project=project,
        other_project=other_project, initial=initial,
        license_guard=license_guard,
        document_storage_root=document_storage_root,
        parse_result_storage_root=parse_result_storage_root,
        **facts)
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before GLOBAL candidate browser proof")
    token = factory_fixture.http_fixture.fixture.TOKEN
    csrf = factory_fixture.http_fixture.fixture.CSRF
    audit = facts["audit"] if "audit" in facts else None
    if audit is None:
        raise RuntimeError("Owned browser fixture needs real audit port")
    outline, section = outline_helper.create_outline_section(
        runtime=runtime, license_guard=license_guard, audit=audit,
        token=token, csrf=csrf, project=project, suffix="global-candidate-browser")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = LoginOriginPolicy([origin])
        hasher = ScryptPasswordHasher()
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
        common = dict(runtime=runtime, sessions=sessions, origins=origins,
                      license_guard=license_guard)
        requirements = create_windows_requirement_routers(
            runtime, sessions=sessions, origins=origins, license_guard=license_guard,
            audit=audit, include_write=False, resolver=TestOnlyKeyResolver())
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            solution_outline_read_router=create_windows_outline_read_router(**common),
            solution_section_list_router=create_windows_section_list_router(
                **common, cursors=SectionListCursorCodec(b"s" * 32)),
            project_reference_list_router=create_windows_project_reference_list_router(
                **common, cursors=ReferenceListCursorCodec(b"r" * 32)),
            project_global_reference_candidate_router=(
                create_windows_project_global_reference_candidate_router(
                    **common, cursors=GlobalReferenceCandidateCursorCodec(b"g" * 32),
                    document_storage_root=document_storage_root,
                    parse_result_storage_root=parse_result_storage_root)),
            solution_outline_version_create_router=create_windows_outline_version_create_router(
                **common, audit=audit,
                document_storage_root=document_storage_root,
                parse_result_storage_root=parse_result_storage_root),
            requirement_package_router=requirements.packages,
            requirement_router=requirements.requirements,
            requirement_version_router=requirements.versions,
            requirement_relation_router=requirements.relations,
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
                    raise RuntimeError("Owned GLOBAL candidate browser preview did not start")
                sleep(.05)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                 origin, str(project), str(other_project), str(outline),
                 str(section), str(initial.reference_solution_id),
                 str(initial.reference_version_id), PASSWORD],
                check=False, timeout=120, capture_output=True, text=True,
                encoding="utf-8")
            if result.returncode:
                raise RuntimeError("GLOBAL candidate browser proof failed: "
                                   f"{result.stdout[-3000:]} {result.stderr[-3000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned GLOBAL candidate browser preview did not stop")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        version = db.execute(
            "SELECT solution_outline_version_id FROM plm.sol_outline_versions "
            "WHERE solution_outline_id=%s", (outline,)).fetchall()
        assert len(version) == 1
        fixed = db.execute(
            "SELECT reference_solution_id,reference_version_id,reference_scope "
            "FROM plm.sol_outline_reference_refs "
            "WHERE solution_outline_version_id=%s", (version[0][0],)).fetchall()
        assert fixed == [(initial.reference_solution_id,
                          initial.reference_version_id, "GLOBAL")]
        assert db.execute(
            "SELECT count(*) FROM plm.aud_events WHERE action='SOL_OUTLINE_VERSION_CREATED' "
            "AND target_object_id=%s", (outline,)).fetchone()[0] == 1


def on_qualified(**facts) -> None:
    factory_fixture.http_fixture.owner_fixture.internal.on_qualified(
        **facts, on_published=lambda **published:
        factory_fixture.http_fixture.owner_fixture.on_published(
            **published, on_http=on_http))


if __name__ == "__main__":
    hasher = ScryptPasswordHasher()
    clear = bytearray(PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            credential = hasher.hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    factory_fixture.http_fixture.fixture.main(
        on_qualified=on_qualified, login_credential=credential)
    print("SOL_03_A04_P03_P03_P06_A03_P05_A06_P03_GLOBAL_CANDIDATE_EDGE_PG_PASS")
