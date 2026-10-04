"""Opt-in PromptVersion POST; production mounting requires packaged admission trust."""

from __future__ import annotations

import hmac
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, AppendedPromptVersion, PromptVersionAppendError,
    PromptVersionAppendService,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft, PromptVersionError
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


MAX_PROMPT_VERSION_BODY = 2_097_152
_FIELDS = frozenset({"task_type", "system_template", "user_template",
                     "output_schema_ref", "schema_version", "rag_policy_ref",
                     "provider_policy_ref"})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> object:
    raise ValueError("nonstandard JSON constant")


async def _read_json(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
    content_types = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(content_types) != 1 or content_types[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_PROMPT_VERSION_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(raw.decode("utf-8", "strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def _command(body: object, *, token: bytes, csrf: bytes, trace_id: uuid.UUID,
             template_id: uuid.UUID, expected: int, key: str) -> AppendPromptVersion:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (any(type(body[name]) is not str for name in _FIELDS - {"schema_version"})
            or type(body["schema_version"]) is not int):
        raise ApplicationError("VALIDATION_FAILED")
    try:
        task_type = PromptTaskType(body["task_type"])
    except ValueError:
        raise ApplicationError("VALIDATION_FAILED") from None
    return AppendPromptVersion(
        token, csrf, trace_id, template_id, task_type,
        body["system_template"], body["user_template"],
        body["output_schema_ref"], body["schema_version"],
        body["rag_policy_ref"], body["provider_policy_ref"], expected, key,
    )


def _error(exc: PromptVersionAppendError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "AI_PROMPT_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "AI_PROMPT_STATE_CONFLICT": "CONFLICT_STATE",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "AI_PROMPT_CONTENT_UNAPPROVED": "VALIDATION_FAILED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_ai_prompt_version_router(*, sessions: SessionService,
                                    versions: PromptVersionAppendService,
                                    origins: LoginOriginPolicy) -> APIRouter:
    if any(item is None for item in (sessions, versions, origins)):
        raise ValueError("session, PromptVersion service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/admin/ai/prompt-templates/{prompt_template_id}/versions")
    async def create_prompt_version(prompt_template_id: uuid.UUID, request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (
            _session_cookie(headers), _csrf_header(headers), _idempotency_header(headers),
        )
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf,
                                    require_csrf=True)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected = parse_if_match(headers)
        if prompt_template_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        command = _command(body, token=token, csrf=csrf,
                           trace_id=uuid.UUID(request.state.trace_id),
                           template_id=prompt_template_id, expected=expected, key=key)
        try:
            result = await run_in_threadpool(versions.append, command)
        except PromptVersionAppendError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not AppendedPromptVersion
                or result.prompt_template_id != prompt_template_id
                or result.expected_lock_version != expected):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        try:
            result.__post_init__()
            draft = PromptVersionDraft(
                command.prompt_template_id, command.task_type,
                command.system_template, command.user_template,
                command.output_schema_ref, command.schema_version,
                command.rag_policy_ref, command.provider_policy_ref,
            )
        except (PromptVersionAppendError, PromptVersionError):
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (not hmac.compare_digest(result.content_fingerprint, draft.fingerprint)
                or result.system_hash != draft.system_hash
                or result.user_hash != draft.user_hash
                or result.output_schema_ref != draft.output_schema_ref
                or result.schema_version != draft.schema_version
                or result.rag_policy_ref != draft.rag_policy_ref
                or result.provider_policy_ref != draft.provider_policy_ref):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = f'"v{result.lock_version}"'
        location = (f"/api/v1/admin/ai/prompt-templates/{prompt_template_id}"
                    f"/versions/{result.version_no}")
        return JSONResponse(
            {"data": {"prompt_template_id": str(prompt_template_id),
                      "version_no": result.version_no, "task_type": command.task_type.value,
                      "system_hash": result.system_hash, "user_hash": result.user_hash,
                      "output_schema_ref": result.output_schema_ref,
                      "schema_version": result.schema_version,
                      "rag_policy_ref": result.rag_policy_ref,
                      "provider_policy_ref": result.provider_policy_ref,
                      "etag": etag}, "trace_id": request.state.trace_id},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag, "Location": location},
        )

    return router
