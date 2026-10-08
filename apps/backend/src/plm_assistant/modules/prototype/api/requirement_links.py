"""Opt-in HTTP boundary for frozen RequirementPrototypeLink operations."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.prototype.application.requirement_links import (
    CreateRequirementPrototypeLink,
    RequirementPrototypeCoverage,
    RequirementPrototypeLinkError,
    RequirementPrototypeLinkPage,
    RequirementPrototypeLinkQuery,
    RequirementPrototypeLinkService,
    RequirementPrototypeLinkView,
    RevokeRequirementPrototypeLink,
    SupersedeRequirementPrototypeLink,
    UncoveredAcceptanceCriterion,
)

from .cursors import RequirementPrototypeLinkCursorCodec
from .packages import (
    _canonical_uuid,
    _instant,
    _page_query,
    _read_json,
    _read_security,
    _uuid_or_none,
    _write_security,
)


_LINK_FIELDS = {
    "requirement_id", "requirement_version_id", "prototype_id",
    "prototype_version_id", "purpose", "coverage",
}
_COVERAGE_FIELDS = {
    "covered_acceptance_criterion_refs", "uncovered_acceptance_criteria",
}
_GAP_FIELDS = {"acceptance_criterion_ref", "reason"}


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "LINK_CONFLICT": "CONFLICT_STATE",
        "COVERAGE_INCOMPLETE": "VALIDATION_FAILED",
        "PROTOTYPE_INPUT_DRIFT": "VALIDATION_FAILED",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _coverage(value: object) -> RequirementPrototypeCoverage:
    if type(value) is not dict or set(value) != _COVERAGE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    covered, gaps = (
        value["covered_acceptance_criterion_refs"],
        value["uncovered_acceptance_criteria"],
    )
    if type(covered) is not list or type(gaps) is not list:
        raise ApplicationError("VALIDATION_FAILED")
    uncovered: list[UncoveredAcceptanceCriterion] = []
    for item in gaps:
        if type(item) is not dict or set(item) != _GAP_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(item["reason"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        uncovered.append(UncoveredAcceptanceCriterion(
            _canonical_uuid(item["acceptance_criterion_ref"]), item["reason"],
        ))
    return RequirementPrototypeCoverage(
        tuple(_canonical_uuid(item) for item in covered), tuple(uncovered),
    )


def _link_body(value: object) -> tuple[
    uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, str,
    RequirementPrototypeCoverage,
]:
    if type(value) is not dict or set(value) != _LINK_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if type(value["purpose"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    return (
        _canonical_uuid(value["requirement_id"]),
        _canonical_uuid(value["requirement_version_id"]),
        _canonical_uuid(value["prototype_id"]),
        _canonical_uuid(value["prototype_version_id"]),
        value["purpose"], _coverage(value["coverage"]),
    )


def _coverage_data(value: RequirementPrototypeCoverage) -> dict[str, object]:
    try:
        normalized = RequirementPrototypeLinkService._coverage(value)
    except RequirementPrototypeLinkError:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if normalized != value:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "covered_acceptance_criterion_refs": [
            str(item) for item in value.covered_acceptance_criterion_refs
        ],
        "uncovered_acceptance_criteria": [{
            "acceptance_criterion_ref": str(item.acceptance_criterion_ref),
            "reason": item.reason,
        } for item in value.uncovered_acceptance_criteria],
    }


def _view(value: RequirementPrototypeLinkView) -> tuple[dict[str, object], str]:
    if type(value) is not RequirementPrototypeLinkView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    identities = (
        value.requirement_prototype_link_id, value.project_id,
        value.requirement_id, value.requirement_version_id,
        value.prototype_id, value.prototype_version_id, value.created_by,
    )
    valid_state = (
        value.link_state == "ACTIVE" and value.lock_version == 0
        and value.superseded_by_ref is None
        or value.link_state == "REVOKED" and value.lock_version == 1
        and value.superseded_by_ref is None
        or value.link_state == "SUPERSEDED" and value.lock_version == 1
        and type(value.superseded_by_ref) is uuid.UUID
        and value.superseded_by_ref.int != 0
    )
    if (any(type(item) is not uuid.UUID or item.int == 0 for item in identities)
            or value.purpose not in {
                "ILLUSTRATES", "VALIDATES", "ACCEPTANCE_REFERENCE",
            }
            or not valid_state):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    etag = f'"v{value.lock_version}"'
    return ({
        "requirement_prototype_link_id": str(
            value.requirement_prototype_link_id),
        "project_id": str(value.project_id),
        "requirement_id": str(value.requirement_id),
        "requirement_version_id": str(value.requirement_version_id),
        "prototype_id": str(value.prototype_id),
        "prototype_version_id": str(value.prototype_version_id),
        "purpose": value.purpose,
        "coverage": _coverage_data(value.coverage),
        "state": value.link_state,
        "created_by": str(value.created_by),
        "created_at": _instant(value.created_at),
        "superseded_by_ref": _uuid_or_none(value.superseded_by_ref),
        "etag": etag,
    }, etag)


async def _require_empty(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise ApplicationError("REQUEST_MALFORMED")


def create_requirement_prototype_link_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service: RequirementPrototypeLinkService,
    cursors: RequirementPrototypeLinkCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, service, cursors)):
        raise ValueError("RequirementPrototypeLink HTTP dependencies are required")
    if type(cursors) is not RequirementPrototypeLinkCursorCodec:
        raise ValueError("dedicated RequirementPrototypeLink cursor codec required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/prototype-requirement-links")
    async def list_links(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project = _canonical_uuid(project_id)
        size, cursor = _page_query(request)
        after = cursors.decode(
            cursor, project_id=project, session_token=token, page_size=size,
        ) if cursor is not None else None
        try:
            page = await run_in_threadpool(
                service.list,
                RequirementPrototypeLinkQuery(token, trace, project),
                page_size=size, after_link_id=after,
            )
        except RequirementPrototypeLinkError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not RequirementPrototypeLinkPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not RequirementPrototypeLinkView
                       or item.project_id != project for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_link_id is not None)
                or page.has_more and (
                    not page.items
                    or page.next_link_id
                    != page.items[-1].requirement_prototype_link_id
                )):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, session_token=token, page_size=size,
            link_id=page.next_link_id,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_view(item)[0] for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/projects/{project_id}/prototype-requirement-links")
    async def create_link(project_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        key = _idempotency_header(headers)
        project = _canonical_uuid(project_id)
        requirement, requirement_version, prototype, prototype_version, purpose, coverage = (
            _link_body(await _read_json(request, headers))
        )
        command = CreateRequirementPrototypeLink(
            token, csrf, trace, project, requirement, requirement_version,
            prototype, prototype_version, purpose, coverage, key,
        )
        try:
            result = await run_in_threadpool(service.create, command)
        except RequirementPrototypeLinkError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(result) is not RequirementPrototypeLinkView or result.project_id != project:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data, etag = _view(result)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag},
        )

    @router.post(
        "/api/v1/projects/{project_id}/prototype-requirement-links/"
        "{link_id}:revoke"
    )
    async def revoke_link(
        project_id: str, link_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        key = _idempotency_header(headers)
        project, link = _canonical_uuid(project_id), _canonical_uuid(link_id)
        await _require_empty(request)
        command = RevokeRequirementPrototypeLink(
            token, csrf, trace, project, link, 0, key,
        )
        try:
            result = await run_in_threadpool(service.revoke, command)
        except RequirementPrototypeLinkError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not RequirementPrototypeLinkView
                or result.project_id != project
                or result.requirement_prototype_link_id != link):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data, etag = _view(result)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": etag},
        )

    @router.post(
        "/api/v1/projects/{project_id}/prototype-requirement-links/"
        "{link_id}:supersede"
    )
    async def supersede_link(
        project_id: str, link_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        key = _idempotency_header(headers)
        project, link = _canonical_uuid(project_id), _canonical_uuid(link_id)
        requirement, requirement_version, prototype, prototype_version, purpose, coverage = (
            _link_body(await _read_json(request, headers))
        )
        command = SupersedeRequirementPrototypeLink(
            token, csrf, trace, project, link, requirement,
            requirement_version, prototype, prototype_version, purpose,
            coverage, 0, key,
        )
        try:
            result = await run_in_threadpool(service.supersede, command)
        except RequirementPrototypeLinkError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not RequirementPrototypeLinkView
                or result.project_id != project
                or result.requirement_prototype_link_id == link):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data, etag = _view(result)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag},
        )

    return router
