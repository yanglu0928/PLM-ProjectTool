"""Opt-in HTTP boundary for the six frozen RequirementPackage operations."""

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
    CreateRequirementPackage, RequirementIdentityCreateError,
    RequirementIdentityCreateService, RequirementPackageInitialView,
)
from plm_assistant.modules.requirement.application.mutate_package import (
    ChangeRequirementPackageMembers, PatchRequirementPackage,
    RequirementPackageMutationError, RequirementPackageMutationService,
    RequirementPackageView as MutatedPackageView,
)
from plm_assistant.modules.requirement.application.read_identities import (
    RequirementIdentityReadError, RequirementIdentityReadQuery,
    RequirementIdentityReadService, RequirementPackagePage,
    RequirementPackageSummary, RequirementPackageView,
)

from .package_cursor import RequirementPackageCursorCodec


_MAX_BODY = 128 * 1024
_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_STATES = frozenset({"ACTIVE", "ARCHIVED", "RESTRICTED"})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_json(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
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


def _summary(view: RequirementPackageSummary) -> dict[str, object]:
    if (type(view) is not RequirementPackageSummary
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.requirement_package_id, view.project_id, view.created_by))
            or view.updated_by is not None and (
                type(view.updated_by) is not uuid.UUID or view.updated_by.int == 0)
            or type(view.name) is not str or not view.name
            or view.package_state not in _STATES
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_package_id": str(view.requirement_package_id),
        "project_id": str(view.project_id), "name": view.name,
        "state": view.package_state, "created_by": str(view.created_by),
        "created_at": _instant(view.created_at),
        "updated_by": _uuid_or_none(view.updated_by),
        "updated_at": _instant(view.updated_at), "etag": view.etag,
    }


def _created(view: RequirementPackageInitialView) -> dict[str, object]:
    if (type(view) is not RequirementPackageInitialView
            or view.package_state not in _STATES
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_package_id": str(view.requirement_package_id),
        "project_id": str(view.project_id), "name": view.name,
        "state": view.package_state, "created_at": _instant(view.created_at),
        "etag": view.etag,
    }


def _mutated(view: MutatedPackageView) -> dict[str, object]:
    if (type(view) is not MutatedPackageView
            or view.package_state not in _STATES
            or _ETAG.fullmatch(view.etag) is None
            or type(view.member_refs) is not tuple
            or tuple(sorted(view.member_refs, key=str)) != view.member_refs
            or len(set(view.member_refs)) != len(view.member_refs)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_package_id": str(view.requirement_package_id),
        "project_id": str(view.project_id), "name": view.name,
        "state": view.package_state,
        "requirement_ids": [str(value) for value in view.member_refs],
        "etag": view.etag,
    }


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
        "REQUIREMENT_STATE_INVALID": "CONFLICT_STATE",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _requirements(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_canonical_uuid(item) for item in value)


def create_requirement_package_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: RequirementIdentityReadService,
    creates: RequirementIdentityCreateService,
    mutations: RequirementPackageMutationService,
    cursors: RequirementPackageCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, creates, mutations, cursors)):
        raise ValueError("RequirementPackage HTTP dependencies are required")
    if type(cursors) is not RequirementPackageCursorCodec:
        raise ValueError("dedicated RequirementPackage cursor codec is required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/requirement-packages")
    async def list_packages(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project = _canonical_uuid(project_id)
        size, cursor = _page_query(request)
        position = cursors.decode(
            cursor, project_id=project, session_token=token, page_size=size,
        ) if cursor is not None else (None, None)
        try:
            page = await run_in_threadpool(
                reads.list_packages,
                RequirementIdentityReadQuery(token, trace, project),
                page_size=size, after_updated_at=position[0],
                after_requirement_package_id=position[1])
        except RequirementIdentityReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not RequirementPackagePage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not RequirementPackageSummary
                       or item.project_id != project for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_updated_at is not None
                                     and page.next_requirement_package_id is not None)
                or page.has_more and (
                    not page.items or page.next_updated_at != page.items[-1].updated_at
                    or page.next_requirement_package_id
                    != page.items[-1].requirement_package_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, session_token=token, page_size=size,
            updated_at=page.next_updated_at,
            package_id=page.next_requirement_package_id,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_summary(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/projects/{project_id}/requirement-packages")
    async def create_package(project_id: str, request: Request) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"name"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["name"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            view = await run_in_threadpool(
                creates.create_package, CreateRequirementPackage(
                    token, csrf, trace, _canonical_uuid(project_id),
                    body["name"], key))
        except RequirementIdentityCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _created(view)
        location = (f"/api/v1/projects/{view.project_id}/requirement-packages/"
                    f"{view.requirement_package_id}")
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag,
                     "Location": location})

    @router.get(
        "/api/v1/projects/{project_id}/requirement-packages/{package_id}"
    )
    async def get_package(
        project_id: str, package_id: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, package = _canonical_uuid(project_id), _canonical_uuid(package_id)
        try:
            view = await run_in_threadpool(
                reads.get_package,
                RequirementIdentityReadQuery(token, trace, project), package)
        except RequirementIdentityReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not RequirementPackageView
                or view.summary.project_id != project
                or view.summary.requirement_package_id != package
                or type(view.requirement_ids) is not tuple
                or any(type(value) is not uuid.UUID or value.int == 0
                       for value in view.requirement_ids)
                or tuple(sorted(view.requirement_ids, key=lambda value: value.bytes))
                != view.requirement_ids
                or len(set(view.requirement_ids)) != len(view.requirement_ids)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = _summary(view.summary)
        data["requirement_ids"] = [str(value) for value in view.requirement_ids]
        return JSONResponse(
            {"data": data, "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.summary.etag})

    @router.patch(
        "/api/v1/projects/{project_id}/requirement-packages/{package_id}"
    )
    async def patch_package(
        project_id: str, package_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if (type(body) is not dict or not body
                or not set(body).issubset({"name", "state"})):
            raise ApplicationError("REQUEST_MALFORMED")
        if ("name" in body and type(body["name"]) is not str
                or "state" in body and type(body["state"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchRequirementPackage(
            token, csrf, trace, _canonical_uuid(project_id),
            _canonical_uuid(package_id), expected, name=body.get("name"),
            package_state=body.get("state"))
        try:
            view = await run_in_threadpool(mutations.patch, command)
        except RequirementPackageMutationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _mutated(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    async def change_members(
        project_id: str, package_id: str, request: Request, operation: str,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"requirement_ids"}:
            raise ApplicationError("REQUEST_MALFORMED")
        command = ChangeRequirementPackageMembers(
            token, csrf, trace, _canonical_uuid(project_id),
            _canonical_uuid(package_id), expected,
            _requirements(body["requirement_ids"]), key)
        method = mutations.add_members if operation == "ADD" else mutations.remove_members
        try:
            view = await run_in_threadpool(method, command)
        except RequirementPackageMutationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _mutated(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.post(
        "/api/v1/projects/{project_id}/requirement-packages/"
        "{package_id}:add-requirements"
    )
    async def add_requirements(
        project_id: str, package_id: str, request: Request,
    ) -> JSONResponse:
        return await change_members(project_id, package_id, request, "ADD")

    @router.post(
        "/api/v1/projects/{project_id}/requirement-packages/"
        "{package_id}:remove-requirements"
    )
    async def remove_requirements(
        project_id: str, package_id: str, request: Request,
    ) -> JSONResponse:
        return await change_members(project_id, package_id, request, "REMOVE")

    return router
