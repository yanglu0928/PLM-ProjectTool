"""Opt-in OUTPUT_REQUEST_GET adapter; never mounted by default."""
from __future__ import annotations

import re
import uuid
from datetime import timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.output.application.read_request import (
    OutputRequestReadError, OutputRequestReadQuery, OutputRequestReadService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

_STATE = frozenset({
    "REQUESTED", "QUEUED", "GENERATING", "VALIDATING",
    "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED",
})


def output_request_view_data(view: object) -> dict[str, object]:
    if (type(view).__name__ != "OutputRequestView"
            or type(view.output_request_id) is not uuid.UUID
            or type(view.project_id) is not uuid.UUID
            or type(view.template_version_ref) is not uuid.UUID
            or type(view.context_snapshot_ref) is not uuid.UUID
            or type(view.source_version_refs) is not tuple
            or not view.source_version_refs
            or any(type(value) is not uuid.UUID for value in view.source_version_refs)
            or type(view.context_fingerprint) is not bytes
            or len(view.context_fingerprint) != 32
            or type(view.request_state) is not str
            or view.request_state not in _STATE
            or not re.fullmatch(r'"v(0|[1-9][0-9]*)"', f'"v{view.lock_version}"')
            or view.requested_at.tzinfo is None
            or (view.completed_at is not None and view.completed_at.tzinfo is None)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    data = {
        "output_request_id": str(view.output_request_id),
        "project_id": str(view.project_id),
        "output_type": view.output_type,
        "template_version_ref": str(view.template_version_ref),
        "source_version_refs": [str(value) for value in view.source_version_refs],
        "output_policy_ref": view.output_policy_ref,
        "plugin_operation": view.plugin_operation,
        "context_snapshot_ref": str(view.context_snapshot_ref),
        "context_fingerprint": view.context_fingerprint.hex(),
        "state": view.request_state,
        "job_ref": str(view.job_ref) if view.job_ref is not None else None,
        "execution_ref": str(view.execution_ref) if view.execution_ref is not None else None,
        "generation_no": view.generation_no,
        "requested_at": view.requested_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "completed_at": (
            view.completed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if view.completed_at is not None else None
        ),
        "etag": f'"v{view.lock_version}"',
    }
    return data


def _error(exc: OutputRequestReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


def create_output_request_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service: OutputRequestReadService,
):
    if any(value is None for value in (sessions, origins, service)):
        raise ValueError("OutputRequest read HTTP dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/output-requests/{output_request_id}")
    async def get_output_request(project_id: uuid.UUID,
                                 output_request_id: uuid.UUID,
                                 request: Request) -> JSONResponse:
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
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            trace_id = uuid.UUID(request.state.trace_id)
        except (AttributeError, TypeError, ValueError):
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        try:
            view = await run_in_threadpool(
                service.get, OutputRequestReadQuery(token, trace_id),
                project_id=project_id, output_request_id=output_request_id,
            )
        except OutputRequestReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = output_request_view_data(view)
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": data["etag"]},
        )

    return router
