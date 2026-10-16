"""Opt-in project AI Task submission HTTP contract; no Provider call."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.api.egress import _canonical_uuid, _read_json, _source_ref
from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateError, AITaskCreateService, CreateAITask, CreatedAITask,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError


_FIELDS = frozenset({
    "task_type", "input_refs", "prompt_policy_ref", "output_schema_ref",
    "context_policy_ref", "task_parameters", "egress_authorization_ref",
})
_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_PARAMETER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _command(body: object, *, token: bytes, csrf: bytes,
             trace_id: uuid.UUID, project_id: uuid.UUID) -> CreateAITask:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    refs, parameters = body["input_refs"], body["task_parameters"]
    string_fields = ("task_type", "prompt_policy_ref", "output_schema_ref", "context_policy_ref")
    if (any(type(body[name]) is not str for name in string_fields)
            or any(_REF.fullmatch(body[name]) is None
                   for name in string_fields[1:])
            or type(refs) is not list or not 1 <= len(refs) <= 1000
            or type(parameters) is not dict or len(parameters) > 16
            or any(type(key) is not str or _PARAMETER.fullmatch(key) is None
                   or type(value) not in (str, int, bool)
                   for key, value in parameters.items())):
        raise ApplicationError("VALIDATION_FAILED")
    return CreateAITask(
        token, csrf, trace_id, project_id, body["task_type"],
        tuple(_source_ref(item) for item in refs), body["prompt_policy_ref"],
        body["output_schema_ref"], body["context_policy_ref"], dict(parameters),
        _canonical_uuid(body["egress_authorization_ref"]),
    )


def _error(exc: AITaskCreateError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "AI_TASK_POLICY_INVALID": "AI_PROMPT_VERSION_INVALID",
        "AI_TASK_PROMPT_UNAVAILABLE": "AI_PROMPT_VERSION_INVALID",
        "AI_EGRESS_AUTHORIZATION_INVALID": "AI_EGRESS_AUTHORIZATION_REQUIRED",
        "AI_INPUT_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_task_create_router(*, sessions: SessionService,
                                 tasks: AITaskCreateService,
                                 origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, tasks, origins)):
        raise ValueError("session, AI Task service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/ai-tasks")
    async def create_ai_task(project_id: uuid.UUID, request: Request) -> JSONResponse:
        if not project_id.int or request.url.query:
            raise ApplicationError(
                "RESOURCE_NOT_FOUND" if not project_id.int else "REQUEST_MALFORMED"
            )
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        body = await _read_json(request, headers)
        command = _command(
            body, token=token, csrf=csrf,
            trace_id=uuid.UUID(request.state.trace_id), project_id=project_id,
        )
        try:
            result = await run_in_threadpool(tasks.create, command, idempotency_key=key)
        except AITaskCreateError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not CreatedAITask
                or not result.ai_task_id.int or not result.job_id.int):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        location = f"/api/v1/projects/{project_id}/ai-tasks/{result.ai_task_id}"
        return JSONResponse(
            {"data": {"ai_task_id": str(result.ai_task_id),
                       "job_id": str(result.job_id)},
             "trace_id": request.state.trace_id},
            status_code=202,
            headers={"Cache-Control": "no-store", "Location": location},
        )

    return router
