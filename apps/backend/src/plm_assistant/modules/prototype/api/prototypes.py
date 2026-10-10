"""Opt-in HTTP boundary for the six frozen Prototype identity operations."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.prototype.application.create_identity import (
    CreatePrototypeIdentity, PrototypeIdentityCreateError,
    PrototypeIdentityCreateService, PrototypeInitialView,
)
from plm_assistant.modules.prototype.application.mark_not_required import (
    MarkPrototypeNotRequired, PrototypeScopeDecisionError,
    PrototypeScopeDecisionService, PrototypeScopeDecisionView,
)
from plm_assistant.modules.prototype.application.mutate_prototype import (
    ArchivePrototypeIdentity, PatchPrototypeIdentity, PrototypeIdentityView,
    PrototypeMutationError, PrototypeMutationService,
)
from plm_assistant.modules.prototype.application.read_identities import (
    PrototypeIdentityReadError, PrototypeIdentityReadQuery,
    PrototypeIdentityReadService, PrototypePage, PrototypeSummary,
)

from .cursors import PrototypeCursorCodec
from .packages import (
    _canonical_uuid, _instant, _page_query, _read_json, _read_security,
    _uuid_or_none, _write_security,
)


_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_STATES = frozenset({"ACTIVE", "NOT_REQUIRED", "ARCHIVED"})


async def _require_empty(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise ApplicationError("REQUEST_MALFORMED")


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_DUPLICATE": "CONFLICT_DUPLICATE",
        "CONFLICT_NO_CHANGE": "CONFLICT_STATE",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "PROTOTYPE_STATE_INVALID": "CONFLICT_STATE",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _summary(view: PrototypeSummary) -> dict[str, object]:
    if (type(view) is not PrototypeSummary or view.prototype_state not in _STATES
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "prototype_id": str(view.prototype_id), "project_id": str(view.project_id),
        "name": view.name, "state": view.prototype_state,
        "current_approved_version_ref": _uuid_or_none(
            view.current_approved_version_ref),
        "created_by": str(view.created_by), "created_at": _instant(view.created_at),
        "updated_by": _uuid_or_none(view.updated_by),
        "updated_at": _instant(view.updated_at), "etag": view.etag,
    }


def _created(view: PrototypeInitialView) -> dict[str, object]:
    if (type(view) is not PrototypeInitialView or view.prototype_state != "ACTIVE"
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "prototype_id": str(view.prototype_id), "project_id": str(view.project_id),
        "name": view.name, "state": view.prototype_state,
        "current_approved_version_ref": None,
        "created_at": _instant(view.created_at), "etag": view.etag,
    }


def _mutated(view: PrototypeIdentityView) -> dict[str, object]:
    if (type(view) is not PrototypeIdentityView
            or view.prototype_state not in {"ACTIVE", "ARCHIVED"}
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "prototype_id": str(view.prototype_id), "project_id": str(view.project_id),
        "name": view.name, "state": view.prototype_state,
        "current_approved_version_ref": _uuid_or_none(
            view.current_approved_version_ref), "etag": view.etag,
    }


def _decision(view: PrototypeScopeDecisionView) -> dict[str, object]:
    if (type(view) is not PrototypeScopeDecisionView
            or view.prototype_state != "NOT_REQUIRED"
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "prototype_id": str(view.prototype_id), "project_id": str(view.project_id),
        "name": view.name, "state": view.prototype_state,
        "scope_decision_id": str(view.scope_decision_id),
        "reason": view.reason, "impact": view.impact,
        "confirmed_by": str(view.confirmed_by),
        "review_id": _uuid_or_none(view.review_id),
        "review_round_id": _uuid_or_none(view.review_round_id),
        "affected_requirement_version_refs": [
            str(value) for value in view.affected_requirement_version_refs
        ],
        "decided_at": _instant(view.decided_at), "etag": view.etag,
    }


def _uuid_list(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_canonical_uuid(item) for item in value)


def _optional_uuid(value: object) -> uuid.UUID | None:
    return None if value is None else _canonical_uuid(value)


def create_prototype_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PrototypeIdentityReadService, creates: PrototypeIdentityCreateService,
    mutations: PrototypeMutationService, decisions: PrototypeScopeDecisionService,
    cursors: PrototypeCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, creates, mutations, decisions, cursors)):
        raise ValueError("Prototype HTTP dependencies are required")
    if type(cursors) is not PrototypeCursorCodec:
        raise ValueError("dedicated Prototype cursor codec is required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/prototypes")
    async def list_prototypes(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project, (size, cursor) = _canonical_uuid(project_id), _page_query(request)
        position = cursors.decode(
            cursor, project_id=project, session_token=token, page_size=size,
        ) if cursor is not None else (None, None)
        try:
            page = await run_in_threadpool(
                reads.list_prototypes, PrototypeIdentityReadQuery(token, trace, project),
                page_size=size, after_updated_at=position[0],
                after_prototype_id=position[1])
        except PrototypeIdentityReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PrototypePage or type(page.items) is not tuple
                or len(page.items) > size
                or any(type(item) is not PrototypeSummary or item.project_id != project
                       for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_updated_at is not None
                                     and page.next_prototype_id is not None)
                or page.has_more and (not page.items
                    or page.next_updated_at != page.items[-1].updated_at
                    or page.next_prototype_id != page.items[-1].prototype_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, session_token=token, page_size=size,
            updated_at=page.next_updated_at, prototype_id=page.next_prototype_id,
        ) if page.has_more else None
        return JSONResponse({"data": {"items": [_summary(v) for v in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/projects/{project_id}/prototypes")
    async def create(project_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(request, sessions, origins)
        key, body, project = _idempotency_header(headers), await _read_json(request, headers), _canonical_uuid(project_id)
        if type(body) is not dict or set(body) != {"name"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["name"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            view = await run_in_threadpool(creates.create_prototype,
                CreatePrototypeIdentity(token, csrf, trace, project, body["name"], key))
        except PrototypeIdentityCreateError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not PrototypeInitialView or view.project_id != project:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        location = f"/api/v1/projects/{project}/prototypes/{view.prototype_id}"
        return JSONResponse({"data": _created(view), "trace_id": str(trace)},
            status_code=201, headers={"Cache-Control": "no-store",
            "ETag": view.etag, "Location": location})

    @router.get("/api/v1/projects/{project_id}/prototypes/{prototype_id}")
    async def get(project_id: str, prototype_id: str, request: Request) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        if request.url.query: raise ApplicationError("REQUEST_MALFORMED")
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        try:
            view = await run_in_threadpool(reads.get_prototype,
                PrototypeIdentityReadQuery(token, trace, project), prototype)
        except PrototypeIdentityReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not PrototypeSummary or view.project_id != project or view.prototype_id != prototype:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _summary(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.patch("/api/v1/projects/{project_id}/prototypes/{prototype_id}")
    async def patch(project_id: str, prototype_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(request, sessions, origins)
        expected, body = parse_if_match(headers), await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"name"}: raise ApplicationError("REQUEST_MALFORMED")
        if type(body["name"]) is not str: raise ApplicationError("VALIDATION_FAILED")
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        try:
            view = await run_in_threadpool(mutations.patch, PatchPrototypeIdentity(
                token, csrf, trace, project, prototype, expected, body["name"]))
        except PrototypeMutationError as exc: raise _failure(exc.code) from None
        except Exception: raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return _identity_response(view, project, prototype, trace, "ACTIVE")

    @router.post("/api/v1/projects/{project_id}/prototypes/{prototype_id}:mark-not-required")
    async def mark_not_required(project_id: str, prototype_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(request, sessions, origins)
        expected, key, body = parse_if_match(headers), _idempotency_header(headers), await _read_json(request, headers)
        required = {"affected_requirement_version_refs", "reason", "impact"}
        allowed = required | {"review_id", "review_round_id"}
        if type(body) is not dict or not required.issubset(body) or not set(body).issubset(allowed):
            raise ApplicationError("REQUEST_MALFORMED")
        review_fields = set(body) & {"review_id", "review_round_id"}
        if review_fields and review_fields != {"review_id", "review_round_id"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["reason"]) is not str or type(body["impact"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        command = MarkPrototypeNotRequired(token, csrf, trace, project, prototype,
            expected, _uuid_list(body["affected_requirement_version_refs"]),
            body["reason"], body["impact"], _optional_uuid(body.get("review_id")),
            _optional_uuid(body.get("review_round_id")), key)
        try: view = await run_in_threadpool(decisions.mark_not_required, command)
        except PrototypeScopeDecisionError as exc: raise _failure(exc.code) from None
        except RuntimeLicenseError: raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception: raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not PrototypeScopeDecisionView or view.project_id != project or view.prototype_id != prototype:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _decision(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.post("/api/v1/projects/{project_id}/prototypes/{prototype_id}:archive")
    async def archive(project_id: str, prototype_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(request, sessions, origins)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        await _require_empty(request)
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        try: view = await run_in_threadpool(mutations.archive, ArchivePrototypeIdentity(
            token, csrf, trace, project, prototype, expected, key))
        except PrototypeMutationError as exc: raise _failure(exc.code) from None
        except Exception: raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return _identity_response(view, project, prototype, trace, "ARCHIVED")

    return router


def _identity_response(view: object, project: uuid.UUID, prototype: uuid.UUID,
                       trace: uuid.UUID, state: str) -> JSONResponse:
    if (type(view) is not PrototypeIdentityView or view.project_id != project
            or view.prototype_id != prototype or view.prototype_state != state):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return JSONResponse({"data": _mutated(view), "trace_id": str(trace)},
        headers={"Cache-Control": "no-store", "ETag": view.etag})
