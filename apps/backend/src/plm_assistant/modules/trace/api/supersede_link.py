"""Opt-in frozen TraceLink supersede HTTP; no default/platform mounting."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.trace.application.supersede_link import (
    SupersedeTraceLinkRefs, SupersededTraceLink, TraceSupersedeError,
    TraceSupersedeService,
)
from plm_assistant.modules.trace.application.target_proof import TraceResourceVersionRef


MAX_SUPERSEDE_BODY = 8192


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


def _canonical_uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _ref(value: object) -> TraceResourceVersionRef:
    if type(value) is not dict or set(value) != {
            "resource_type", "resource_id", "version_id"}:
        raise ApplicationError("REQUEST_MALFORMED")
    if type(value["resource_type"]) is not str or not value["resource_type"]:
        raise ApplicationError("VALIDATION_FAILED")
    return TraceResourceVersionRef(
        value["resource_type"], _canonical_uuid(value["resource_id"]),
        _canonical_uuid(value["version_id"]),
    )


async def _read_body(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> tuple[
        TraceResourceVersionRef, TraceResourceVersionRef, str]:
    content_types = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(content_types) != 1
            or content_types[0].strip().lower() not in (
                b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_SUPERSEDE_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            body = json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)
    if type(body) is not dict or set(body) != {"source", "target", "relation_type"}:
        raise ApplicationError("REQUEST_MALFORMED")
    if type(body["relation_type"]) is not str or not body["relation_type"]:
        raise ApplicationError("VALIDATION_FAILED")
    return _ref(body["source"]), _ref(body["target"]), body["relation_type"]


def create_trace_supersede_router(*, sessions: SessionService,
                                  supersedes: TraceSupersedeService,
                                  origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or supersedes is None or origins is None:
        raise ValueError("Trace supersede HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/trace-links/{trace_link_id}:supersede",
                 operation_id="TRACE_LINK_SUPERSEDE", status_code=201)
    async def supersede_link(project_id: uuid.UUID, trace_link_id: uuid.UUID,
                             request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        csrf = _csrf_header(headers)
        key = _idempotency_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected = parse_if_match(headers)
        if project_id.int == 0 or trace_link_id.int == 0:
            raise ApplicationError("RESOURCE_NOT_FOUND")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        source, target, relation_type = await _read_body(request, headers)
        try:
            result = await run_in_threadpool(
                supersedes.supersede_refs,
                SupersedeTraceLinkRefs(
                    token, csrf, uuid.UUID(request.state.trace_id),
                    project_id, trace_link_id, expected,
                    source, target, relation_type,
                ),
                idempotency_key=key,
            )
        except TraceSupersedeError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "CONFLICT_STATE": "CONFLICT_STATE",
                "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not SupersededTraceLink
                or result.trace_link_id != trace_link_id
                or type(result.replacement_id) is not uuid.UUID
                or result.replacement_id.int == 0
                or result.lock_version != 1):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": {"trace_link_id": str(result.replacement_id)},
             "trace_id": request.state.trace_id},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": '"v0"',
                     "X-Content-Type-Options": "nosniff"},
        )

    return router
