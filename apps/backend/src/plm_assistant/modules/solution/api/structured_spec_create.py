"""Opt-in frozen SOL_SPEC_CREATE HTTP boundary; no implicit Windows wiring."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.outline_version_create import _body
from plm_assistant.modules.solution.api.reference_create import _uuid
from plm_assistant.modules.solution.application.create_structured_spec import (
    CreateStructuredSpec, StructuredSpecCreateError, StructuredSpecCreateService,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    StructuredSpecInputError, validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecInitialView,
)


_FIELDS = frozenset({
    "spec_type", "payload", "requirement_refs", "section_refs",
    "evidence_ids", "artifact_ids",
})


def _draft(body: object, project: uuid.UUID) -> StructuredSpecDraftInput:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(body["spec_type"]) is not str
            or type(body["payload"]) is not dict
            or any(type(body[key]) is not list for key in (
                "requirement_refs", "section_refs", "evidence_ids",
                "artifact_ids"))):
        raise ApplicationError("VALIDATION_FAILED")
    requirements = []
    for item in body["requirement_refs"]:
        if (type(item) is not dict
                or set(item) != {"requirement_id", "requirement_version_id"}):
            raise ApplicationError("VALIDATION_FAILED")
        requirements.append(SpecRequirementRef(
            _uuid(item["requirement_id"]), _uuid(item["requirement_version_id"])))
    sections = []
    for item in body["section_refs"]:
        if (type(item) is not dict
                or set(item) != {"solution_section_id", "solution_section_version_id"}):
            raise ApplicationError("VALIDATION_FAILED")
        sections.append(SpecSectionRef(
            _uuid(item["solution_section_id"]),
            _uuid(item["solution_section_version_id"])))
    if body["artifact_ids"]:
        raise ApplicationError("VALIDATION_FAILED")
    draft = StructuredSpecDraftInput(
        project, None, None, body["spec_type"], body["payload"],
        tuple(requirements), tuple(sections),
        tuple(_uuid(item) for item in body["evidence_ids"]), ())
    try:
        validate_structured_spec_draft(draft)
    except StructuredSpecInputError:
        raise ApplicationError("VALIDATION_FAILED") from None
    return draft


def _failure(error: StructuredSpecCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: StructuredSpecInitialView, project: uuid.UUID) -> dict[str, object]:
    if (type(view) is not StructuredSpecInitialView
            or view.project_id != project
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None
            or view.created_at.utcoffset() is None
            or view.version_state != "DRAFT"
            or view.artifact_ids
            or view.review_ref is not None
            or view.review_round_ref is not None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "structured_solution_spec_id": str(view.structured_solution_spec_id),
        "spec_series_id": str(view.spec_series_id),
        "project_id": str(project), "spec_type": view.spec_type,
        "version_no": view.version_no, "version_state": "DRAFT",
        "content_fingerprint": view.content_fingerprint.hex(),
        "payload": view.payload(),
        "payload_fingerprint": view.payload_fingerprint.hex(),
        "requirement_refs": [{
            "requirement_id": str(item.requirement_id),
            "requirement_version_id": str(item.requirement_version_id),
        } for item in view.requirement_refs],
        "section_refs": [{
            "solution_section_id": str(item.solution_section_id),
            "solution_section_version_id": str(item.solution_section_version_id),
        } for item in view.section_refs],
        "evidence_ids": [str(item) for item in view.evidence_ids],
        "artifact_ids": [],
        "declared_requirement_count": len(view.requirement_refs),
        "declared_section_count": len(view.section_refs),
        "declared_evidence_count": len(view.evidence_ids),
        "supersedes_version_ref": (
            str(view.supersedes_version_ref)
            if view.supersedes_version_ref is not None else None),
        "review_ref": None, "review_round_ref": None,
        "created_by": str(view.created_by),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_structured_spec_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: StructuredSpecCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("StructuredSpec HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/structured-solution-specs")
    async def create(project_id: str, request: Request) -> JSONResponse:
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
        key, project = _idempotency_header(headers), _uuid(project_id)
        draft = _draft(await _body(request, headers), project)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(creates.create, CreateStructuredSpec(
                token, csrf, trace, draft, key))
        except StructuredSpecCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project)
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
