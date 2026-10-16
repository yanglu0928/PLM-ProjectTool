"""Opt-in authorized DocumentVersion content streaming from verified snapshots."""

from __future__ import annotations

import threading
import uuid
import re
from collections.abc import AsyncIterator
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.document.api.read_documents import _query
from plm_assistant.modules.document.application.prepare_download import (
    DownloadError, VerifiedDownload,
)
from plm_assistant.modules.document.application.read_documents import DocumentReadQuery
from plm_assistant.modules.platform.application.errors import ApplicationError


_MIME = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+\Z", re.ASCII)


class DownloadServicePort(Protocol):
    def prepare(self, query: DocumentReadQuery, document_id: uuid.UUID,
                document_version_id: uuid.UUID) -> VerifiedDownload: ...


def _error(exc: DownloadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "FILE_INTEGRITY_MISMATCH": "FILE_INTEGRITY_MISMATCH",
        "FILE_UNAVAILABLE": "FILE_CONTENT_UNAVAILABLE",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_document_download_router(*, sessions: SessionService,
                                    downloads: DownloadServicePort,
                                    origins: LoginOriginPolicy,
                                    max_inflight: int = 4) -> APIRouter:
    if (any(item is None for item in (sessions, downloads, origins))
            or type(max_inflight) is not int or not 1 <= max_inflight <= 20):
        raise ValueError("bounded Document download dependencies are required")
    router = APIRouter()
    slots = threading.BoundedSemaphore(max_inflight)

    async def download_for(request: Request, *, scope: str,
                           project_id: uuid.UUID | None, document_id: uuid.UUID,
                           version_id: uuid.UUID) -> StreamingResponse:
        query = await _query(request, sessions=sessions, origins=origins,
                             scope=scope, project_id=project_id)
        if request.url.query or "range" in request.headers or "if-range" in request.headers:
            raise ApplicationError("REQUEST_MALFORMED")
        if not slots.acquire(blocking=False):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            try:
                ready = await run_in_threadpool(
                    downloads.prepare, query, document_id, version_id,
                )
            except DownloadError as exc:
                raise _error(exc) from None
            if (type(ready) is not VerifiedDownload
                    or ready.document_version_id != version_id
                    or type(ready.size_bytes) is not int
                    or not 0 <= ready.size_bytes <= 100_000_000
                    or type(ready.detected_mime) is not str
                    or _MIME.fullmatch(ready.detected_mime) is None):
                if isinstance(ready, VerifiedDownload):
                    ready.close()
                raise ApplicationError("SYSTEM_UNAVAILABLE")
        except Exception:
            slots.release()
            raise
        close_lock = threading.Lock()
        closed = False

        def cleanup() -> None:
            nonlocal closed
            with close_lock:
                if closed:
                    return
                closed = True
                try:
                    ready.close()
                finally:
                    slots.release()

        async def chunks() -> AsyncIterator[bytes]:
            try:
                while True:
                    chunk = await run_in_threadpool(ready.stream.read, 1_048_576)
                    if not chunk:
                        break
                    yield chunk
            finally:
                cleanup()

        try:
            return StreamingResponse(
                chunks(), media_type=ready.detected_mime,
                headers={
                    "Content-Length": str(ready.size_bytes),
                    "Content-Disposition": f'attachment; filename="document-{version_id}.bin"',
                    "X-Content-Type-Options": "nosniff",
                    "Cache-Control": "no-store",
                },
                background=BackgroundTask(cleanup),
            )
        except Exception:
            cleanup()
            raise

    @router.get("/api/v1/projects/{project_id}/documents/{document_id}/versions/{version_id}/content")
    async def project_content(project_id: uuid.UUID, document_id: uuid.UUID,
                              version_id: uuid.UUID, request: Request) -> StreamingResponse:
        return await download_for(request, scope="PROJECT", project_id=project_id,
                                  document_id=document_id, version_id=version_id)

    @router.get("/api/v1/global/documents/{document_id}/versions/{version_id}/content")
    async def global_content(document_id: uuid.UUID, version_id: uuid.UUID,
                             request: Request) -> StreamingResponse:
        return await download_for(request, scope="GLOBAL", project_id=None,
                                  document_id=document_id, version_id=version_id)

    return router
