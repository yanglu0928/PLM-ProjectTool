"""Opt-in frozen SOL_SPEC_REVISE HTTP boundary; no Windows wiring here."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.outline_version_create import _body
from plm_assistant.modules.solution.api.reference_create import _uuid
from plm_assistant.modules.solution.api.structured_spec_create import (
    _draft, _response,
)
from plm_assistant.modules.solution.application.revise_structured_spec import (
    ReviseStructuredSpec, StructuredSpecReviseError,
    StructuredSpecReviseService,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView,
)


def _failure(error: StructuredSpecReviseError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "VERSION_CONFLICT": "CONFLICT_VERSION",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _revision_response(view: StructuredSpecInitialView, *, project: uuid.UUID,
                       predecessor: uuid.UUID) -> dict[str, object]:
    if (type(view) is not StructuredSpecInitialView
            or view.supersedes_version_ref != predecessor
            or type(view.version_no) is not int or view.version_no < 2):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return _response(view, project)


def create_structured_spec_revise_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    revises: StructuredSpecReviseService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, revises)):
        raise ValueError("StructuredSpec revise HTTP dependencies are required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/structured-solution-specs/{spec_id}:revise")
    async def revise(project_id: str, spec_id: str,
                     request: Request) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        key = _idempotency_header(headers)
        project, predecessor = _uuid(project_id), _uuid(spec_id)
        draft = _draft(await _body(request, headers), project)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                revises.revise, ReviseStructuredSpec(
                    token, csrf, trace, project, predecessor, draft, key))
        except StructuredSpecReviseError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _revision_response(
            view, project=project, predecessor=predecessor)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={
                "Cache-Control": "no-store",
                "Location": (
                    f"/api/v1/projects/{project}/structured-solution-specs/"
                    f"{view.structured_solution_spec_id}"),
            },
        )

    return router
