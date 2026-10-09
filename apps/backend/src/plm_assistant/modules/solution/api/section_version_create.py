"""Opt-in frozen SOL_SECTION_VERSION_CREATE HTTP boundary."""

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
from plm_assistant.modules.solution.application.create_section_version import (
    CreateSectionVersion, SectionVersionCreateError,
    SectionVersionCreateService, SectionVersionInitialView,
)
from plm_assistant.modules.solution.application.section_version_input import (
    SectionRequirementRef, SectionVersionDraftInput, SectionVersionInputError,
    validate_section_version_draft,
)


_FIELDS = frozenset({
    "title", "content_document_version_ref", "content_artifact_ref",
    "requirement_refs", "evidence_ids", "assumptions", "exclusions",
})


def _draft(body: object, project: uuid.UUID,
           section: uuid.UUID) -> SectionVersionDraftInput:
    if type(body) is not dict or set(body) != _FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(body["title"]) is not str
            or type(body["requirement_refs"]) is not list
            or type(body["evidence_ids"]) is not list
            or type(body["assumptions"]) is not list
            or type(body["exclusions"]) is not list
            or any(type(item) is not dict for item in (
                *body["assumptions"], *body["exclusions"]))):
        raise ApplicationError("VALIDATION_FAILED")
    document = body["content_document_version_ref"]
    artifact = body["content_artifact_ref"]
    if document is not None:
        document = _uuid(document)
    if artifact is not None:
        artifact = _uuid(artifact)
    requirements = []
    for item in body["requirement_refs"]:
        if (type(item) is not dict
                or set(item) != {"requirement_id", "requirement_version_id"}):
            raise ApplicationError("VALIDATION_FAILED")
        requirements.append(SectionRequirementRef(
            _uuid(item["requirement_id"]), _uuid(item["requirement_version_id"])))
    draft = SectionVersionDraftInput(
        project, section, body["title"], document, artifact,
        tuple(requirements),
        tuple(_uuid(item) for item in body["evidence_ids"]),
        tuple(body["assumptions"]), tuple(body["exclusions"]),
    )
    try:
        validate_section_version_draft(draft)
    except SectionVersionInputError:
        raise ApplicationError("VALIDATION_FAILED") from None
    return draft


def _failure(error: SectionVersionCreateError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SOURCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _response(view: SectionVersionInitialView, project: uuid.UUID,
              section: uuid.UUID) -> dict[str, object]:
    if (type(view) is not SectionVersionInitialView
            or view.project_id != project
            or view.solution_section_id != section
            or type(view.created_at) is not datetime
            or view.created_at.tzinfo is None
            or view.created_at.utcoffset() is None
            or view.version_state != "DRAFT"
            or view.content_artifact_ref is not None
            or view.review_ref is not None
            or view.review_round_ref is not None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_section_version_id": str(view.solution_section_version_id),
        "solution_section_id": str(section), "project_id": str(project),
        "version_no": view.version_no, "version_state": "DRAFT",
        "title": view.title,
        "content_document_version_ref": str(view.content_document_version_ref),
        "content_artifact_ref": None,
        "content_fingerprint": view.content_fingerprint.hex(),
        "requirement_refs": [{
            "requirement_id": str(item.requirement_id),
            "requirement_version_id": str(item.requirement_version_id),
        } for item in view.requirement_refs],
        "evidence_ids": [str(item) for item in view.evidence_ids],
        "assumptions": list(view.assumptions),
        "exclusions": list(view.exclusions),
        "declared_requirement_count": len(view.requirement_refs),
        "declared_evidence_count": len(view.evidence_ids),
        "supersedes_version_ref": (
            str(view.supersedes_version_ref)
            if view.supersedes_version_ref is not None else None),
        "review_ref": None, "review_round_ref": None,
        "created_by": str(view.created_by),
        "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace(
            "+00:00", "Z"),
    }


def create_section_version_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: SectionVersionCreateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates)):
        raise ValueError("SectionVersion HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/solution-sections/{section_id}/versions")
    async def create(project_id: str, section_id: str, request: Request) -> JSONResponse:
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
        key, project, section = (
            _idempotency_header(headers), _uuid(project_id), _uuid(section_id))
        draft = _draft(await _body(request, headers), project, section)
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(creates.create, CreateSectionVersion(
                token, csrf, trace, draft, key))
        except SectionVersionCreateError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _response(view, project, section)
        location = (
            f"/api/v1/projects/{project}/solution-sections/{section}"
            f"/versions/{view.solution_section_version_id}")
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "Location": location},
        )

    return router
