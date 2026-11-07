from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

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


class _UnitOfWork:
    def __init__(self, engine):
        self.engine = engine

    def __call__(self):
        return _Transaction(self.engine)


class _Transaction:
    def __init__(self, engine):
        from sqlalchemy.orm import Session
        self.session = Session(engine, expire_on_commit=False)
        self._committed = False

    def __enter__(self):
        self.session.begin()
        return self

    def commit(self):
        self.session.commit()
        self._committed = True

    def __exit__(self, exc_type, exc, tb):
        if not self._committed and self.session.in_transaction():
            self.session.rollback()
        self.session.close()


class _Sessions:
    def __init__(self, token: bytes):
        self.token = token

    def validate(self, token: bytes) -> None:
        if token != self.token:
            raise ValueError("synthetic session rejected")


class _Origins:
    def require_trusted_host(self, headers) -> None:
        del headers


class _License:
    def require_valid(self, *, trace_id: uuid.UUID) -> object:
        del trace_id
        return object()


class _Access:
    def __init__(self, user_id: uuid.UUID, token: bytes):
        self.user_id, self.token = user_id, token

    def authenticated_user(self, transaction, *, session_token: bytes, now):
        del transaction, now
        return self.user_id if session_token == self.token else None


class _ProjectRead:
    def __init__(self, user_id: uuid.UUID, project_id: uuid.UUID):
        self.user_id, self.project_id = user_id, project_id

    def get_authorized(self, transaction, user_id: uuid.UUID, project_id: uuid.UUID):
        del transaction
        return object() if (user_id == self.user_id and project_id == self.project_id) else None


class _ProjectFacts:
    def __init__(self, user_id: uuid.UUID, project_id: uuid.UUID):
        self.user_id, self.project_id = user_id, project_id

    def actor_facts(self, transaction, *, user_id, project_id, lock=False):
        del transaction, lock
        if user_id != self.user_id or project_id != self.project_id:
            return None
        return ProjectActorFacts("ACTIVE", "PROJECT_MANAGER")


class _Admin:
    def authorized_admin(self, transaction, *, session_token: bytes, now):
        del transaction, session_token, now
        return None


def verify_output_artifact_download_http(engine, *, data: dict,
                                         storage_root: Path) -> dict[str, object]:
    """Exercise real P36 and Document content HTTP routes over P33 PG18 facts."""
    project_id, user_id = data["project"], data["user"]
    document_id, version_id = data["document"], data["version"]
    request_id = data["request"]
    token = bytes.fromhex("77" * 32)
    access = _Access(user_id, token)
    projects = _ProjectRead(user_id, project_id)
    project_facts = _ProjectFacts(user_id, project_id)
    guard = _License()
    uow = _UnitOfWork(engine)
    sessions, origins = _Sessions(token), _Origins()

    artifact_reads = OutputArtifactReadService(
        unit_of_work=uow, access=access, projects=projects,
        license_guard=guard, repository=SqlAlchemyOutputArtifactReadRepository(),
    )
    document_reads = DocumentReadService(
        unit_of_work=uow, session_access=access, admin_access=_Admin(),
        project_facts=project_facts, license_guard=guard,
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

    def get(path: str):
        messages = []
        received = False

        async def receive():
            nonlocal received
            if not received:
                received = True
                return {"type": "http.request", "body": b"", "more_body": False}
            await asyncio.Event().wait()

        async def send(message):
            messages.append(message)

        raw_path = path.encode("ascii")
        scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": raw_path, "query_string": b"",
            "root_path": "", "headers": [
                (b"host", b"testserver"),
                (b"cookie", b"plm_session=" + token.hex().encode("ascii")),
            ],
            "client": ("hosted-verifier", 41000), "server": ("testserver", 80),
            "state": {},
        }
        async def invoke():
            await app(scope, receive, send)
        asyncio.run(invoke())
        start = next(item for item in messages if item["type"] == "http.response.start")
        body = b"".join(item.get("body", b"") for item in messages
                        if item["type"] == "http.response.body")
        headers = {name.decode("latin1").lower(): value.decode("latin1")
                   for name, value in start.get("headers", [])}
        return SimpleNamespace(
            status_code=start["status"], headers=headers, content=body,
            text=body.decode("utf-8", "replace"),
        )

    reference_path = (
        f"/api/v1/projects/{project_id}/output-requests/{request_id}/artifact"
    )
    reference_response = get(reference_path)
    if reference_response.status_code != 200:
        raise AssertionError("authorized Artifact reference HTTP read failed")
    envelope = json.loads(reference_response.text)
    envelope_valid = (
        type(envelope) is dict and set(envelope) == {"data", "trace_id"}
        and type(envelope.get("data")) is dict
        and type(envelope.get("trace_id")) is str
        and str(uuid.UUID(envelope["trace_id"])) == envelope["trace_id"]
    )
    if not envelope_valid:
        raise AssertionError("Artifact reference response envelope is invalid")
    reference = envelope["data"]
    expected_content_path = (
        f"/api/v1/projects/{project_id}/documents/{document_id}"
        f"/versions/{version_id}/content"
    )
    reference_checks = {
        "content_url": reference.get("content_url") == expected_content_path,
        "project_id": reference.get("project_id") == str(project_id),
        "output_request_id": reference.get("output_request_id") == str(request_id),
        "document_id": reference.get("document_id") == str(document_id),
        "document_version_id": reference.get("document_version_id") == str(version_id),
        "content_sha256": reference.get("content_sha256") == data["content_hash"].hex(),
        "size_bytes": reference.get("size_bytes") == data["size"],
        "storage_locator_hidden": data["locator"] not in reference_response.text
            and data["final_locator"] not in reference_response.text,
        "content_body_hidden": data["content_bytes"].decode("ascii") not in reference_response.text,
    }
    if not all(reference_checks.values()):
        raise AssertionError("Artifact reference check failed: "
                             + json.dumps(reference_checks, sort_keys=True))

    hidden_project_path = f"/api/v1/projects/{uuid.uuid4()}/output-requests/{request_id}/artifact"
    hidden_project = get(hidden_project_path)
    unknown_request = get(
        f"/api/v1/projects/{project_id}/output-requests/{uuid.uuid4()}/artifact"
    )
    if hidden_project.status_code != 404 or unknown_request.status_code != 404:
        raise AssertionError("cross-project or unknown Artifact lookup was not hidden")

    content = get(reference["content_url"])
    if (content.status_code != 200 or content.content != data["content_bytes"]
            or hashlib.sha256(content.content).digest() != data["content_hash"]
            or len(content.content) != data["size"]
            or content.headers.get("content-type") != data["mime"]):
        raise AssertionError("Document download HTTP bytes/hash/size/MIME mismatch")

    hidden_document = get(
        f"/api/v1/projects/{uuid.uuid4()}/documents/{document_id}"
        f"/versions/{version_id}/content"
    )
    if hidden_document.status_code != 404 or data["content_bytes"] in hidden_document.content:
        raise AssertionError("cross-project Document content was not hidden")

    storage_path = storage_root.joinpath(*data["final_locator"].split("/"))
    if not storage_path.is_file() or storage_root not in storage_path.parents:
        raise AssertionError("synthetic storage path escaped isolated runner root")
    original = storage_path.read_bytes()
    corrupted = b"X" * len(original)
    if corrupted == original:
        corrupted = bytes([original[0] ^ 1]) + original[1:]
    try:
        storage_path.write_bytes(corrupted)
        rejected = get(reference["content_url"])
        if (rejected.status_code == 200 or corrupted in rejected.content
                or data["locator"] in rejected.text
                or data["final_locator"] in rejected.text):
            raise AssertionError("corrupt content was streamed or its locator disclosed")
    finally:
        storage_path.write_bytes(original)

    return {
        "authorized_reference_http": "PASS",
        "document_stream_bytes_hash_size_mime": "PASS",
        "cross_project_and_unknown_reference_hidden": "PASS",
        "cross_project_document_content_hidden": "PASS",
        "corrupt_file_failed_closed": "PASS",
        "storage_locator_disclosed": False,
        "customer_data": False,
        "external_calls": 0,
        "production_trust_used": False,
        "runner_temp_storage_only": True,
    }
