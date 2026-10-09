"""Owned Windows Edge/PG preview for one synthetic GLOBAL source."""

from __future__ import annotations

import importlib.util
import socket
import subprocess
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_global_reference_create_router,
    create_windows_global_reference_read_router,
    create_windows_global_reference_list_router,
    create_windows_global_reference_revise_router,
    create_windows_reference_deidentification_router,
)
from plm_assistant.modules.solution.api.global_reference_list_cursor import GlobalReferenceListCursorCodec
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
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.evidence.api.view_evidence import create_evidence_viewer_router
from plm_assistant.modules.evidence.api.read_evidence import create_evidence_read_router
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.evidence.application.document_source_proof import DocumentEvidenceProofService
from plm_assistant.modules.evidence.application.parsed_node_proof import ParsedNodeEvidenceProofService
from plm_assistant.modules.evidence.application.read_evidence import EvidenceReadService
from plm_assistant.modules.evidence.application.view_evidence import EvidenceViewerService
from plm_assistant.modules.evidence.infrastructure.read_repository import SqlAlchemyEvidenceReadRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import SqlAlchemyIdempotencyReceipts


ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Synthetic-Reference-Browser-Only-2026"
SPEC = importlib.util.spec_from_file_location(
    "global_source_fixture", ROOT / "validation/sol-01-a04-p02-p03-p03-p03-p02-real-sources/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
DIST = ROOT / "apps/frontend/dist"


def on_preview(*, runtime, audit, license_guard, document, version, evidence,
               documents, downloads, parse_results, browser_script=None,
               browser_extra=(), include_reference_create=False,
               include_reference_read=False, include_reference_revise=False,
               **_unused) -> None:
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build apps/frontend before browser verification")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = LoginOriginPolicy([origin])
        verifier = ScryptPasswordHasher()
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=SqlAlchemyPasswordIssueAccess(verifier), audit=audit,
            idempotency=SqlAlchemyIdempotencyReceipts())
        login = LoginService(
            unit_of_work=runtime.unit_of_work,
            rate=LoginRateLimiter(unit_of_work=runtime.unit_of_work,
                                  repository=SqlAlchemyLoginRateRepository()),
            identity=SqlAlchemyLoginIdentity(),
            missing_verifier=ScryptMissingIdentityVerifier(verifier),
            sessions=sessions, audit=audit)
        views = SqlAlchemySessionView(
            unit_of_work=runtime.unit_of_work,
            projects=SqlAlchemyAuthorizedProjects())
        evidence_reads = EvidenceReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=license_guard,
            repository=SqlAlchemyEvidenceReadRepository())
        viewer = EvidenceViewerService(
            evidence=evidence_reads, versions=documents,
            document_proof=DocumentEvidenceProofService(document_snapshots=downloads),
            node_proof=ParsedNodeEvidenceProofService(results=parse_results))
        app = create_app(
            login_router=create_login_router(login=login, origins=origins, views=views),
            session_router=create_session_read_router(
                sessions=sessions, origins=origins, views=views),
            evidence_read_router=create_evidence_read_router(
                sessions=sessions, origins=origins,
                cursors=EvidenceListCursorCodec(b"e" * 32), evidence=evidence_reads),
            reference_deidentification_router=create_windows_reference_deidentification_router(
                runtime=runtime, sessions=sessions, origins=origins,
                license_guard=license_guard, audit=audit,
                documents=documents, downloads=downloads,
                parse_results=parse_results),
            global_reference_create_router=(
                create_windows_global_reference_create_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=license_guard, audit=audit,
                    documents=documents, downloads=downloads,
                    parse_results=parse_results) if include_reference_create else None),
            global_reference_read_router=(
                create_windows_global_reference_read_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=license_guard) if include_reference_read else None),
            global_reference_list_router=(
                create_windows_global_reference_list_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=license_guard,
                    cursors=GlobalReferenceListCursorCodec(b"g" * 32))
                if include_reference_read else None),
            global_reference_revise_router=(
                create_windows_global_reference_revise_router(
                    runtime=runtime, sessions=sessions, origins=origins,
                    license_guard=license_guard, audit=audit,
                    documents=documents, downloads=downloads,
                    parse_results=parse_results) if include_reference_revise else None),
            evidence_viewer_router=create_evidence_viewer_router(
                sessions=sessions, origins=origins, viewer=viewer),
            document_download_router=create_document_download_router(
                sessions=sessions, downloads=downloads, origins=origins))
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="frontend-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend(frontend_path: str):
            if frontend_path.startswith("api/"):
                from fastapi import HTTPException
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
                    raise RuntimeError("Owned GLOBAL attestation preview server did not start")
                sleep(.05)
            command = ["node", str(browser_script or Path(__file__).with_name("run-edge-browser.mjs")),
                       origin, str(document), str(version), str(evidence), PASSWORD,
                       *map(str, browser_extra)]
            result = subprocess.run(command, check=False, timeout=120,
                                    capture_output=True, text=True, encoding="utf-8")
            if result.returncode != 0:
                raise RuntimeError(f"Edge proof failed: {result.stdout[-3000:]} {result.stderr[-3000:]}")
            print(result.stdout.strip())
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned GLOBAL attestation preview server did not stop")


def main() -> None:
    clear = bytearray(PASSWORD.encode("ascii"))
    try:
        with memoryview(clear) as view:
            credential = ScryptPasswordHasher().hash_password(view)
    finally:
        clear[:] = b"\x00" * len(clear)
    fixture.main(on_preview=on_preview, login_credential=credential)
    print("SOL_01_A04_P08_P04_P03_GLOBAL_ATTESTATION_EDGE_PG_PASS: synthetic Windows 11 Edge")


if __name__ == "__main__":
    main()
