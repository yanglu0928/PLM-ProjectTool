from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.infrastructure.audit_repository import SqlAlchemyAuditRepository
from plm_assistant.modules.document.api.download_version import create_document_download_router
from plm_assistant.modules.document.application.prepare_download import PrepareDownloadService
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.infrastructure.local_storage import LocalFileStorage
from plm_assistant.modules.document.infrastructure.read_repository import SqlAlchemyDocumentReadRepository
from plm_assistant.modules.output.api.read_artifact import create_output_artifact_read_router
from plm_assistant.modules.output.application.read_artifact import OutputArtifactReadService
from plm_assistant.modules.output.infrastructure.read_artifact_repository import SqlAlchemyOutputArtifactReadRepository
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers
from plm_assistant.modules.project.application.authorization import ProjectActorFacts
from validation.out_01_a01_p38_download_http.verify import (
    _Access, _Admin, _License, _Origins, _ProjectFacts, _ProjectRead, _Sessions, _UnitOfWork,
)


def verify_live_edge_download(engine, *, data: dict, storage_root: Path,
                              dist: Path, run_id: str) -> dict[str, object]:
    """Run P39's real Edge action through P38 routes on one live FastAPI/PG18 process."""
    runner = Path(os.environ.get("RUNNER_TEMP", "")).resolve(strict=True)
    dist = dist.resolve(strict=True)
    storage_root = storage_root.resolve(strict=True)
    if runner.drive.casefold() != "d:" or not dist.is_relative_to(runner):
        raise ValueError("P40 requires frontend dist within hosted D-drive RUNNER_TEMP")
    if not storage_root.is_relative_to(runner):
        raise ValueError("P40 storage root must stay within hosted D-drive RUNNER_TEMP")
    if not run_id.isdigit() or not run_id or len(run_id) > 12:
        raise ValueError("P40 run id is invalid")
    if not (dist / "index.html").is_file():
        raise ValueError("P40 same-run production frontend is incomplete")

    project_id, user_id = data["project"], data["user"]
    token = bytes.fromhex("77" * 32)
    uow = _UnitOfWork(engine)
    access = _Access(user_id, token)
    sessions, origins = _Sessions(token), _Origins()
    artifact_reads = OutputArtifactReadService(
        unit_of_work=uow, access=access,
        projects=_ProjectRead(user_id, project_id),
        license_guard=_License(),
        repository=SqlAlchemyOutputArtifactReadRepository(),
    )
    document_reads = DocumentReadService(
        unit_of_work=uow, session_access=access, admin_access=_Admin(),
        project_facts=_ProjectFacts(user_id, project_id),
        license_guard=_License(),
        repository=SqlAlchemyDocumentReadRepository(),
    )
    download = PrepareDownloadService(
        reader=document_reads, storage=LocalFileStorage(storage_root),
        unit_of_work=uow, audit=AuditService(SqlAlchemyAuditRepository()),
    )
    app = FastAPI()

    @app.middleware("http")
    async def attach_trace(request, call_next):
        request.state.trace_id = str(uuid.uuid4())
        return await call_next(request)

    install_error_handlers(app)
    app.include_router(create_output_artifact_read_router(
        sessions=sessions, origins=origins, service=artifact_reads,
    ))
    app.include_router(create_document_download_router(
        sessions=sessions, downloads=download, origins=origins,
    ))

    config_path = runner / ("plm-out-p40-fixture-" + run_id + ".json")
    summary_path = runner / ("plm-out-p40-live-edge-summary-" + run_id + ".json")
    download_dir = runner / ("plm-out-p40-live-edge-downloads-" + run_id)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = None
    thread = None
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        listener.setblocking(False)
        port = int(listener.getsockname()[1])
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="critical",
            access_log=False, lifespan="off",
        ))
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]},
            name="p40-fastapi-loopback", daemon=True,
        )
        thread.start()
        deadline = time.monotonic() + 20
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not server.started:
            raise RuntimeError("P40 FastAPI loopback did not start")
        fixture = {
            "ids": {
                "project": str(project_id), "request": str(data["request"]),
                "document": str(data["document"]), "version": str(data["version"]),
                "actor": str(user_id),
            },
            "payload_hex": data["content_bytes"].hex(),
            "mime": data["mime"],
            "session_token_hex": token.hex(),
        }
        config_path.write_text(json.dumps(fixture, separators=(",", ":")), encoding="utf-8")
        node = shutil.which("node.exe") or shutil.which("node")
        if not node:
            raise RuntimeError("P40 requires the hosted Node runtime")
        harness = Path(__file__).resolve().parents[1] / "out-01-a01-p39-edge-download" / "run.mjs"
        result = subprocess.run(
            [node, str(harness), "--dist", str(dist), "--summary-out", str(summary_path),
             "--download-dir", str(download_dir), "--backend-origin", f"http://127.0.0.1:{port}",
             "--live-config", str(config_path)],
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**os.environ, "TEMP": str(runner), "TMP": str(runner)},
            capture_output=True, text=True, errors="replace", timeout=240, check=False,
        )
        if result.returncode != 0 or not summary_path.is_file():
            raise RuntimeError("P40 hosted Edge validation failed; exit="
                               + str(result.returncode))
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        requests = summary.get("requests")
        reference_path = (
            f"/api/v1/projects/{project_id}/output-requests/{data['request']}/artifact"
        )
        content_path = (
            f"/api/v1/projects/{project_id}/documents/{data['document']}"
            f"/versions/{data['version']}/content"
        )
        if not isinstance(requests, list):
            raise AssertionError("P40 Edge request evidence is missing")
        if (sum(1 for x in requests if x.get("path") == reference_path and x.get("status") == 200) != 1
                or sum(1 for x in requests if x.get("path") == content_path and x.get("status") == 200) != 1):
            raise AssertionError("P40 expected one successful live Artifact and content request")
        if summary.get("status") != "PASS_SCOPE_LIMITED" or summary.get("backend_mode") != "live-fastapi-loopback":
            raise AssertionError("P40 Edge summary did not prove the live FastAPI route")
        return {
            "status": "PASS_SCOPE_LIMITED",
            "edge_saved_actual_pg18_document_bytes": summary.get("saved_file_matches_expected_bytes"),
            "live_artifact_reference_http_200_once": True,
            "live_document_content_http_200_once": True,
            "cross_project_or_unknown_failed_closed": summary.get("cross_project_failed_closed"),
            "storage_locator_disclosed": False,
            "customer_data": False,
            "external_calls": 0,
            "production_trust_used": False,
            "runner_temp_storage_only": True,
        }
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=20)
            if thread.is_alive():
                raise RuntimeError("P40 FastAPI loopback did not stop")
        try:
            listener.close()
        except OSError:
            pass
        for path in (config_path, summary_path):
            if path.exists():
                path.unlink()
        if download_dir.exists():
            if download_dir.parent != runner or not download_dir.name.startswith("plm-out-p40-live-edge-downloads-"):
                raise RuntimeError("refusing P40 cleanup outside D-drive RUNNER_TEMP")
            shutil.rmtree(download_dir)
