"""Opt-in frozen upload Commit/Abort HTTP contract; no default mount."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.document.application.abort_upload import (
    AbortUpload, AbortedUpload, AbortUploadService, UploadAbortError,
)
from plm_assistant.modules.document.application.commit_upload import (
    CommitUpload, CommittedUpload, CommitUploadService, UploadCommitError,
)
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccessError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError


def _error(exc: UploadCommitError | UploadAbortError | DocumentUploadAccessError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PRECONDITION_REQUIRED": "CONFLICT_VERSION_REQUIRED",
        "FILE_UPLOAD_EXPIRED": "FILE_UPLOAD_EXPIRED",
        "FILE_INTEGRITY_MISMATCH": "FILE_INTEGRITY_MISMATCH",
        "FILE_UNAVAILABLE": "FILE_CONTENT_UNAVAILABLE",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def _optional_if_match(headers: tuple[tuple[bytes, bytes], ...]) -> int | None:
    if any(name.lower() == b"if-match" for name, _ in headers):
        return parse_if_match(headers)
    return None


def create_document_upload_finalize_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    commit_factory: Callable[[bytes, bytes], CommitUploadService],
    abort_factory: Callable[[bytes, bytes], AbortUploadService],
    max_bytes: int = 100_000_000,
) -> APIRouter:
    if (any(item is None for item in (sessions, origins, commit_factory, abort_factory))
            or type(max_bytes) is not int or max_bytes <= 0):
        raise ValueError("upload finalize dependencies are required")
    router = APIRouter()

    async def _principal(request: Request, *, scope: str,
                         project_id: uuid.UUID | None,
                         upload_id: uuid.UUID) -> tuple[bytes, bytes, str, uuid.UUID]:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers)
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
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        return token, csrf, key, principal.user_id

    async def _commit(request: Request, *, scope: str,
                      project_id: uuid.UUID | None,
                      upload_id: uuid.UUID) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        token, csrf, key, actor_id = await _principal(
            request, scope=scope, project_id=project_id, upload_id=upload_id,
        )
        expected = _optional_if_match(headers)
        command = CommitUpload(
            upload_id, scope, project_id, actor_id,
            uuid.UUID(request.state.trace_id), expected, max_bytes,
        )
        try:
            result = await run_in_threadpool(
                commit_factory(token, csrf).commit, command, idempotency_key=key,
            )
        except (UploadCommitError, DocumentUploadAccessError) as exc:
            raise _error(exc) from None
        except IdempotencyError:
            raise ApplicationError("CONFLICT_IDEMPOTENCY") from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not CommittedUpload or result.upload_id != upload_id
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    result.document_id, result.document_version_id, result.parse_job_id,
                ))
                or type(result.version_no) is not int or result.version_no <= 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        base = "/api/v1/global" if scope == "GLOBAL" else f"/api/v1/projects/{project_id}"
        return JSONResponse({"data": {
            "upload_id": str(upload_id), "document_id": str(result.document_id),
            "document_version_id": str(result.document_version_id),
            "version_no": result.version_no, "parse_job_id": str(result.parse_job_id),
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store",
            "Location": f"{base}/documents/{result.document_id}/versions/{result.document_version_id}",
        })

    async def _abort(request: Request, *, scope: str,
                     project_id: uuid.UUID | None,
                     upload_id: uuid.UUID) -> JSONResponse:
        token, csrf, key, actor_id = await _principal(
            request, scope=scope, project_id=project_id, upload_id=upload_id,
        )
        command = AbortUpload(upload_id, scope, project_id, actor_id,
                              uuid.UUID(request.state.trace_id))
        try:
            result = await run_in_threadpool(
                abort_factory(token, csrf).abort, command, idempotency_key=key,
            )
        except (UploadAbortError, DocumentUploadAccessError) as exc:
            raise _error(exc) from None
        except IdempotencyError:
            raise ApplicationError("CONFLICT_IDEMPOTENCY") from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not AbortedUpload or result.upload_id != upload_id
                or type(result.cleanup_pending) is not bool):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            "upload_id": str(upload_id), "state": "ABORTED",
            "cleanup_pending": result.cleanup_pending,
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/global/document-uploads/{upload_id}:commit")
    async def commit_global(upload_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _commit(request, scope="GLOBAL", project_id=None, upload_id=upload_id)

    @router.post("/api/v1/projects/{project_id}/document-uploads/{upload_id}:commit")
    async def commit_project(project_id: uuid.UUID, upload_id: uuid.UUID,
                             request: Request) -> JSONResponse:
        return await _commit(request, scope="PROJECT", project_id=project_id,
                             upload_id=upload_id)

    @router.post("/api/v1/global/document-uploads/{upload_id}:abort")
    async def abort_global(upload_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _abort(request, scope="GLOBAL", project_id=None, upload_id=upload_id)

    @router.post("/api/v1/projects/{project_id}/document-uploads/{upload_id}:abort")
    async def abort_project(project_id: uuid.UUID, upload_id: uuid.UUID,
                            request: Request) -> JSONResponse:
        return await _abort(request, scope="PROJECT", project_id=project_id,
                            upload_id=upload_id)

    return router
