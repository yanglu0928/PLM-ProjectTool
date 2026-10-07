"""Opt-in HTTP boundary for the four frozen RequirementRelation operations."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.requirement.application.relations import (
    CreateRequirementRelation, RELATION_TYPES, RequirementRelationError,
    RequirementRelationPage, RequirementRelationQuery,
    RequirementRelationService, RequirementRelationView,
    RequirementVersionRef, RevokeRequirementRelation,
    SupersedeRequirementRelation,
)

from .relation_cursor import RequirementRelationCursorCodec
from .versions import (
    _canonical_uuid, _instant, _read_json, _read_security,
    _require_empty, _write_security,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_RELATION_FIELDS = {"source", "target", "relation_type"}
_REF_FIELDS = {"requirement_id", "requirement_version_id"}
_STATES = frozenset({"ACTIVE", "REVOKED", "SUPERSEDED"})


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "REQUIREMENT_RELATION_CYCLE": "VALIDATION_FAILED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def _uuid(value: object) -> uuid.UUID:
    parsed = _canonical_uuid(value)
    if type(parsed) is not uuid.UUID:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _ref(value: object) -> RequirementVersionRef:
    if type(value) is not dict or set(value) != _REF_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    return RequirementVersionRef(
        _uuid(value["requirement_id"]),
        _uuid(value["requirement_version_id"]),
    )


def _body(value: object) -> tuple[RequirementVersionRef, RequirementVersionRef, str]:
    if type(value) is not dict or set(value) != _RELATION_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    relation_type = value["relation_type"]
    if type(relation_type) is not str or relation_type not in RELATION_TYPES:
        raise ApplicationError("VALIDATION_FAILED")
    return _ref(value["source"]), _ref(value["target"]), relation_type


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


def _view(value: RequirementRelationView) -> dict[str, object]:
    if (type(value) is not RequirementRelationView
            or type(value.requirement_relation_id) is not uuid.UUID
            or value.requirement_relation_id.int == 0
            or type(value.project_id) is not uuid.UUID
            or value.project_id.int == 0
            or type(value.source) is not RequirementVersionRef
            or type(value.target) is not RequirementVersionRef
            or value.relation_type not in RELATION_TYPES
            or value.relation_state not in _STATES
            or type(value.lock_version) is not int
            or value.lock_version not in (0, 1)
            or (value.relation_state == "ACTIVE") != (value.lock_version == 0)
            or type(value.created_by) is not uuid.UUID
            or value.created_by.int == 0
            or value.superseded_by_ref is not None
            and (type(value.superseded_by_ref) is not uuid.UUID
                 or value.superseded_by_ref.int == 0)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    for ref in (value.source, value.target):
        if (type(ref.requirement_id) is not uuid.UUID
                or ref.requirement_id.int == 0
                or type(ref.requirement_version_id) is not uuid.UUID
                or ref.requirement_version_id.int == 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_relation_id": str(value.requirement_relation_id),
        "project_id": str(value.project_id),
        "source": {
            "requirement_id": str(value.source.requirement_id),
            "requirement_version_id": str(value.source.requirement_version_id),
        },
        "target": {
            "requirement_id": str(value.target.requirement_id),
            "requirement_version_id": str(value.target.requirement_version_id),
        },
        "relation_type": value.relation_type,
        "relation_state": value.relation_state,
        "lock_version": value.lock_version,
        "created_by": str(value.created_by),
        "created_at": _instant(value.created_at),
        "superseded_by_ref": (
            None if value.superseded_by_ref is None
            else str(value.superseded_by_ref)),
    }


def create_requirement_relation_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    relations: RequirementRelationService,
    cursors: RequirementRelationCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, relations, cursors)):
        raise ValueError("RequirementRelation HTTP dependencies required")
    router = APIRouter()
    root = "/api/v1/projects/{project_id}/requirement-relations"

    @router.get(root)
    async def list_relations(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project, (size, cursor) = _uuid(project_id), _page_query(request)
        after = None if cursor is None else cursors.decode(
            cursor, project_id=project, session_token=token, page_size=size)
        try:
            page = await run_in_threadpool(
                relations.list, RequirementRelationQuery(token, trace, project),
                page_size=size, after_relation_id=after,
            )
        except RequirementRelationError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not RequirementRelationPage
                or type(page.items) is not tuple
                or type(page.has_more) is not bool
                or page.has_more != (page.next_relation_id is not None)
                or len(page.items) > size
                or any(item.project_id != project for item in page.items)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = None
        if page.next_relation_id is not None:
            next_cursor = cursors.encode(
                project_id=project, session_token=token, page_size=size,
                relation_id=page.next_relation_id,
            )
        return JSONResponse({"data": {
            "items": [_view(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.post(root)
    async def create_relation(project_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        project, key = _uuid(project_id), _idempotency_header(headers)
        source, target, relation_type = _body(await _read_json(request, headers))
        try:
            result = await run_in_threadpool(
                relations.create, CreateRequirementRelation(
                    token, csrf, trace, project, source, target,
                    relation_type, key),
            )
        except RequirementRelationError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return _response(result, project, trace, 201)

    @router.post(root + "/{relation_id}:revoke")
    async def revoke_relation(
        project_id: str, relation_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        project, relation = _uuid(project_id), _uuid(relation_id)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        await _require_empty(request)
        try:
            result = await run_in_threadpool(
                relations.revoke, RevokeRequirementRelation(
                    token, csrf, trace, project, relation, expected, key),
            )
        except RequirementRelationError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (result.requirement_relation_id != relation
                or result.relation_state != "REVOKED"
                or result.lock_version != 1):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return _response(result, project, trace, 200)

    @router.post(root + "/{relation_id}:supersede")
    async def supersede_relation(
        project_id: str, relation_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        project, relation = _uuid(project_id), _uuid(relation_id)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        source, target, relation_type = _body(await _read_json(request, headers))
        try:
            result = await run_in_threadpool(
                relations.supersede, SupersedeRequirementRelation(
                    token, csrf, trace, project, relation, source, target,
                    relation_type, expected, key),
            )
        except RequirementRelationError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (result.requirement_relation_id == relation
                or result.relation_state != "ACTIVE"
                or result.lock_version != 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return _response(result, project, trace, 201)

    return router


def _response(
    value: RequirementRelationView, project_id: uuid.UUID,
    trace_id: uuid.UUID, status: int,
) -> JSONResponse:
    if type(value) is not RequirementRelationView or value.project_id != project_id:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    etag = f'"v{value.lock_version}"'
    return JSONResponse(
        {"data": _view(value), "trace_id": str(trace_id)}, status_code=status,
        headers={"Cache-Control": "no-store", "ETag": etag},
    )
