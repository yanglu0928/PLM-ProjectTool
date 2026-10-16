"""Opt-in HTTP boundary for the seven frozen Requirement identity operations."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.requirement.application.create_identity import (
    CreateRequirementIdentity, RequirementIdentityCreateError,
    RequirementIdentityCreateService, RequirementInitialView,
)
from plm_assistant.modules.requirement.application.mutate_requirement import (
    ArchiveRequirementIdentity, DecideRequirementIdentity,
    PatchRequirementIdentity, RequirementIdentityView,
    RequirementMutationError, RequirementMutationService,
)
from plm_assistant.modules.requirement.application.read_identities import (
    RequirementIdentityReadError, RequirementIdentityReadQuery,
    RequirementIdentityReadService, RequirementPage, RequirementSummary,
)

from .requirement_cursor import RequirementCursorCodec


_MAX_BODY = 128 * 1024
_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_STATES = frozenset({"ACTIVE", "DEFERRED", "REJECTED", "ARCHIVED"})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_json(
    request: Request, headers: tuple[tuple[bytes, bytes], ...],
) -> object:
    values = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(values) != 1 or values[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > _MAX_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(
                raw.decode("utf-8", errors="strict"),
                object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


async def _require_empty(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise ApplicationError("REQUEST_MALFORMED")


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


def _instant(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _read_security(
    request: Request, sessions: SessionService, origins: LoginOriginPolicy,
) -> tuple[bytes, uuid.UUID]:
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
    return token, uuid.UUID(request.state.trace_id)


async def _write_security(
    request: Request, sessions: SessionService, origins: LoginOriginPolicy,
) -> tuple[bytes, bytes, uuid.UUID, tuple[tuple[bytes, bytes], ...]]:
    headers = tuple(request.scope.get("headers", ()))
    try:
        origins.require_trusted(headers)
    except LoginOriginError:
        raise ApplicationError("AUTH_CSRF_INVALID") from None
    token, csrf = _session_cookie(headers), _csrf_header(headers)
    try:
        await run_in_threadpool(
            sessions.validate, token, csrf_token=csrf, require_csrf=True)
    except SessionError as exc:
        raise _session_failure(exc) from None
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if request.url.query:
        raise ApplicationError("REQUEST_MALFORMED")
    return token, csrf, uuid.UUID(request.state.trace_id), headers


def _page_query(request: Request) -> tuple[int, str | None]:
    entries = list(request.query_params.multi_items())
    if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
            or any(key not in {"page_size", "cursor"} for key, _ in entries)):
        raise ApplicationError("REQUEST_MALFORMED")
    params = dict(entries)
    raw = params.get("page_size", "50")
    if _PAGE_SIZE.fullmatch(raw) is None or int(raw) > 200:
        raise ApplicationError("VALIDATION_FAILED")
    return int(raw), params.get("cursor")


def _uuid_or_none(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _summary(view: RequirementSummary) -> dict[str, object]:
    if (type(view) is not RequirementSummary
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.requirement_id, view.project_id, view.created_by))
            or view.updated_by is not None and (
                type(view.updated_by) is not uuid.UUID or view.updated_by.int == 0)
            or view.current_approved_version_ref is not None and (
                type(view.current_approved_version_ref) is not uuid.UUID
                or view.current_approved_version_ref.int == 0)
            or type(view.requirement_code) is not str or not view.requirement_code
            or view.requirement_state not in _STATES
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_id": str(view.requirement_id),
        "project_id": str(view.project_id),
        "requirement_code": view.requirement_code,
        "state": view.requirement_state,
        "current_approved_version_ref": _uuid_or_none(
            view.current_approved_version_ref),
        "created_by": str(view.created_by),
        "created_at": _instant(view.created_at),
        "updated_by": _uuid_or_none(view.updated_by),
        "updated_at": _instant(view.updated_at), "etag": view.etag,
    }


def _created(view: RequirementInitialView) -> dict[str, object]:
    if (type(view) is not RequirementInitialView
            or view.requirement_state != "ACTIVE"
            or view.current_approved_version_ref is not None
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_id": str(view.requirement_id),
        "project_id": str(view.project_id),
        "requirement_code": view.requirement_code,
        "state": view.requirement_state,
        "current_approved_version_ref": None,
        "created_at": _instant(view.created_at), "etag": view.etag,
    }


def _mutated(view: RequirementIdentityView) -> dict[str, object]:
    if type(view) is not RequirementIdentityView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    decision = view.requirement_state in {"DEFERRED", "REJECTED"}
    if (type(view.requirement_id) is not uuid.UUID
            or view.requirement_id.int == 0
            or type(view.project_id) is not uuid.UUID or view.project_id.int == 0
            or type(view.requirement_code) is not str or not view.requirement_code
            or view.requirement_state not in _STATES
            or _ETAG.fullmatch(view.etag) is None
            or type(view.evidence_refs) is not tuple
            or tuple(sorted(view.evidence_refs, key=str)) != view.evidence_refs
            or len(set(view.evidence_refs)) != len(view.evidence_refs)
            or any(type(value) is not uuid.UUID or value.int == 0
                   for value in view.evidence_refs)
            or decision and (
                type(view.decision_ref) is not uuid.UUID
                or view.decision_ref.int == 0 or not view.reason or not view.impact
                or not view.evidence_refs)
            or not decision and (
                view.decision_ref is not None or view.reason is not None
                or view.impact is not None or view.evidence_refs)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_id": str(view.requirement_id),
        "project_id": str(view.project_id),
        "requirement_code": view.requirement_code,
        "state": view.requirement_state,
        "decision_ref": _uuid_or_none(view.decision_ref),
        "reason": view.reason, "impact": view.impact,
        "evidence_refs": [str(value) for value in view.evidence_refs],
        "etag": view.etag,
    }


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "REQUIREMENT_DECISION_INVALID": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_DUPLICATE": "CONFLICT_DUPLICATE",
        "CONFLICT_NO_CHANGE": "CONFLICT_STATE",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "REQUIREMENT_STATE_INVALID": "CONFLICT_STATE",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _evidence(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_canonical_uuid(item) for item in value)


def create_requirement_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: RequirementIdentityReadService,
    creates: RequirementIdentityCreateService,
    mutations: RequirementMutationService,
    cursors: RequirementCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, creates, mutations, cursors)):
        raise ValueError("Requirement HTTP dependencies are required")
    if type(cursors) is not RequirementCursorCodec:
        raise ValueError("dedicated Requirement cursor codec is required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/requirements")
    async def list_requirements(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project = _canonical_uuid(project_id)
        size, cursor = _page_query(request)
        position = cursors.decode(
            cursor, project_id=project, session_token=token, page_size=size,
        ) if cursor is not None else (None, None)
        try:
            page = await run_in_threadpool(
                reads.list_requirements,
                RequirementIdentityReadQuery(token, trace, project),
                page_size=size, after_updated_at=position[0],
                after_requirement_id=position[1])
        except RequirementIdentityReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not RequirementPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not RequirementSummary
                       or item.project_id != project for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_updated_at is not None
                                     and page.next_requirement_id is not None)
                or page.has_more and (
                    not page.items or page.next_updated_at != page.items[-1].updated_at
                    or page.next_requirement_id != page.items[-1].requirement_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, session_token=token, page_size=size,
            updated_at=page.next_updated_at,
            requirement_id=page.next_requirement_id,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_summary(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/projects/{project_id}/requirements")
    async def create_requirement(project_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        key = _idempotency_header(headers)
        project = _canonical_uuid(project_id)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"requirement_code"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["requirement_code"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            view = await run_in_threadpool(
                creates.create_requirement, CreateRequirementIdentity(
                    token, csrf, trace, project,
                    body["requirement_code"], key))
        except RequirementIdentityCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not RequirementInitialView or view.project_id != project:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = _created(view)
        location = (f"/api/v1/projects/{view.project_id}/requirements/"
                    f"{view.requirement_id}")
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag,
                     "Location": location})

    @router.get("/api/v1/projects/{project_id}/requirements/{requirement_id}")
    async def get_requirement(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project = _canonical_uuid(project_id)
        requirement = _canonical_uuid(requirement_id)
        try:
            view = await run_in_threadpool(
                reads.get_requirement,
                RequirementIdentityReadQuery(token, trace, project), requirement)
        except RequirementIdentityReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not RequirementSummary
                or view.project_id != project or view.requirement_id != requirement):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _summary(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.patch("/api/v1/projects/{project_id}/requirements/{requirement_id}")
    async def patch_requirement(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        expected = parse_if_match(headers)
        project = _canonical_uuid(project_id)
        requirement = _canonical_uuid(requirement_id)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"requirement_code"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["requirement_code"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchRequirementIdentity(
            token, csrf, trace, project, requirement, expected,
            body["requirement_code"])
        try:
            view = await run_in_threadpool(mutations.patch, command)
        except RequirementMutationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not RequirementIdentityView
                or view.project_id != project or view.requirement_id != requirement
                or view.requirement_state != "ACTIVE"):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _mutated(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    async def decide(
        project_id: str, requirement_id: str, request: Request, operation: str,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        project = _canonical_uuid(project_id)
        requirement = _canonical_uuid(requirement_id)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"reason", "impact", "evidence_ids"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["reason"]) is not str or type(body["impact"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = DecideRequirementIdentity(
            token, csrf, trace, project, requirement, expected, body["reason"],
            body["impact"], _evidence(body["evidence_ids"]), key)
        method = mutations.defer if operation == "DEFER" else mutations.reject
        try:
            view = await run_in_threadpool(method, command)
        except RequirementMutationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        expected_state = "DEFERRED" if operation == "DEFER" else "REJECTED"
        if (type(view) is not RequirementIdentityView
                or view.project_id != project or view.requirement_id != requirement
                or view.requirement_state != expected_state):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _mutated(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.post(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}:defer"
    )
    async def defer_requirement(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        return await decide(project_id, requirement_id, request, "DEFER")

    @router.post(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}:reject"
    )
    async def reject_requirement(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        return await decide(project_id, requirement_id, request, "REJECT")

    @router.post(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}:archive"
    )
    async def archive_requirement(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        project = _canonical_uuid(project_id)
        requirement = _canonical_uuid(requirement_id)
        await _require_empty(request)
        command = ArchiveRequirementIdentity(
            token, csrf, trace, project, requirement, expected, key)
        try:
            view = await run_in_threadpool(mutations.archive, command)
        except RequirementMutationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not RequirementIdentityView
                or view.project_id != project or view.requirement_id != requirement
                or view.requirement_state != "ARCHIVED"):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _mutated(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    return router
