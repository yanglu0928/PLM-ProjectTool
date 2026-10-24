"""Opt-in Secret metadata detail endpoint; no secret value crosses this boundary."""

from __future__ import annotations

import uuid
import re

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.secret_metadata import (
    SecretMetadataError, SecretMetadataQuery, SecretMetadataService, SecretMetadataView,
)
from plm_assistant.modules.platform.api.secret_list_cursor import SecretListCursorCodec


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _public(view: SecretMetadataView) -> dict[str, object]:
    return {
        "secret_id": str(view.secret_id),
        "purpose": view.purpose,
        "state": view.state,
        "allowed_consumer": view.allowed_consumer,
        "current_version_no": view.current_version_no,
        "created_at": view.created_at.isoformat(),
        "updated_at": view.updated_at.isoformat(),
    }


def _read_token(request: Request, origins: LoginOriginPolicy) -> bytes:
    headers = tuple(request.scope.get("headers", ()))
    try:
        origins.require_trusted_host(headers)
    except LoginOriginError:
        raise ApplicationError("AUTH_CSRF_INVALID") from None
    return _session_cookie(headers)


async def _validate_session(sessions: SessionService, token: bytes) -> None:
    try:
        await run_in_threadpool(sessions.validate, token)
    except SessionError:
        raise ApplicationError("AUTH_SESSION_EXPIRED") from None
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def _metadata_error(exc: SecretMetadataError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "SECRET_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SECRET_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_secret_metadata_detail_router(*, sessions: SessionService,
                                         metadata: SecretMetadataService,
                                         origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or metadata is None or origins is None:
        raise ValueError("session, secret metadata and origins are required")
    router = APIRouter()

    @router.get("/api/v1/admin/secrets/{secret_id}")
    async def get_secret_metadata(secret_id: uuid.UUID, request: Request) -> JSONResponse:
        token = _read_token(request, origins)
        await _validate_session(sessions, token)
        try:
            view = await run_in_threadpool(
                metadata.get,
                SecretMetadataQuery(token, uuid.UUID(request.state.trace_id)),
                secret_id,
            )
        except SecretMetadataError as exc:
            raise _metadata_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view.lock_version) is not int or view.lock_version < 0:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": f'"v{view.lock_version}"'},
        )

    return router


def create_secret_metadata_list_router(*, sessions: SessionService,
                                       metadata: SecretMetadataService,
                                       origins: LoginOriginPolicy,
                                       cursors: SecretListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, metadata, origins, cursors)):
        raise ValueError("session, metadata, origins and cursor codec are required")
    router = APIRouter()

    @router.get("/api/v1/admin/secrets")
    async def list_secret_metadata(request: Request) -> JSONResponse:
        token = _read_token(request, origins)
        await _validate_session(sessions, token)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        after = None
        if "cursor" in params:
            after = cursors.decode(params["cursor"], session_token=token, page_size=page_size)
        try:
            rows = await run_in_threadpool(
                metadata.list_http_page,
                SecretMetadataQuery(token, uuid.UUID(request.state.trace_id)),
                after=after, limit=page_size + 1,
            )
        except SecretMetadataError as exc:
            raise _metadata_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(rows) is not list or len(rows) > page_size + 1:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        has_more = len(rows) > page_size
        page = rows[:page_size]
        next_cursor = (cursors.encode(
            session_token=token, page_size=page_size,
            created_at=page[-1].created_at, secret_id=page[-1].secret_id,
        ) if has_more else None)
        return JSONResponse(
            {"data": {"items": [_public(row) for row in page],
                      "next_cursor": next_cursor, "has_more": has_more},
             "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    return router
