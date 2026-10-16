"""Opt-in HTTP boundary for the four frozen PrototypeVersion operations."""

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
from plm_assistant.modules.prototype.application.create_template import (
    PrototypeTemplateCreateError,
    PrototypeTemplateCreateService,
)
from plm_assistant.modules.prototype.application.create_version import (
    CreatePrototypeVersion,
    PrototypeVersionCreateError,
    PrototypeVersionCreateService,
    PrototypeVersionInitialView,
    VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.read_validate_version import (
    PrototypeVersionPage,
    PrototypeVersionQuery,
    PrototypeVersionReadError,
    PrototypeVersionReadValidationService,
    PrototypeVersionValidationReport,
)

from .cursors import PrototypeVersionCursorCodec
from .packages import (
    _canonical_uuid,
    _instant,
    _page_query as _shared_page_query,
    _read_json,
    _read_security,
    _uuid_or_none,
    _write_security,
)


_CREATE_FIELDS = {
    "template_id", "template_version_id", "artifact_refs",
    "requirement_refs", "interaction_spec", "coverage_summary",
}
_VERSION_STATES = frozenset({
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED",
})
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "VERSION_CONFLICT": "CONFLICT_VERSION",
        "PROTOTYPE_STATE_CONFLICT": "CONFLICT_STATE",
        "PROTOTYPE_TEMPLATE_UNAVAILABLE": "RESOURCE_NOT_FOUND",
        "PROTOTYPE_REQUIREMENT_UNAVAILABLE": "RESOURCE_NOT_FOUND",
        "PROTOTYPE_ARTIFACT_UNAVAILABLE": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _page_query(request: Request) -> tuple[int, str | None]:
    size, cursor = _shared_page_query(request)
    if size > 100:
        raise ApplicationError("VALIDATION_FAILED")
    return size, cursor


def _artifacts(value: object) -> tuple[VersionArtifactRef, ...]:
    if type(value) is not list:
        raise ApplicationError("VALIDATION_FAILED")
    result: list[VersionArtifactRef] = []
    for item in value:
        if type(item) is not dict or set(item) != {"artifact_kind", "target_id"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(item["artifact_kind"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        result.append(VersionArtifactRef(
            item["artifact_kind"], _canonical_uuid(item["target_id"]),
        ))
    return tuple(result)


def _requirements(value: object) -> tuple[VersionRequirementRef, ...]:
    if type(value) is not list:
        raise ApplicationError("VALIDATION_FAILED")
    result: list[VersionRequirementRef] = []
    for item in value:
        if (type(item) is not dict
                or set(item) != {"requirement_id", "requirement_version_id"}):
            raise ApplicationError("REQUEST_MALFORMED")
        result.append(VersionRequirementRef(
            _canonical_uuid(item["requirement_id"]),
            _canonical_uuid(item["requirement_version_id"]),
        ))
    return tuple(result)


def _body(value: object) -> tuple[
    uuid.UUID, uuid.UUID, tuple[VersionArtifactRef, ...],
    tuple[VersionRequirementRef, ...], dict[str, object], dict[str, object],
]:
    if type(value) is not dict or set(value) != _CREATE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(value["interaction_spec"]) is not dict
            or type(value["coverage_summary"]) is not dict):
        raise ApplicationError("VALIDATION_FAILED")
    return (
        _canonical_uuid(value["template_id"]),
        _canonical_uuid(value["template_version_id"]),
        _artifacts(value["artifact_refs"]),
        _requirements(value["requirement_refs"]),
        value["interaction_spec"],
        value["coverage_summary"],
    )


def _view(value: PrototypeVersionInitialView) -> dict[str, object]:
    if type(value) is not PrototypeVersionInitialView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    identities = (
        value.prototype_version_id, value.prototype_id, value.project_id,
        value.template_id, value.template_version_id,
    )
    if (any(type(item) is not uuid.UUID or item.int == 0 for item in identities)
            or type(value.version_no) is not int or value.version_no < 1
            or value.version_state not in _VERSION_STATES
            or _FINGERPRINT.fullmatch(value.content_fingerprint) is None
            or type(value.artifact_refs) is not tuple
            or not 1 <= len(value.artifact_refs) <= 100
            or any(type(item) is not VersionArtifactRef
                   for item in value.artifact_refs)
            or type(value.requirement_refs) is not tuple
            or not 1 <= len(value.requirement_refs) <= 200
            or any(type(item) is not VersionRequirementRef
                   for item in value.requirement_refs)
            or type(value.interaction_spec) is not dict
            or type(value.coverage_summary) is not dict):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    try:
        interaction = PrototypeTemplateCreateService._contract(value.interaction_spec)
        coverage = PrototypeTemplateCreateService._contract(value.coverage_summary)
    except PrototypeTemplateCreateError:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    artifacts = tuple(sorted(
        value.artifact_refs, key=lambda item: (item.artifact_kind, str(item.target_id)),
    ))
    requirements = tuple(sorted(
        value.requirement_refs, key=lambda item: str(item.requirement_version_id),
    ))
    if (artifacts != value.artifact_refs or len(set(artifacts)) != len(artifacts)
            or any(item.artifact_kind not in {"DOCUMENT_VERSION", "OUTPUT_ARTIFACT"}
                   or type(item.target_id) is not uuid.UUID or item.target_id.int == 0
                   or item.document_id is not None and (
                       item.artifact_kind != "DOCUMENT_VERSION"
                       or type(item.document_id) is not uuid.UUID
                       or item.document_id.int == 0
                   )
                   for item in artifacts)
            or requirements != value.requirement_refs
            or len({item.requirement_version_id for item in requirements})
            != len(requirements)
            or any(type(item.requirement_id) is not uuid.UUID
                   or item.requirement_id.int == 0
                   or type(item.requirement_version_id) is not uuid.UUID
                   or item.requirement_version_id.int == 0
                   for item in requirements)
            or interaction != value.interaction_spec
            or coverage != value.coverage_summary):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "prototype_version_id": str(value.prototype_version_id),
        "prototype_id": str(value.prototype_id),
        "project_id": str(value.project_id),
        "version_no": value.version_no,
        "state": value.version_state,
        "supersedes_version_id": _uuid_or_none(value.supersedes_version_id),
        "template_id": str(value.template_id),
        "template_version_id": str(value.template_version_id),
        "artifact_refs": [{
            "artifact_kind": item.artifact_kind,
            "target_id": str(item.target_id),
            **({"document_id": str(item.document_id)}
               if item.document_id is not None else {}),
        } for item in artifacts],
        "requirement_refs": [
            {"requirement_id": str(item.requirement_id),
             "requirement_version_id": str(item.requirement_version_id)}
            for item in requirements
        ],
        "interaction_spec": interaction,
        "coverage_summary": coverage,
        "content_fingerprint": value.content_fingerprint,
        "created_at": _instant(value.created_at),
    }


def _report(value: PrototypeVersionValidationReport) -> dict[str, object]:
    order = (
        "TEMPLATE_UNAVAILABLE", "REQUIREMENT_UNAVAILABLE",
        "ARTIFACT_UNAVAILABLE",
    )
    if (type(value) is not PrototypeVersionValidationReport
            or type(value.prototype_version_id) is not uuid.UUID
            or value.prototype_version_id.int == 0
            or type(value.audit_event_id) is not uuid.UUID
            or value.audit_event_id.int == 0
            or type(value.trace_id) is not uuid.UUID or value.trace_id.int == 0
            or type(value.valid) is not bool or type(value.issues) is not tuple
            or value.issues != tuple(item for item in order if item in value.issues)
            or value.valid != (not value.issues)
            or value.version_state not in _VERSION_STATES):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    issues = set(value.issues)
    return {
        "audit_event_id": str(value.audit_event_id),
        "prototype_version_id": str(value.prototype_version_id),
        "state": value.version_state,
        "valid": value.valid,
        "blocking_issues": list(value.issues),
        "warnings": [],
        "coverage_summary": {
            "template_available": "TEMPLATE_UNAVAILABLE" not in issues,
            "requirements_available": "REQUIREMENT_UNAVAILABLE" not in issues,
            "artifacts_available": "ARTIFACT_UNAVAILABLE" not in issues,
        },
        "checked_at": _instant(value.checked_at),
    }


def create_prototype_version_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: PrototypeVersionReadValidationService,
    creates: PrototypeVersionCreateService,
    cursors: PrototypeVersionCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, creates, cursors)):
        raise ValueError("PrototypeVersion HTTP dependencies are required")
    if type(cursors) is not PrototypeVersionCursorCodec:
        raise ValueError("dedicated PrototypeVersion cursor codec is required")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions"
    )
    async def list_versions(
        project_id: str, prototype_id: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        size, cursor = _page_query(request)
        before = cursors.decode(
            cursor, project_id=project, prototype_id=prototype,
            session_token=token, page_size=size,
        ) if cursor is not None else None
        query = PrototypeVersionQuery(token, trace, project, prototype)
        try:
            page = await run_in_threadpool(
                reads.list, query, page_size=size, before_version_no=before,
            )
        except PrototypeVersionReadError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not PrototypeVersionPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not PrototypeVersionInitialView
                       or item.project_id != project or item.prototype_id != prototype
                       for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_version_no is not None)
                or page.has_more and (
                    not page.items
                    or page.next_version_no != page.items[-1].version_no
                )):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, prototype_id=prototype,
            session_token=token, page_size=size,
            version_no=page.next_version_no,
        ) if page.has_more else None
        return JSONResponse({
            "data": {"items": [_view(item) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    @router.post(
        "/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions"
    )
    async def create_version(
        project_id: str, prototype_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        template, template_version, artifacts, requirements, interaction, coverage = (
            _body(await _read_json(request, headers))
        )
        command = CreatePrototypeVersion(
            token, csrf, trace, project, prototype, expected,
            template, template_version, artifacts, requirements,
            interaction, coverage, key,
        )
        try:
            view = await run_in_threadpool(creates.create, command)
        except PrototypeVersionCreateError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not PrototypeVersionInitialView
                or view.project_id != project or view.prototype_id != prototype):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = f'"v{expected + 1}"'
        data = _view(view)
        data["prototype_etag"] = etag
        location = (
            f"/api/v1/projects/{project}/prototypes/{prototype}/versions/"
            f"{view.prototype_version_id}"
        )
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag,
                     "Location": location},
        )

    @router.get(
        "/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions/"
        "{prototype_version_id}"
    )
    async def get_version(
        project_id: str, prototype_id: str,
        prototype_version_id: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        version = _canonical_uuid(prototype_version_id)
        query = PrototypeVersionQuery(token, trace, project, prototype)
        try:
            view = await run_in_threadpool(reads.get, query, version_id=version)
        except PrototypeVersionReadError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not PrototypeVersionInitialView
                or view.project_id != project or view.prototype_id != prototype
                or view.prototype_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _view(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    @router.post(
        "/api/v1/projects/{project_id}/prototypes/{prototype_id}/versions/"
        "{prototype_version_id}:validate"
    )
    async def validate_version(
        project_id: str, prototype_id: str,
        prototype_version_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins,
        )
        key = _idempotency_header(headers)
        project, prototype = _canonical_uuid(project_id), _canonical_uuid(prototype_id)
        version = _canonical_uuid(prototype_version_id)
        async for chunk in request.stream():
            if chunk:
                raise ApplicationError("REQUEST_MALFORMED")
        query = PrototypeVersionQuery(token, trace, project, prototype)
        try:
            view = await run_in_threadpool(
                reads.validate, query, version_id=version,
                csrf_token=csrf, idempotency_key=key,
            )
        except PrototypeVersionReadError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not PrototypeVersionValidationReport
                or view.prototype_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _report(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    return router
