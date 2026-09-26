"""Opt-in bounded Content PUT over the existing two-phase upload service."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator

from anyio import from_thread
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _csrf_header, _session_cookie, _session_failure
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.document.application.receive_upload_content import (
    ReceiveUploadContent, ReceiveUploadContentService, ReceivedUploadContent, UploadContentError,
)
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccessError
from plm_assistant.modules.document.infrastructure.content_spool import ContentSpoolError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.errors import ApplicationError


_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)
_SHA = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_LENGTH = re.compile(r"[1-9][0-9]*\Z", re.ASCII)
_CHUNK = 1_048_576


def _single_header(headers: tuple[tuple[bytes, bytes], ...], name: bytes) -> str:
    try:
        values = [value.decode("ascii") for key, value in headers if key.lower() == name]
        if len(values) != 1:
            raise ValueError()
        return values[0]
    except (UnicodeDecodeError, ValueError):
        raise ApplicationError("REQUEST_MALFORMED") from None


def _claims(headers: tuple[tuple[bytes, bytes], ...], *, max_bytes: int) -> tuple[str, int, bytes]:
    if _single_header(headers, b"content-type").strip().lower() != "application/octet-stream":
        raise ApplicationError("REQUEST_MALFORMED")
    token = _single_header(headers, b"x-upload-token")
    sha = _single_header(headers, b"x-content-sha256")
    length_text = _single_header(headers, b"content-length")
    if (_TOKEN.fullmatch(token) is None or _SHA.fullmatch(sha) is None
            or len(length_text) > 20 or _LENGTH.fullmatch(length_text) is None):
        raise ApplicationError("VALIDATION_FAILED")
    length = int(length_text)
    if length > max_bytes:
        raise ApplicationError("FILE_TOO_LARGE")
    return token, length, bytes.fromhex(sha)


def _chunks(request: Request) -> Iterator[bytes]:
    """Pull the async body from an AnyIO worker; never collect the whole body."""
    stream = request.stream()

    async def next_chunk() -> bytes:
        return await anext(stream)

    while True:
        try:
            chunk = from_thread.run(next_chunk)
        except StopAsyncIteration:
            return
        if type(chunk) is not bytes:
            raise UploadContentError("VALIDATION_FAILED")
        for offset in range(0, len(chunk), _CHUNK):
            yield chunk[offset:offset + _CHUNK]


def _error(exc: UploadContentError | ContentSpoolError | DocumentUploadAccessError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "FILE_UPLOAD_EXPIRED": "FILE_UPLOAD_EXPIRED",
        "FILE_TOO_LARGE": "FILE_TOO_LARGE",
        "FILE_TYPE_UNSUPPORTED": "FILE_TYPE_UNSUPPORTED",
        "FILE_INTEGRITY_MISMATCH": "FILE_INTEGRITY_MISMATCH",
        "FILE_CONTENT_UNAVAILABLE": "FILE_CONTENT_UNAVAILABLE",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_document_upload_content_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service_factory: Callable[[bytes, bytes], ReceiveUploadContentService],
    max_bytes: int = 100_000_000,
) -> APIRouter:
    if (sessions is None or origins is None or service_factory is None
            or type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError("content HTTP dependencies are required")
    router = APIRouter()

    async def _receive(request: Request, *, scope: str, project_id: uuid.UUID | None,
                       upload_id: uuid.UUID) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            principal = await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(getattr(principal, "user_id", None)) is not uuid.UUID
                or principal.user_id.int == 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        if (upload_id.int == 0 or scope == "PROJECT" and (
                type(project_id) is not uuid.UUID or project_id.int == 0)):
            raise ApplicationError("RESOURCE_NOT_FOUND")
        upload_token, length, sha256 = _claims(headers, max_bytes=max_bytes)
        command = ReceiveUploadContent(
            upload_id=upload_id, scope=scope, project_id=project_id,
            actor_id=principal.user_id, trace_id=uuid.UUID(request.state.trace_id),
            upload_token=upload_token, declared_length=length, declared_sha256=sha256,
        )
        try:
            service = service_factory(token, csrf)
            result = await run_in_threadpool(service.receive, command, chunks=_chunks(request))
        except (UploadContentError, ContentSpoolError, DocumentUploadAccessError) as exc:
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not ReceivedUploadContent
                or result.upload_id != upload_id
                or type(result.file_object_id) is not uuid.UUID or result.file_object_id.int == 0
                or type(result.size_bytes) is not int or result.size_bytes != length
                or type(result.sha256) is not bytes or len(result.sha256) != 32
                or result.sha256 != sha256 or type(result.detected_mime) is not str):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            "upload_id": str(result.upload_id), "size_bytes": result.size_bytes,
            "sha256": result.sha256.hex(), "detected_mime": result.detected_mime,
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    @router.put("/api/v1/global/document-uploads/{upload_id}/content")
    async def receive_global(upload_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _receive(request, scope="GLOBAL", project_id=None, upload_id=upload_id)

    @router.put("/api/v1/projects/{project_id}/document-uploads/{upload_id}/content")
    async def receive_project(project_id: uuid.UUID, upload_id: uuid.UUID,
                              request: Request) -> JSONResponse:
        return await _receive(request, scope="PROJECT", project_id=project_id,
                              upload_id=upload_id)

    return router
