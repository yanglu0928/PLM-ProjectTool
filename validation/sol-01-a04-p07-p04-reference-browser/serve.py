"""Owned Windows 11 Edge/PG proof for PROJECT Reference fixed-source pages."""

from __future__ import annotations

import importlib.util
import socket
import subprocess
import sys
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from plm_assistant.entrypoints.api import create_app
from plm_assistant.entrypoints.windows_solution_reference import (
    create_windows_project_reference_list_router,
    create_windows_project_reference_read_router,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import create_session_read_router
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.session_repository import SqlAlchemySessionRepository
from plm_assistant.modules.auth.infrastructure.session_view import SqlAlchemySessionView
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.document.api.read_documents import create_document_read_router
from plm_assistant.modules.document.api.read_versions import create_document_version_read_router
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.evidence.api.view_evidence import create_evidence_viewer_router
from plm_assistant.modules.evidence.application.document_source_proof import DocumentEvidenceProofService
from plm_assistant.modules.evidence.application.parsed_node_proof import ParsedNodeEvidenceProofService
from plm_assistant.modules.evidence.application.read_evidence import EvidenceReadService
from plm_assistant.modules.evidence.application.view_evidence import EvidenceViewerService
from plm_assistant.modules.evidence.infrastructure.read_repository import SqlAlchemyEvidenceReadRepository
from plm_assistant.modules.auth.infrastructure.deployment_read_access import SqlAlchemyDeploymentReadAccess
from plm_assistant.modules.auth.infrastructure.project_read_access import SqlAlchemyProjectReadAccess
from plm_assistant.modules.project.infrastructure.authorized_projects import SqlAlchemyAuthorizedProjects
from plm_assistant.modules.project.infrastructure.authorization_repository import SqlAlchemyProjectAuthorizationRepository
from plm_assistant.modules.solution.api.reference_list_cursor import ReferenceListCursorCodec


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "reference_project_fixture", ROOT / "validation/sol-01-a04-p03-p02-p02-project-reference-create/verify.py")
assert SPEC and SPEC.loader
fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixture)
DIST = ROOT / "apps/frontend/dist"


def on_created(*, runtime, audit, license_guard, project, created, document_version,
               evidence, token, documents, downloads, parse_results, **_unused) -> None:
    if not (DIST / "index.html").is_file():
        raise RuntimeError("Build apps/frontend before the browser proof")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        reservation.listen(128)
        http_port = reservation.getsockname()[1]
        origin = f"http://127.0.0.1:{http_port}"
        origins = LoginOriginPolicy([origin])
        sessions = SessionService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemySessionRepository(),
            issue_access=object(), audit=audit,
        )
        evidence_reads = EvidenceReadService(
            unit_of_work=runtime.unit_of_work,
            session_access=SqlAlchemyProjectReadAccess(),
            admin_access=SqlAlchemyDeploymentReadAccess(),
            project_facts=SqlAlchemyProjectAuthorizationRepository(),
            license_guard=license_guard,
            repository=SqlAlchemyEvidenceReadRepository(),
        )
        viewer = EvidenceViewerService(
            evidence=evidence_reads, versions=documents,
            document_proof=DocumentEvidenceProofService(document_snapshots=downloads),
            node_proof=ParsedNodeEvidenceProofService(results=parse_results),
        )
        app = create_app(
            session_router=create_session_read_router(
                sessions=sessions, origins=origins,
                views=SqlAlchemySessionView(
                    unit_of_work=runtime.unit_of_work,
                    projects=SqlAlchemyAuthorizedProjects(),
                ),
            ),
            project_reference_read_router=create_windows_project_reference_read_router(
                runtime=runtime, sessions=sessions, origins=origins, license_guard=license_guard,
            ),
            project_reference_list_router=create_windows_project_reference_list_router(
                runtime=runtime, sessions=sessions, origins=origins, license_guard=license_guard,
                cursors=ReferenceListCursorCodec(b"r" * 32),
            ),
            document_read_router=create_document_read_router(
                sessions=sessions, documents=documents, origins=origins,
                cursors=DocumentListCursorCodec(b"d" * 32),
            ),
            document_version_read_router=create_document_version_read_router(
                sessions=sessions, documents=documents, origins=origins,
                cursors=VersionListCursorCodec(b"v" * 32),
            ),
            document_download_router=create_document_download_router(
                sessions=sessions, downloads=downloads, origins=origins,
            ),
            evidence_viewer_router=create_evidence_viewer_router(
                sessions=sessions, origins=origins, viewer=viewer,
            ),
        )
        app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="frontend-assets")

        @app.get("/{frontend_path:path}", include_in_schema=False)
        async def frontend(frontend_path: str):
            if frontend_path.startswith("api/"):
                from fastapi import HTTPException
                raise HTTPException(404)
            return FileResponse(DIST / "index.html", media_type="text/html")

        server = uvicorn.Server(uvicorn.Config(
            app, log_level="critical", access_log=False,
            proxy_headers=False, lifespan="on", timeout_graceful_shutdown=5,
        ))
        worker = Thread(target=lambda: server.run(sockets=[reservation]), daemon=False)
        worker.start()
        try:
            deadline = monotonic() + 15
            while not server.started:
                if not worker.is_alive() or monotonic() > deadline:
                    raise RuntimeError("Owned frontend/API startup failed")
                sleep(.05)
            command = ["node", str(Path(__file__).with_name("run-edge-browser.mjs")),
                       origin, str(project), str(created.reference_solution_id),
                       str(document_version), str(evidence), token.hex()]
            result = subprocess.run(command, check=False, timeout=120,
                                    capture_output=True, text=True, encoding="utf-8")
            if result.returncode != 0:
                raise RuntimeError(f"Edge browser proof failed: {result.stdout[-3000:]} {result.stderr[-3000:]}")
            print(result.stdout.strip())
        finally:
            server.should_exit = True
            worker.join(timeout=15)
            if worker.is_alive():
                raise RuntimeError("Owned frontend/API server did not stop")


def main() -> None:
    fixture.main(on_created=on_created)
    print("SOL_01_A04_P07_P04_REFERENCE_BROWSER_PG_PASS: Windows 11 Edge, real Session/PG/private file, "
          "candidate/detail/document/Evidence navigation")


if __name__ == "__main__":
    main()
