"""Opt-in HTTP boundary for the four frozen RequirementVersion operations."""

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
from plm_assistant.modules.requirement.application.create_version import (
    CreateRequirementVersion, CreatedRequirementVersion,
    RequirementAcceptanceDraft, RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft, RequirementSourceDraft,
    RequirementVersionCreateError, RequirementVersionCreateService,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementAcceptanceView, RequirementAITaskView,
    RequirementAssessmentEvidenceView, RequirementCapabilityAssessmentView,
    RequirementSourceEvidenceView, RequirementSourceView,
    RequirementTextItemView, RequirementVersionPage,
    RequirementVersionReadError, RequirementVersionReadQuery,
    RequirementVersionReadService, RequirementVersionSummary,
    RequirementVersionView,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionValidationError, RequirementVersionValidationReport,
    RequirementVersionValidationService, ValidateRequirementVersion,
)

from .version_cursor import RequirementVersionCursorCodec


_MAX_BODY = 2 * 1024 * 1024
_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_HEX_32 = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_VERSION_STATES = frozenset({
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED",
})
_CREATE_FIELDS = {
    "initial", "base_version_ref", "title", "statement", "rationale",
    "domain_name", "priority", "risk", "classification", "sources",
    "acceptance_criteria", "capability_assessments", "assumptions",
    "exclusions", "dependencies", "ai_task_refs", "client_reason",
}
_SOURCE_FIELDS = {
    "source_type", "source_object_id", "source_version_ref", "evidence_refs",
}
_ACCEPTANCE_FIELDS = {
    "observable_result", "verification_method", "required_data",
    "required_environment", "evidence_requirement",
}
_ASSESSMENT_FIELDS = {
    "baseline_version_id", "capability_item_id", "match_type", "fit_gap",
    "constraints_text", "assessor_kind", "confirmation_state", "evidence_refs",
}
_ASSESSMENT_EVIDENCE_FIELDS = {"evidence_id", "evidence_role"}


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


def _canonical_uuid(value: object, *, nullable: bool = False) -> uuid.UUID | None:
    if value is None and nullable:
        return None
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _uuid(value: object) -> uuid.UUID:
    result = _canonical_uuid(value)
    if type(result) is not uuid.UUID:
        raise ApplicationError("VALIDATION_FAILED")
    return result


def _instant(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _uuid_or_none(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


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


def _list(value: object) -> list[object]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return value


def _strings(value: object) -> tuple[str, ...]:
    values = _list(value)
    if any(type(item) is not str for item in values):
        raise ApplicationError("VALIDATION_FAILED")
    return tuple(values)  # type: ignore[arg-type]


def _uuid_list(value: object) -> tuple[uuid.UUID, ...]:
    return tuple(_uuid(item) for item in _list(value))


def _sources(value: object) -> tuple[RequirementSourceDraft, ...]:
    result = []
    for item in _list(value):
        if type(item) is not dict or set(item) != _SOURCE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(item["source_type"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        result.append(RequirementSourceDraft(
            item["source_type"], _uuid(item["source_object_id"]),
            _canonical_uuid(item["source_version_ref"], nullable=True),
            _uuid_list(item["evidence_refs"])))
    return tuple(result)


def _acceptance(value: object) -> tuple[RequirementAcceptanceDraft, ...]:
    result = []
    for item in _list(value):
        if type(item) is not dict or set(item) != _ACCEPTANCE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if any(type(item[field]) is not str for field in _ACCEPTANCE_FIELDS):
            raise ApplicationError("VALIDATION_FAILED")
        result.append(RequirementAcceptanceDraft(
            item["observable_result"], item["verification_method"],
            item["required_data"], item["required_environment"],
            item["evidence_requirement"]))
    return tuple(result)


def _assessments(value: object) -> tuple[RequirementCapabilityAssessmentDraft, ...]:
    result = []
    for item in _list(value):
        if type(item) is not dict or set(item) != _ASSESSMENT_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        text_fields = {
            "match_type", "fit_gap", "constraints_text",
            "assessor_kind", "confirmation_state",
        }
        if any(type(item[field]) is not str for field in text_fields):
            raise ApplicationError("VALIDATION_FAILED")
        evidence = []
        for ref in _list(item["evidence_refs"]):
            if type(ref) is not dict or set(ref) != _ASSESSMENT_EVIDENCE_FIELDS:
                raise ApplicationError("REQUEST_MALFORMED")
            if type(ref["evidence_role"]) is not str:
                raise ApplicationError("VALIDATION_FAILED")
            evidence.append(RequirementAssessmentEvidenceDraft(
                _uuid(ref["evidence_id"]), ref["evidence_role"]))
        result.append(RequirementCapabilityAssessmentDraft(
            _uuid(item["baseline_version_id"]), _uuid(item["capability_item_id"]),
            item["match_type"], item["fit_gap"], item["constraints_text"],
            item["assessor_kind"], item["confirmation_state"], tuple(evidence)))
    return tuple(result)


def _create_command(
    body: object, *, token: bytes, csrf: bytes, trace: uuid.UUID,
    project_id: uuid.UUID, requirement_id: uuid.UUID,
    expected: int, key: str,
) -> CreateRequirementVersion:
    if type(body) is not dict or set(body) != _CREATE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    string_fields = {
        "statement", "rationale", "domain_name", "priority", "risk",
        "classification", "client_reason",
    }
    if (type(body["initial"]) is not bool
            or body["title"] is not None and type(body["title"]) is not str
            or any(type(body[field]) is not str for field in string_fields)):
        raise ApplicationError("VALIDATION_FAILED")
    return CreateRequirementVersion(
        token, csrf, trace, project_id, requirement_id, expected,
        body["initial"], _canonical_uuid(body["base_version_ref"], nullable=True),
        body["title"], body["statement"], body["rationale"], body["domain_name"],
        body["priority"], body["risk"], body["classification"],
        _sources(body["sources"]), _acceptance(body["acceptance_criteria"]),
        _assessments(body["capability_assessments"]),
        _strings(body["assumptions"]), _strings(body["exclusions"]),
        _strings(body["dependencies"]), _uuid_list(body["ai_task_refs"]),
        body["client_reason"], key)


def _summary(view: RequirementVersionSummary) -> dict[str, object]:
    identities = (
        view.requirement_version_id, view.requirement_id,
        view.project_id, view.created_by,
    ) if type(view) is RequirementVersionSummary else ()
    counts = (
        view.declared_source_count, view.declared_acceptance_count,
        view.declared_capability_count, view.declared_assumption_count,
        view.declared_exclusion_count, view.declared_dependency_count,
        view.declared_ai_task_count,
    ) if type(view) is RequirementVersionSummary else ()
    if (type(view) is not RequirementVersionSummary
            or any(type(value) is not uuid.UUID or value.int == 0 for value in identities)
            or type(view.version_no) is not int or view.version_no < 1
            or view.version_state not in _VERSION_STATES
            or view.title is not None and type(view.title) is not str
            or any(type(value) is not str or not value for value in (
                view.domain_name, view.priority, view.risk, view.classification))
            or type(view.content_fingerprint) is not str
            or _HEX_32.fullmatch(view.content_fingerprint) is None
            or any(type(value) is not int or value < 0 for value in counts)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "requirement_version_id": str(view.requirement_version_id),
        "requirement_id": str(view.requirement_id),
        "project_id": str(view.project_id), "version_no": view.version_no,
        "state": view.version_state, "title": view.title,
        "domain_name": view.domain_name, "priority": view.priority,
        "risk": view.risk, "classification": view.classification,
        "content_fingerprint": view.content_fingerprint,
        "declared_counts": {
            "sources": view.declared_source_count,
            "acceptance_criteria": view.declared_acceptance_count,
            "capability_assessments": view.declared_capability_count,
            "assumptions": view.declared_assumption_count,
            "exclusions": view.declared_exclusion_count,
            "dependencies": view.declared_dependency_count,
            "ai_tasks": view.declared_ai_task_count,
        },
        "supersedes_version_ref": _uuid_or_none(view.supersedes_version_ref),
        "review_ref": _uuid_or_none(view.review_ref),
        "review_round_ref": _uuid_or_none(view.review_round_ref),
        "created_by": str(view.created_by), "created_at": _instant(view.created_at),
    }


def _source(view: RequirementSourceView) -> dict[str, object]:
    if (type(view) is not RequirementSourceView
            or type(view.ordinal) is not int or view.ordinal < 0
            or type(view.source_type) is not str or not view.source_type
            or type(view.source_object_id) is not uuid.UUID
            or view.source_object_id.int == 0
            or type(view.evidence_refs) is not tuple
            or any(type(item) is not RequirementSourceEvidenceView
                   or type(item.evidence_id) is not uuid.UUID
                   or item.evidence_id.int == 0 or type(item.ordinal) is not int
                   or item.ordinal < 0 for item in view.evidence_refs)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "ordinal": view.ordinal, "source_type": view.source_type,
        "source_object_id": str(view.source_object_id),
        "source_version_ref": _uuid_or_none(view.source_version_ref),
        "evidence_refs": [
            {"evidence_id": str(item.evidence_id), "ordinal": item.ordinal}
            for item in view.evidence_refs
        ],
    }


def _criterion(view: RequirementAcceptanceView) -> dict[str, object]:
    if (type(view) is not RequirementAcceptanceView
            or type(view.ordinal) is not int or view.ordinal < 0
            or any(type(value) is not str or not value for value in (
                view.observable_result, view.verification_method,
                view.required_data, view.required_environment,
                view.evidence_requirement))):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "ordinal": view.ordinal, "observable_result": view.observable_result,
        "verification_method": view.verification_method,
        "required_data": view.required_data,
        "required_environment": view.required_environment,
        "evidence_requirement": view.evidence_requirement,
    }


def _assessment(view: RequirementCapabilityAssessmentView) -> dict[str, object]:
    if (type(view) is not RequirementCapabilityAssessmentView
            or type(view.ordinal) is not int or view.ordinal < 0
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.baseline_version_id, view.capability_item_id))
            or any(type(value) is not str or not value for value in (
                view.match_type, view.fit_gap, view.constraints_text,
                view.assessor_kind, view.confirmation_state))
            or type(view.evidence_refs) is not tuple
            or any(type(item) is not RequirementAssessmentEvidenceView
                   or type(item.evidence_id) is not uuid.UUID
                   or item.evidence_id.int == 0
                   or type(item.evidence_role) is not str
                   or not item.evidence_role or type(item.ordinal) is not int
                   or item.ordinal < 0 for item in view.evidence_refs)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "ordinal": view.ordinal,
        "baseline_version_id": str(view.baseline_version_id),
        "capability_item_id": str(view.capability_item_id),
        "match_type": view.match_type, "fit_gap": view.fit_gap,
        "constraints_text": view.constraints_text,
        "assessor_kind": view.assessor_kind,
        "assessed_by": _uuid_or_none(view.assessed_by),
        "assessed_at": _instant(view.assessed_at),
        "confirmation_state": view.confirmation_state,
        "evidence_refs": [
            {"evidence_id": str(item.evidence_id),
             "evidence_role": item.evidence_role, "ordinal": item.ordinal}
            for item in view.evidence_refs
        ],
    }


def _text_item(view: RequirementTextItemView) -> dict[str, object]:
    if (type(view) is not RequirementTextItemView
            or type(view.ordinal) is not int or view.ordinal < 0
            or type(view.text) is not str or not view.text):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"ordinal": view.ordinal, "text": view.text}


def _detail(view: RequirementVersionView) -> dict[str, object]:
    if type(view) is not RequirementVersionView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    if (type(view.statement) is not str or not view.statement
            or type(view.rationale) is not str or not view.rationale
            or any(type(item) is not RequirementSourceView for item in view.sources)
            or any(type(item) is not RequirementAcceptanceView
                   for item in view.acceptance_criteria)
            or any(type(item) is not RequirementCapabilityAssessmentView
                   for item in view.capability_assessments)
            or any(type(item) is not RequirementTextItemView
                   for values in (view.assumptions, view.exclusions, view.dependencies)
                   for item in values)
            or any(type(item) is not RequirementAITaskView
                   or type(item.ai_task_id) is not uuid.UUID
                   or item.ai_task_id.int == 0 or type(item.ordinal) is not int
                   or item.ordinal < 0 for item in view.ai_tasks)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = _summary(view.summary)
    result.update({
        "statement": view.statement, "rationale": view.rationale,
        "sources": [_source(item) for item in view.sources],
        "acceptance_criteria": [_criterion(item) for item in view.acceptance_criteria],
        "capability_assessments": [
            _assessment(item) for item in view.capability_assessments],
        "assumptions": [_text_item(item) for item in view.assumptions],
        "exclusions": [_text_item(item) for item in view.exclusions],
        "dependencies": [_text_item(item) for item in view.dependencies],
        "ai_tasks": [
            {"ai_task_id": str(item.ai_task_id), "ordinal": item.ordinal}
            for item in view.ai_tasks],
    })
    return result


def _created(view: CreatedRequirementVersion) -> tuple[dict[str, object], str]:
    if type(view) is not CreatedRequirementVersion:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    etag = f'"v{view.lock_version}"'
    return ({
        "requirement_version_id": str(view.requirement_version_id),
        "requirement_id": str(view.requirement_id),
        "project_id": str(view.project_id), "version_no": view.version_no,
        "state": view.version_state,
        "content_fingerprint": view.content_fingerprint.hex(),
        "supersedes_version_ref": _uuid_or_none(view.supersedes_version_ref),
        "created_by": str(view.created_by), "created_at": _instant(view.created_at),
        "requirement_etag": etag,
    }, etag)


def _report(view: RequirementVersionValidationReport) -> dict[str, object]:
    if (type(view) is not RequirementVersionValidationReport
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.audit_event_id, view.trace_id, view.requirement_id,
                view.requirement_version_id, view.project_id))
            or type(view.valid) is not bool or type(view.issue_codes) is not tuple
            or any(type(value) is not str or not value for value in view.issue_codes)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "audit_event_id": str(view.audit_event_id),
        "requirement_id": str(view.requirement_id),
        "requirement_version_id": str(view.requirement_version_id),
        "project_id": str(view.project_id), "version_no": view.version_no,
        "state": view.version_state, "classification": view.classification,
        "valid": view.valid, "blocking_issues": list(view.issue_codes),
        "warnings": [],
        "coverage_summary": {
            "sources": view.source_count,
            "acceptance_criteria": view.acceptance_count,
            "capability_assessments": view.capability_count,
            "assumptions": view.assumption_count,
            "exclusions": view.exclusion_count,
            "dependencies": view.dependency_count,
            "evidence_refs": view.evidence_ref_count,
        },
        "checked_at": _instant(view.observed_at),
    }


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "REQUIREMENT_STATE_CONFLICT": "CONFLICT_STATE",
        "REQUIREMENT_SOURCE_UNAVAILABLE": "VALIDATION_FAILED",
        "REQUIREMENT_CAPABILITY_UNAVAILABLE": "VALIDATION_FAILED",
        "REQUIREMENT_EVIDENCE_UNAVAILABLE": "VALIDATION_FAILED",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def create_requirement_version_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: RequirementVersionReadService,
    creates: RequirementVersionCreateService,
    validations: RequirementVersionValidationService,
    cursors: RequirementVersionCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, creates, validations, cursors)):
        raise ValueError("RequirementVersion HTTP dependencies are required")
    if type(cursors) is not RequirementVersionCursorCodec:
        raise ValueError("dedicated RequirementVersion cursor codec is required")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}/versions"
    )
    async def list_versions(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        project, requirement = _uuid(project_id), _uuid(requirement_id)
        size, cursor = _page_query(request)
        after = cursors.decode(
            cursor, project_id=project, requirement_id=requirement,
            session_token=token, page_size=size,
        ) if cursor is not None else None
        try:
            page = await run_in_threadpool(
                reads.list_versions,
                RequirementVersionReadQuery(token, trace, project),
                requirement_id=requirement, page_size=size,
                after_version_no=after)
        except RequirementVersionReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not RequirementVersionPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not RequirementVersionSummary
                       or item.project_id != project
                       or item.requirement_id != requirement for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_version_no is not None)
                or page.has_more and (
                    not page.items or page.next_version_no != page.items[-1].version_no)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, requirement_id=requirement,
            session_token=token, page_size=size,
            version_no=page.next_version_no,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_summary(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.post(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}/versions"
    )
    async def create_version(
        project_id: str, requirement_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        project, requirement = _uuid(project_id), _uuid(requirement_id)
        body = await _read_json(request, headers)
        command = _create_command(
            body, token=token, csrf=csrf, trace=trace,
            project_id=project, requirement_id=requirement,
            expected=expected, key=key)
        try:
            view = await run_in_threadpool(creates.create, command)
        except RequirementVersionCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not CreatedRequirementVersion
                or view.project_id != project or view.requirement_id != requirement):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data, etag = _created(view)
        location = (f"/api/v1/projects/{project}/requirements/{requirement}/versions/"
                    f"{view.requirement_version_id}")
        return JSONResponse(
            {"data": data, "trace_id": str(trace)}, status_code=201,
            headers={"Cache-Control": "no-store", "ETag": etag,
                     "Location": location})

    @router.get(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}/versions/"
        "{requirement_version_id}"
    )
    async def get_version(
        project_id: str, requirement_id: str,
        requirement_version_id: str, request: Request,
    ) -> JSONResponse:
        token, trace = await _read_security(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, requirement = _uuid(project_id), _uuid(requirement_id)
        version = _uuid(requirement_version_id)
        try:
            view = await run_in_threadpool(
                reads.get_version,
                RequirementVersionReadQuery(token, trace, project),
                requirement_id=requirement,
                requirement_version_id=version)
        except RequirementVersionReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not RequirementVersionView
                or view.summary.project_id != project
                or view.summary.requirement_id != requirement
                or view.summary.requirement_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _detail(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"})

    @router.post(
        "/api/v1/projects/{project_id}/requirements/{requirement_id}/versions/"
        "{requirement_version_id}:validate"
    )
    async def validate_version(
        project_id: str, requirement_id: str,
        requirement_version_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, trace, headers = await _write_security(
            request, sessions, origins)
        key = _idempotency_header(headers)
        project, requirement = _uuid(project_id), _uuid(requirement_id)
        version = _uuid(requirement_version_id)
        await _require_empty(request)
        try:
            view = await run_in_threadpool(
                validations.validate, ValidateRequirementVersion(
                    token, csrf, trace, project, requirement, version, key))
        except RequirementVersionValidationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        # An idempotent replay returns the immutable audit proof produced by the
        # first request. Its trace may therefore differ from this HTTP request's
        # trace; the response envelope still carries the current request trace.
        if (type(view) is not RequirementVersionValidationReport
                or view.project_id != project or view.requirement_id != requirement
                or view.requirement_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _report(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"})

    return router
