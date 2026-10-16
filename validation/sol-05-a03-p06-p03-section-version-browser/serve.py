"""Disposable Win11 Edge/PG proof of the real SectionVersion CREATE page."""

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
from plm_assistant.entrypoints.windows_requirement import create_windows_requirement_routers
from plm_assistant.entrypoints.windows_solution_outline import (
    create_windows_section_read_router,
    create_windows_section_list_router,
    create_windows_section_version_create_router,
    create_windows_section_version_read_router,
    create_windows_section_version_validate_router,
    create_windows_structured_spec_create_router,
    create_windows_structured_spec_list_router,
    create_windows_structured_spec_read_router,
    create_windows_structured_spec_revise_router,
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
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.read_documents import create_document_read_router
from plm_assistant.modules.document.api.read_versions import create_document_version_read_router
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.evidence.api.read_evidence import create_evidence_read_router
from plm_assistant.modules.evidence.application.read_evidence import EvidenceReadService
from plm_assistant.modules.evidence.infrastructure.read_repository import SqlAlchemyEvidenceReadRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.project.api.read_projects import create_project_read_router
from plm_assistant.modules.project.application.read_projects import ProjectReadService
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.project.infrastructure.read_repository import SqlAlchemyProjectReadRepository
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.solution.api.section_version_list_cursor import SectionVersionListCursorCodec
from plm_assistant.modules.solution.api.section_list_cursor import SectionListCursorCodec
from plm_assistant.modules.solution.api.structured_spec_list_cursor import StructuredSpecListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "section_create_browser_fixture",
    ROOT / "validation/sol-05-a02-p11-section-version-create-owner/verify.py")
assert SPEC and SPEC.loader
prior = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prior)
DIST = ROOT / "apps/frontend/dist"
PASSWORD = secrets.token_urlsafe(24)


class TestOnlyKeyResolver:
    def resolve_key(self, reference):
        assert isinstance(reference, str) and reference.endswith("-v1")
        return b"r" * 32


def _writer(port, project):
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
            "SELECT department_id FROM plm.prj_departments WHERE project_id=%s LIMIT 1",
            (project,)).fetchone()[0]
        actor = db.execute(
            "INSERT INTO plm.auth_users(username_display,username_normalized) "
            "VALUES ('Section Browser Writer','section browser writer') RETURNING user_id"
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
            "VALUES (%s,%s,%s,'IMPLEMENTATION_MEMBER')",
            (project, actor, department))
    return hasher


def on_browser(*, port, runtime, audit, license_guard, project, other_project,
               section, document_version, requirement, requirement_version,
               evidence, documents, downloads, parse_results,
               validation_mode=False, spec_mode=False, detail_mode=False,
               list_mode=False, revise_mode=False, stale_spec=None,
               current_requirement_version=None, **_unused):
    if detail_mode and not spec_mode:
        raise ValueError("Structured spec detail proof requires spec mode")
    if list_mode and not (spec_mode and detail_mode):
        raise ValueError("Structured spec list proof requires spec detail mode")
    if revise_mode and not (spec_mode and detail_mode):
        raise ValueError("Structured spec revise proof requires spec detail mode")
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build frontend before SectionVersion CREATE browser proof")
    hasher = _writer(port, project)
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        document = db.execute(
            "SELECT document_id FROM plm.doc_document_versions WHERE document_version_id=%s",
            (document_version,)).fetchone()[0]
        fixed_version = db.execute(
            "SELECT solution_section_version_id FROM plm.sol_section_versions "
            "WHERE solution_section_id=%s AND version_no=1", (section,)).fetchone()[0]
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
        common = dict(runtime=runtime, sessions=sessions, origins=origins,
                      license_guard=license_guard)
        doc_reads = DocumentReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=license_guard,
            repository=SqlAlchemyDocumentReadRepository())
        evidence_reads = EvidenceReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=license_guard,
            repository=SqlAlchemyEvidenceReadRepository())
        requirements = create_windows_requirement_routers(
            runtime, sessions=sessions, origins=origins, license_guard=license_guard,
            audit=audit, include_write=False, resolver=TestOnlyKeyResolver())
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            project_read_router=create_project_read_router(
                sessions=sessions, origins=origins, projects=ProjectReadService(
                    unit_of_work=runtime.unit_of_work,
                    access=SqlAlchemyProjectReadAccess(),
                    license_guard=license_guard,
                    repository=SqlAlchemyProjectReadRepository())),
            document_read_router=create_document_read_router(
                sessions=sessions, documents=doc_reads, origins=origins,
                cursors=DocumentListCursorCodec(b"d" * 32)),
            document_version_read_router=create_document_version_read_router(
                sessions=sessions, documents=doc_reads, origins=origins,
                cursors=VersionListCursorCodec(b"v" * 32)),
            evidence_read_router=create_evidence_read_router(
                sessions=sessions, evidence=evidence_reads, origins=origins,
                cursors=EvidenceListCursorCodec(b"e" * 32)),
            requirement_router=requirements.requirements,
            solution_section_read_router=create_windows_section_read_router(**common),
            solution_section_list_router=(create_windows_section_list_router(
                **common, cursors=SectionListCursorCodec(b"s" * 32)) if spec_mode else None),
            solution_section_version_read_router=create_windows_section_version_read_router(
                **common, cursors=SectionVersionListCursorCodec(b"h" * 32)),
            solution_section_version_create_router=create_windows_section_version_create_router(
                **common, audit=audit, documents=documents,
                downloads=downloads, parse_results=parse_results),
            solution_structured_spec_create_router=(
                create_windows_structured_spec_create_router(
                    **common, audit=audit, documents=documents,
                    downloads=downloads, parse_results=parse_results)
                if spec_mode else None),
            solution_structured_spec_read_router=(
                create_windows_structured_spec_read_router(**common)
                if detail_mode else None),
            solution_structured_spec_list_router=(
                create_windows_structured_spec_list_router(
                    **common, cursors=StructuredSpecListCursorCodec(b"l" * 32))
                if list_mode else None),
            solution_structured_spec_revise_router=(
                create_windows_structured_spec_revise_router(
                    **common, audit=audit, documents=documents,
                    downloads=downloads, parse_results=parse_results)
                if revise_mode else None),
            solution_section_version_validate_router=(
                create_windows_section_version_validate_router(
                    **common, audit=audit, documents=documents,
                    downloads=downloads, parse_results=parse_results)
                if validation_mode else None),
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
                    raise RuntimeError("Owned SectionVersion CREATE preview did not start")
                sleep(.05)
            browser_script = (ROOT / "validation/sol-05-a04-p08-section-version-browser/run-edge-browser.mjs"
                              if validation_mode else
                              ROOT / "validation/sol-06-a09-p06-p03-structured-spec-browser/run-edge-browser.mjs"
                              if spec_mode else Path(__file__).with_name("run-edge-browser.mjs"))
            result = subprocess.run(
                ["node", str(browser_script),
                 origin, str(project), str(other_project), str(section), str(document),
                 str(document_version), str(requirement), str(requirement_version),
                 str(evidence), *((str(fixed_version),) if validation_mode else ())],
                check=False, timeout=120, capture_output=True, text=True,
                encoding="utf-8", env={**os.environ,
                                        "PLM_BROWSER_SYNTHETIC_PASSWORD": PASSWORD,
                                        "PLM_SPEC_DETAIL_ACCEPTANCE": "1" if detail_mode else "0",
                                        "PLM_SPEC_LIST_ACCEPTANCE": "1" if list_mode else "0",
                                        "PLM_SPEC_REVISE_ACCEPTANCE": "1" if revise_mode else "0",
                                        "PLM_STALE_SPEC_ID": str(stale_spec or ""),
                                        "PLM_CURRENT_REQUIREMENT_VERSION": str(
                                            current_requirement_version or "")})
            if result.returncode:
                raise RuntimeError("SectionVersion browser proof failed: "
                                   f"{result.stdout[-3000:]} {result.stderr[-3000:]}")
            print(result.stdout.strip(), flush=True)
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned SectionVersion CREATE preview did not stop")
    with psycopg.connect(host="127.0.0.1", port=port, user="poc_admin",
                         dbname="postgres", autocommit=True) as db:
        for table, predicate in (
            ("sol_section_versions", "solution_section_id=%s"),
            ("sol_section_version_create_results", "solution_section_id=%s"),
            ("plt_idempotency_receipts", "operation='V1_SOL_SECTION_VERSION_CREATE'"),
            ("aud_events", "action='SOL_SECTION_VERSION_CREATED'"),
        ):
            args = (section,) if "%s" in predicate else ()
            assert db.execute(
                f"SELECT count(*) FROM plm.{table} WHERE {predicate}", args
            ).fetchone()[0] == (5 if validation_mode or spec_mode else 6), table
        if validation_mode:
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                              "WHERE operation='V1_SOL_SECTION_VERSION_VALIDATE'").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.aud_events "
                              "WHERE action='SOL_SECTION_VERSION_VALIDATED'").fetchone()[0] == 1
        if spec_mode:
            assert db.execute("SELECT count(*) FROM plm.sol_structured_specs").fetchone()[0] == (
                51 if list_mode else 3 if revise_mode else 1)
            assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                              "WHERE operation='V1_SOL_STRUCTURED_SPEC_CREATE'").fetchone()[0] == 1
            assert db.execute("SELECT count(*) FROM plm.aud_events "
                              "WHERE action='SOL_STRUCTURED_SPEC_CREATED'").fetchone()[0] == 1
            if revise_mode:
                assert db.execute("SELECT count(*) FROM plm.plt_idempotency_receipts "
                                  "WHERE operation='V1_SOL_STRUCTURED_SPEC_REVISE'").fetchone()[0] == 1
                assert db.execute("SELECT count(*) FROM plm.aud_events "
                                  "WHERE action='SOL_STRUCTURED_SPEC_REVISED'").fetchone()[0] == 1
    if revise_mode:
        print("SOL_06_A12_P07_STRUCTURED_SPEC_REVISE_BROWSER_PASS: "
              "Win11 Edge/PG detail-to-revise, original-key replay, source drift, "
              "cross-project hidden, one create/revise receipt and audit")
    elif list_mode:
        print("SOL_06_A11_P07_STRUCTURED_SPEC_LIST_BROWSER_PASS: "
              "Win11 Edge/PG project entry, 51-item two-page history, detail, "
              "cross-project clear, one browser DRAFT/receipt/audit")
    elif detail_mode:
        print("SOL_06_A10_P05_STRUCTURED_SPEC_DETAIL_BROWSER_PASS: "
              "Win11 Edge/PG CREATE-to-GET and cross-project isolation, one DRAFT/receipt/audit")
    elif spec_mode:
        print("SOL_06_A09_P06_P03_STRUCTURED_SPEC_BROWSER_PASS: "
              "Win11 Edge/PG CREATE and original-key replay, one DRAFT/receipt/audit")
    elif validation_mode:
        print("SOL_05_A04_P08_SECTION_VERSION_VALIDATE_BROWSER_PASS: "
              "Win11 Edge/PG validated page and original-key replay, one receipt/audit")
    else:
        print("SOL_05_A03_P06_P03_SECTION_VERSION_BROWSER_PASS: "
              "Win11 Edge/PG create and original-key replay, one version/receipt/audit")


if __name__ == "__main__":
    prior.prior.main(on_created=lambda **kwargs: prior.on_created(
        **kwargs, on_http=on_browser))
