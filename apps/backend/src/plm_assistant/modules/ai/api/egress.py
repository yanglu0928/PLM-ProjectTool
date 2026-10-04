"""Opt-in project Egress Preview and Authorization HTTP contracts."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.ai.application.egress_authorization import (
    AuthorizeEgress,
    EgressAuthorizationError,
    EgressAuthorizationService,
    EgressAuthorizationView,
    EgressAuthorizeResult,
    EgressRevokeResult,
    RevokeEgress,
)
from plm_assistant.modules.ai.application.egress_preview import (
    CreateEgressPreview,
    EgressPreviewError,
    EgressPreviewQuery,
    EgressPreviewService,
    EgressPreviewSourceView,
    EgressPreviewView,
)
from plm_assistant.modules.ai.application.egress_task_plan import (
    AIEgressTaskPlanError,
    AITaskPreviewPlanRequest,
)
from plm_assistant.modules.ai.application.input_resolution import AIInputResourceVersionRef
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header,
    _idempotency_header,
    _session_cookie,
    _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


MAX_EGRESS_BODY = 262_144
_PREVIEW_COMMON_FIELDS = frozenset({
    "purpose_ref", "operation_type", "provider_id", "model_id", "source_refs",
    "allowed_data_categories", "minimal_payload_policy_ref", "max_payload_bytes",
    "max_input_tokens", "max_retry_attempts",
})
_AI_TASK_PREVIEW_FIELDS = _PREVIEW_COMMON_FIELDS | {"ai_task_plan"}
_OTHER_PREVIEW_FIELDS = _PREVIEW_COMMON_FIELDS | {
    "estimated_record_count", "payload_fingerprint",
}
_TASK_PLAN_FIELDS = frozenset({
    "task_type", "prompt_policy_ref", "output_schema_ref", "context_policy_ref",
    "task_parameters",
})
_SOURCE_FIELDS = frozenset({"resource_type", "resource_id", "version_id"})
_AUTHORIZE_FIELDS = frozenset({
    "expected_preview_fingerprint", "allowed_data_categories", "max_record_count",
    "max_payload_bytes", "max_input_tokens", "max_retry_attempts", "valid_until",
})
_REVOKE_FIELDS = frozenset({"reason_code", "reason_summary"})
_HEX_32 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z", re.ASCII)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_json(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
    content_types = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(content_types) != 1 or content_types[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_EGRESS_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(
                raw.decode("utf-8", errors="strict"), object_pairs_hook=_unique_pairs,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


def _canonical_uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if not parsed.int or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _fingerprint(value: object) -> bytes:
    if type(value) is not str or _HEX_32.fullmatch(value) is None:
        raise ApplicationError("VALIDATION_FAILED")
    return bytes.fromhex(value)


def _utc_datetime(value: object) -> datetime:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _utc_text(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_ref(value: object) -> AIInputResourceVersionRef:
    if type(value) is not dict or set(value) != _SOURCE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if type(value["resource_type"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    return AIInputResourceVersionRef(
        value["resource_type"], _canonical_uuid(value["resource_id"]),
        _canonical_uuid(value["version_id"]),
    )


def _create_command(body: object, *, token: bytes, csrf: bytes, trace_id: uuid.UUID,
                    project_id: uuid.UUID) -> CreateEgressPreview:
    if type(body) is not dict or type(body.get("operation_type")) is not str:
        raise ApplicationError("REQUEST_MALFORMED")
    ai_task = body["operation_type"] == "AI_TASK"
    if set(body) != (_AI_TASK_PREVIEW_FIELDS if ai_task else _OTHER_PREVIEW_FIELDS):
        raise ApplicationError("REQUEST_MALFORMED")
    sources, categories = body["source_refs"], body["allowed_data_categories"]
    if (type(sources) is not list or not 1 <= len(sources) <= 1000
            or type(categories) is not list or not 1 <= len(categories) <= 64
            or any(type(item) is not str for item in categories)
            or len(set(categories)) != len(categories)):
        raise ApplicationError("VALIDATION_FAILED")
    scalar_strings = ("purpose_ref", "operation_type", "minimal_payload_policy_ref")
    scalar_ints = (
        "max_payload_bytes", "max_input_tokens", "max_retry_attempts",
    )
    if (any(type(body[name]) is not str for name in scalar_strings)
            or any(type(body[name]) is not int for name in scalar_ints)):
        raise ApplicationError("VALIDATION_FAILED")
    estimated_record_count = None
    payload_fingerprint = None
    task_plan = None
    if ai_task:
        task_plan = _task_plan(body["ai_task_plan"])
    else:
        if type(body["estimated_record_count"]) is not int:
            raise ApplicationError("VALIDATION_FAILED")
        estimated_record_count = body["estimated_record_count"]
        payload_fingerprint = _fingerprint(body["payload_fingerprint"])
    return CreateEgressPreview(
        token, csrf, trace_id, project_id, body["purpose_ref"], body["operation_type"],
        _canonical_uuid(body["provider_id"]), _canonical_uuid(body["model_id"]),
        tuple(_source_ref(item) for item in sources), tuple(categories),
        body["minimal_payload_policy_ref"], estimated_record_count,
        body["max_payload_bytes"], body["max_input_tokens"], body["max_retry_attempts"],
        payload_fingerprint, task_plan,
    )


def _task_plan(value: object) -> AITaskPreviewPlanRequest:
    if type(value) is not dict or set(value) != _TASK_PLAN_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    parameters = value["task_parameters"]
    if (type(parameters) is not dict or len(parameters) > 16
            or any(type(key) is not str or type(item) not in (str, int, bool)
                   for key, item in parameters.items())
            or any(type(value[name]) is not str for name in (
                "task_type", "prompt_policy_ref", "output_schema_ref",
                "context_policy_ref",
            ))):
        raise ApplicationError("VALIDATION_FAILED")
    try:
        return AITaskPreviewPlanRequest(
            value["task_type"], value["prompt_policy_ref"],
            value["output_schema_ref"], value["context_policy_ref"],
            dict(parameters),
        )
    except AIEgressTaskPlanError:
        raise ApplicationError("VALIDATION_FAILED") from None


def _authorize_command(body: object, *, token: bytes, csrf: bytes, trace_id: uuid.UUID,
                       project_id: uuid.UUID, preview_id: uuid.UUID) -> AuthorizeEgress:
    if type(body) is not dict or set(body) != _AUTHORIZE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    categories = body["allowed_data_categories"]
    integer_fields = (
        "max_record_count", "max_payload_bytes", "max_input_tokens", "max_retry_attempts",
    )
    if (type(categories) is not list or not 1 <= len(categories) <= 64
            or any(type(item) is not str for item in categories)
            or len(set(categories)) != len(categories)
            or any(type(body[name]) is not int for name in integer_fields)):
        raise ApplicationError("VALIDATION_FAILED")
    return AuthorizeEgress(
        token, csrf, trace_id, project_id, preview_id,
        _fingerprint(body["expected_preview_fingerprint"]), tuple(categories),
        body["max_record_count"], body["max_payload_bytes"], body["max_input_tokens"],
        body["max_retry_attempts"], _utc_datetime(body["valid_until"]),
    )


def _revoke_command(body: object, *, token: bytes, csrf: bytes, trace_id: uuid.UUID,
                    project_id: uuid.UUID, authorization_id: uuid.UUID,
                    expected: int) -> RevokeEgress:
    if type(body) is not dict or set(body) != _REVOKE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if any(type(body[name]) is not str for name in _REVOKE_FIELDS):
        raise ApplicationError("VALIDATION_FAILED")
    return RevokeEgress(
        token, csrf, trace_id, project_id, authorization_id, expected,
        body["reason_code"], body["reason_summary"],
    )


def _preview_public(view: EgressPreviewView) -> dict[str, object]:
    if (type(view) is not EgressPreviewView or type(view.source_refs) is not tuple
            or type(view.allowed_data_categories) is not tuple
            or type(view.risk_codes) is not tuple
            or any(type(item) is not EgressPreviewSourceView for item in view.source_refs)
            or any(type(item) is not str for item in view.allowed_data_categories + view.risk_codes)
            or any(type(item) is not uuid.UUID or not item.int for item in (
                view.preview_id, view.project_id, view.provider_id,
                view.provider_config_version_id, view.model_id,
            ))
            or any(type(item) is not bytes or len(item) != 32 for item in (
                view.payload_fingerprint, view.source_refs_fingerprint,
                view.preview_fingerprint,
            ))):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "preview_id": str(view.preview_id), "project_id": str(view.project_id),
        "purpose_ref": view.purpose_ref, "operation_type": view.operation_type,
        "provider_id": str(view.provider_id),
        "provider_config_version_id": str(view.provider_config_version_id),
        "model_id": str(view.model_id), "data_region": view.data_region,
        "allowed_data_categories": list(view.allowed_data_categories),
        "source_refs": [{
            "resource_type": item.resource_type, "resource_id": str(item.resource_id),
            "version_id": str(item.version_id),
        } for item in view.source_refs],
        "minimal_payload_policy_ref": view.minimal_payload_policy_ref,
        "estimated_record_count": view.estimated_record_count,
        "max_payload_bytes": view.max_payload_bytes,
        "max_input_tokens": view.max_input_tokens,
        "max_retry_attempts": view.max_retry_attempts,
        "payload_fingerprint": view.payload_fingerprint.hex(),
        "source_refs_fingerprint": view.source_refs_fingerprint.hex(),
        "preview_fingerprint": view.preview_fingerprint.hex(),
        "risk_codes": list(view.risk_codes), "created_at": _utc_text(view.created_at),
        "expires_at": _utc_text(view.expires_at),
    }


def _authorization_public(view: EgressAuthorizationView,
                          *, preview_fingerprint: bytes) -> dict[str, object]:
    if (type(view) is not EgressAuthorizationView
            or type(preview_fingerprint) is not bytes or len(preview_fingerprint) != 32
            or type(view.payload_fingerprint) is not bytes or len(view.payload_fingerprint) != 32
            or type(view.source_refs_fingerprint) is not bytes
            or len(view.source_refs_fingerprint) != 32
            or view.state not in {"AUTHORIZED", "REVOKED"}
            or type(view.lock_version) is not int or view.lock_version < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "authorization_id": str(view.authorization_id), "preview_id": str(view.preview_id),
        "project_id": str(view.project_id), "preview_fingerprint": preview_fingerprint.hex(),
        "purpose_ref": view.purpose_ref, "operation_type": view.operation_type,
        "provider_id": str(view.provider_id),
        "provider_config_version_id": str(view.provider_config_version_id),
        "model_id": str(view.model_id), "data_region": view.data_region,
        "allowed_data_categories": list(view.allowed_data_categories),
        "minimal_payload_policy_ref": view.minimal_payload_policy_ref,
        "max_record_count": view.max_record_count, "max_payload_bytes": view.max_payload_bytes,
        "max_input_tokens": view.max_input_tokens,
        "max_retry_attempts": view.max_retry_attempts,
        "payload_fingerprint": view.payload_fingerprint.hex(),
        "source_refs_fingerprint": view.source_refs_fingerprint.hex(),
        "approved_by": str(view.approved_by), "approved_role": view.approved_role,
        "approved_at": _utc_text(view.approved_at), "valid_until": _utc_text(view.valid_until),
        "state": view.state, "etag": f'"v{view.lock_version}"',
    }


def _preview_error(exc: EgressPreviewError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "AI_EGRESS_POLICY_DENIED": "VALIDATION_FAILED",
        "AI_EGRESS_ROUTE_UNAVAILABLE": "AI_PROVIDER_UNAVAILABLE",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def _authorization_error(exc: EgressAuthorizationError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "AI_EGRESS_APPROVAL_DENIED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


async def _write_context(request: Request, *, sessions: SessionService,
                         origins: LoginOriginPolicy) -> tuple[
                             tuple[tuple[bytes, bytes], ...], bytes, bytes, str
                         ]:
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
    return headers, token, csrf, key


def _path_uuid(value: uuid.UUID) -> None:
    if not value.int:
        raise ApplicationError("RESOURCE_NOT_FOUND")


def create_ai_egress_router(*, sessions: SessionService, previews: EgressPreviewService,
                            authorizations: EgressAuthorizationService,
                            origins: LoginOriginPolicy) -> APIRouter:
    if any(value is None for value in (sessions, previews, authorizations, origins)):
        raise ValueError("session, Egress services and origins are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/egress-previews")
    async def create_preview(project_id: uuid.UUID, request: Request) -> JSONResponse:
        _path_uuid(project_id)
        headers, token, csrf, key = await _write_context(
            request, sessions=sessions, origins=origins,
        )
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        command = _create_command(
            body, token=token, csrf=csrf, trace_id=uuid.UUID(request.state.trace_id),
            project_id=project_id,
        )
        try:
            view = await run_in_threadpool(previews.create, command, idempotency_key=key)
        except EgressPreviewError as exc:
            raise _preview_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.project_id != project_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = _preview_public(view)
        location = f"/api/v1/projects/{project_id}/egress-previews/{view.preview_id}"
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id}, status_code=201,
            headers={"Cache-Control": "no-store", "Location": location},
        )

    @router.get("/api/v1/projects/{project_id}/egress-previews/{preview_id}")
    async def get_preview(project_id: uuid.UUID, preview_id: uuid.UUID,
                          request: Request) -> JSONResponse:
        _path_uuid(project_id)
        _path_uuid(preview_id)
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted_host(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token = _session_cookie(headers)
        try:
            await run_in_threadpool(sessions.validate, token)
        except SessionError as exc:
            raise _session_failure(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        query = EgressPreviewQuery(token, uuid.UUID(request.state.trace_id), project_id)
        try:
            view = await run_in_threadpool(previews.get, query, preview_id=preview_id)
        except EgressPreviewError as exc:
            raise _preview_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.project_id != project_id or view.preview_id != preview_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _preview_public(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/api/v1/projects/{project_id}/egress-previews/{preview_id}:authorize")
    async def authorize(project_id: uuid.UUID, preview_id: uuid.UUID,
                        request: Request) -> JSONResponse:
        _path_uuid(project_id)
        _path_uuid(preview_id)
        headers, token, csrf, key = await _write_context(
            request, sessions=sessions, origins=origins,
        )
        expected = parse_if_match(headers)
        if expected != 0:
            raise ApplicationError("CONFLICT_VERSION")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        command = _authorize_command(
            body, token=token, csrf=csrf, trace_id=uuid.UUID(request.state.trace_id),
            project_id=project_id, preview_id=preview_id,
        )
        try:
            result = await run_in_threadpool(
                authorizations.authorize, command, idempotency_key=key,
            )
        except EgressAuthorizationError as exc:
            raise _authorization_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not EgressAuthorizeResult
                or result.authorization.project_id != project_id
                or result.authorization.preview_id != preview_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = _authorization_public(
            result.authorization, preview_fingerprint=command.expected_preview_fingerprint,
        )
        location = (
            f"/api/v1/projects/{project_id}/egress-authorizations/"
            f"{result.authorization.authorization_id}"
        )
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": data["etag"], "Location": location},
        )

    @router.post(
        "/api/v1/projects/{project_id}/egress-authorizations/{authorization_id}:revoke"
    )
    async def revoke(project_id: uuid.UUID, authorization_id: uuid.UUID,
                     request: Request) -> JSONResponse:
        _path_uuid(project_id)
        _path_uuid(authorization_id)
        headers, token, csrf, key = await _write_context(
            request, sessions=sessions, origins=origins,
        )
        expected = parse_if_match(headers)
        if expected != 0:
            raise ApplicationError("CONFLICT_VERSION")
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        body = await _read_json(request, headers)
        command = _revoke_command(
            body, token=token, csrf=csrf, trace_id=uuid.UUID(request.state.trace_id),
            project_id=project_id, authorization_id=authorization_id, expected=expected,
        )
        try:
            result = await run_in_threadpool(
                authorizations.revoke, command, idempotency_key=key,
            )
        except EgressAuthorizationError as exc:
            raise _authorization_error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not EgressRevokeResult
                or result.authorization_id != authorization_id
                or result.state != "REVOKED" or result.lock_version != 1):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = f'"v{result.lock_version}"'
        data = {
            "authorization_id": str(result.authorization_id),
            "revocation_id": str(result.revocation_id), "state": result.state,
            "revoked_at": _utc_text(result.revoked_at), "etag": etag,
        }
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": etag},
        )

    return router
