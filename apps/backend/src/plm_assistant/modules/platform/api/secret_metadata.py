"""Opt-in Secret metadata detail endpoint; no secret value crosses this boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.secret_metadata import (
    SecretMetadataError, SecretMetadataQuery, SecretMetadataService,
)


def create_secret_metadata_detail_router(*, sessions: SessionService,
                                         metadata: SecretMetadataService,
                                         origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or metadata is None or origins is None:
        raise ValueError("session, secret metadata and origins are required")
    router = APIRouter()

    @router.get("/api/v1/admin/secrets/{secret_id}")
    async def get_secret_metadata(secret_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        try:
            await run_in_threadpool(sessions.validate, token)
        except SessionError:
            raise ApplicationError("AUTH_SESSION_EXPIRED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        try:
            view = await run_in_threadpool(
                metadata.get,
                SecretMetadataQuery(token, uuid.UUID(request.state.trace_id)),
                secret_id,
            )
        except SecretMetadataError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
                "SECRET_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "SECRET_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view.lock_version) is not int or view.lock_version < 0:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {
                "secret_id": str(view.secret_id),
                "purpose": view.purpose,
                "state": view.state,
                "allowed_consumer": view.allowed_consumer,
                "current_version_no": view.current_version_no,
                "created_at": view.created_at.isoformat(),
                "updated_at": view.updated_at.isoformat(),
            }, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": f'"v{view.lock_version}"'},
        )

    return router
