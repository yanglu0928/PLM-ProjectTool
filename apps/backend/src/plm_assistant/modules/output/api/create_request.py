"""Opt-in OUTPUT_REQUEST_CREATE HTTP adapter; never mounted by default."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError,
    LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header,
    _idempotency_header,
    _session_cookie,
    _session_failure,
)
from plm_assistant.modules.auth.application.session_service import (
    SessionError,
    SessionService,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.output.application.create_request import (
    CreateOutputRequest,
    CreatedOutputRequest,
    OutputRequestError,
    OutputRequestService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.platform.application.idempotency import IdempotencyError
from plm_assistant.modules.project.api.create_project import (
    _canonical_uuid,
    _read_json,
)

_ERROR_MAP = {
    "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
    "FORBIDDEN": "RESOURCE_NOT_FOUND",
    "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
    "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
    "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
    "VALIDATION_FAILED": "VALIDATION_FAILED",
    "SYSTEM_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
}
_BODY_FIELDS = frozenset({
    "output_type",
    "template_version_ref",
    "source_version_refs",
    "output_policy_ref",
    "plugin_operation",
})
_OUTPUT_TYPES = frozenset({"DOCX", "PPTX", "PNG", "JPEG"})
_OUTPUT_STATES = frozenset({
    "REQUESTED", "QUEUED", "GENERATING", "VALIDATING",
    "SUCCEEDED", "FAILED", "CANCEL_REQUESTED", "CANCELLED",
})


def _create_command(
    body: object, *, token: bytes, csrf: bytes,
    project_id: uuid.UUID, trace_id: uuid.UUID,
) -> CreateOutputRequest:
    if type(body) is not dict or set(body) != _BODY_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(body["output_type"]) is not str
            or body["output_type"] not in _OUTPUT_TYPES
            or type(body["source_version_refs"]) is not list
            or not 1 <= len(body["source_version_refs"]) <= 64
            or type(body["output_policy_ref"]) is not str
            or type(body["plugin_operation"]) is not str):
        raise ApplicationError("VALIDATION_FAILED")
    template_ref = _canonical_uuid(body["template_version_ref"])
    source_refs = tuple(_canonical_uuid(value) for value in body["source_version_refs"])
    if len(set(source_refs)) != len(source_refs):
        raise ApplicationError("VALIDATION_FAILED")
    return CreateOutputRequest(
        session_token=token,
        csrf_token=csrf,
        trace_id=trace_id,
        project_id=project_id,
        output_type=body["output_type"],
        template_version_ref=template_ref,
        source_version_refs=source_refs,
        output_policy_ref=body["output_policy_ref"],
        plugin_operation=body["plugin_operation"],
    )


def _output_error(error: OutputRequestError) -> ApplicationError:
    return ApplicationError(_ERROR_MAP.get(error.code, "SYSTEM_UNAVAILABLE"))


def create_output_request_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service: OutputRequestService,
) -> APIRouter:
    """Build the single frozen Create route for explicit test/composition use."""
    if any(value is None for value in (sessions, origins, service)):
        raise ValueError("Output Create HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/output-requests")
    async def create_output_request(
        project_id: uuid.UUID, request: Request,
    ) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers),
            _csrf_header(headers),
            _idempotency_header(headers),
        )
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
        if type(project_id) is not uuid.UUID or project_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        try:
            trace_id = _canonical_uuid(request.state.trace_id)
        except (AttributeError, ApplicationError):
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        body = await _read_json(request, headers)
        command = _create_command(
            body, token=token, csrf=csrf, project_id=project_id,
            trace_id=trace_id,
        )
        try:
            result = await run_in_threadpool(
                service.create, command, idempotency_key=key,
            )
        except OutputRequestError as exc:
            raise _output_error(exc) from None
        except IdempotencyError:
            raise ApplicationError("CONFLICT_IDEMPOTENCY") from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not CreatedOutputRequest
                or result.project_id != project_id
                or type(result.output_request_id) is not uuid.UUID
                or result.output_request_id.int == 0
                or type(result.job_id) is not uuid.UUID or result.job_id.int == 0
                or type(result.request_state) is not str
                or result.request_state not in _OUTPUT_STATES
                or result.status_code != 202):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {
                "data": {
                    "output_request_id": str(result.output_request_id),
                    "job_id": str(result.job_id),
                    "state": result.request_state,
                },
                "trace_id": request.state.trace_id,
            },
            status_code=202,
            headers={"Cache-Control": "no-store"},
        )

    return router
