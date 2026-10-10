"""Opt-in Project bootstrap HTTP with strict browser and JSON boundaries."""

from __future__ import annotations

import json
import uuid
from datetime import timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.application.create_project import (
    CreateProject, CreatedProjectView, DepartmentSeed, ProjectCreateError,
    ProjectCreateService,
)


MAX_PROJECT_CREATE_BODY = 8192


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
    content_types = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(content_types) != 1 or content_types[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > MAX_PROJECT_CREATE_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(raw.decode("utf-8", errors="strict"),
                              object_pairs_hook=_unique_pairs,
                              parse_constant=_reject_constant)
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


def _command(body: object, *, token: bytes, csrf: bytes,
             trace_id: uuid.UUID) -> CreateProject:
    if (type(body) is not dict
            or not {"code", "name", "initial_manager_user_id"}.issubset(body)
            or set(body) - {"code", "name", "initial_manager_user_id", "department"}):
        raise ApplicationError("REQUEST_MALFORMED")
    if type(body["code"]) is not str or type(body["name"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    department = None
    if "department" in body:
        value = body["department"]
        if (type(value) is not dict or set(value) != {"code", "name"}
                or type(value["code"]) is not str or type(value["name"]) is not str):
            raise ApplicationError("REQUEST_MALFORMED")
        department = DepartmentSeed(value["code"], value["name"])
    return CreateProject(
        token, csrf, trace_id, body["code"], body["name"],
        _canonical_uuid(body["initial_manager_user_id"]), department,
    )


def _error(exc: ProjectCreateError) -> ApplicationError:
    code = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "PROJECT_MANAGER_INVALID": "PROJECT_ROLE_INVALID",
        "PROJECT_USER_ALREADY_ASSIGNED": "PROJECT_USER_ALREADY_ASSIGNED",
        "PROJECT_CODE_CONFLICT": "CONFLICT_DUPLICATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(code)


def create_project_create_router(*, sessions: SessionService,
                                 projects: ProjectCreateService,
                                 origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or projects is None or origins is None:
        raise ValueError("session, Project create service and origins are required")
    router = APIRouter()

    @router.post("/api/v1/projects")
    async def create_project(request: Request) -> JSONResponse:
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
        body = await _read_json(request, headers)
        command = _command(body, token=token, csrf=csrf,
                           trace_id=uuid.UUID(request.state.trace_id))
        try:
            view = await run_in_threadpool(
                projects.create_idempotent, command, idempotency_key=key,
            )
        except ProjectCreateError as exc:
            raise _error(exc) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not CreatedProjectView or view.created_at.tzinfo is None
                or view.created_at.utcoffset() is None or view.state != "ACTIVE"
                or view.etag != '"v0"'):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = f"/api/v1/projects/{view.project_id}"
        return JSONResponse({
            "data": {
                "project_id": str(view.project_id), "code": view.code,
                "name": view.name, "state": view.state,
                "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "etag": view.etag,
            },
            "trace_id": request.state.trace_id,
        }, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": view.etag, "Location": path,
        })

    return router
