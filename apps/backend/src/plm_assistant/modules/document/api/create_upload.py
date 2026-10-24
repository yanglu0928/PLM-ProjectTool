"""Opt-in UploadIntent HTTP; the production composition must supply a key-backed service."""

from __future__ import annotations

import uuid
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.document.application.create_upload_intent import (
    CreateUploadIntent, CreatedUploadIntent, CreateUploadIntentService, UploadIntentCreateError,
)
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccessError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.api.create_project import _read_json


class UploadLicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


_FIELDS = frozenset({
    "purpose", "category", "subtype", "document_purpose", "title",
    "display_name", "size_hint_bytes", "mime_hint", "document_id",
    "supersedes_version_id",
})
_UPLOAD_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _command(body: object, *, scope: str, project_id: uuid.UUID | None,
             actor_id: uuid.UUID, trace_id: uuid.UUID) -> CreateUploadIntent:
    if type(body) is not dict or "purpose" not in body or "display_name" not in body or set(body) - _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    target = _uuid(body["document_id"]) if body.get("document_id") is not None else None
    parent = (_uuid(body["supersedes_version_id"])
              if body.get("supersedes_version_id") is not None else None)
    if (type(body["purpose"]) is not str or type(body["display_name"]) is not str
            or target is None and ("category" not in body or "title" not in body)
            or target is None and parent is not None
            or target is not None and any(body.get(name) is not None for name in (
                "category", "subtype", "document_purpose", "title",
            ))):
        raise ApplicationError("VALIDATION_FAILED")
    return CreateUploadIntent(
        scope=scope, project_id=project_id, actor_id=actor_id, trace_id=trace_id,
        purpose_code=body["purpose"], target_document_id=target,
        supersedes_version_id=parent, document_category=body.get("category"),
        document_subtype=body.get("subtype"),
        document_purpose=body.get("document_purpose"), title=body.get("title"),
        original_display_name=body["display_name"],
        expected_size_bytes=body.get("size_hint_bytes"), mime_hint=body.get("mime_hint"),
    )


def _create_error(exc: UploadIntentCreateError | DocumentUploadAccessError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "FILE_UPLOAD_EXPIRED": "FILE_UPLOAD_EXPIRED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_document_upload_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    license_guard: UploadLicenseGuardPort,
    service_factory: Callable[[bytes, bytes], CreateUploadIntentService],
) -> APIRouter:
    if any(value is None for value in (sessions, origins, license_guard, service_factory)):
        raise ValueError("upload HTTP dependencies are required")
    router = APIRouter()

    async def _create(request: Request, *, scope: str,
                      project_id: uuid.UUID | None) -> JSONResponse:
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
        if type(getattr(principal, "user_id", None)) is not uuid.UUID or principal.user_id.int == 0:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        if scope == "PROJECT" and (type(project_id) is not uuid.UUID or project_id.int == 0):
            raise ApplicationError("RESOURCE_NOT_FOUND")
        trace_id = uuid.UUID(request.state.trace_id)
        body = await _read_json(request, headers)
        command = _command(body, scope=scope, project_id=project_id,
                           actor_id=principal.user_id, trace_id=trace_id)
        try:
            await run_in_threadpool(license_guard.require_valid, trace_id=trace_id)
            service = service_factory(token, csrf)
            result = await run_in_threadpool(service.create, command, idempotency_key=key)
        except (UploadIntentCreateError, DocumentUploadAccessError) as exc:
            raise _create_error(exc) from None
        except IdempotencyError:
            raise ApplicationError("CONFLICT_IDEMPOTENCY") from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not CreatedUploadIntent or type(result.upload_id) is not uuid.UUID
                or result.upload_id.int == 0 or type(result.upload_token) is not str
                or _UPLOAD_TOKEN.fullmatch(result.upload_token) is None
                or type(result.expires_at) is not datetime
                or result.expires_at.tzinfo is None or result.expires_at.utcoffset() is None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        base = "/api/v1/global" if scope == "GLOBAL" else f"/api/v1/projects/{project_id}"
        return JSONResponse({"data": {
            "upload_id": str(result.upload_id), "upload_token": result.upload_token,
            "expires_at": result.expires_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "Location": f"{base}/document-uploads/{result.upload_id}",
        })

    @router.post("/api/v1/global/document-uploads")
    async def create_global(request: Request) -> JSONResponse:
        return await _create(request, scope="GLOBAL", project_id=None)

    @router.post("/api/v1/projects/{project_id}/document-uploads")
    async def create_project(project_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _create(request, scope="PROJECT", project_id=project_id)

    return router
