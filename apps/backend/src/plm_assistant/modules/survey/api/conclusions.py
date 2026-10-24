"""Opt-in HTTP boundary for the five frozen SurveyConclusion operations."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.review.application.project_persistence import (
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.survey.application.conclusion_views import (
    ConclusionEvidenceView, ConclusionOpenIssueView,
    DepartmentConclusionView, ModuleConclusionView, SurveyConclusionPage,
    SurveyConclusionSummaryView, SurveyConclusionView,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    ConclusionEvidenceInput, ConclusionOpenIssueInput,
    CreateSurveyConclusion, DepartmentConclusionInput, ModuleConclusionInput,
    SurveyConclusionCreateError, SurveyConclusionCreateService,
)
from plm_assistant.modules.survey.application.read_conclusions import (
    SurveyConclusionReadError, SurveyConclusionReadQuery,
    SurveyConclusionReadService,
)
from plm_assistant.modules.survey.application.submit_conclusion_review import (
    SubmitSurveyConclusionReview, SurveyConclusionReviewSubmissionError,
    SurveyConclusionReviewSubmissionService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionValidationError, SurveyConclusionValidationReport,
    SurveyConclusionValidationService, ValidateSurveyConclusion,
)

from .commands import (
    _canonical_uuid, _idempotency_header, _instant, _nullable_uuid,
    _read_json, _require_empty, _security, _uuid_list,
)
from .read import _page, _query
from .read_cursor import SurveyConclusionCursorCodec


_STATES = frozenset({
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED",
    "RESTRICTED",
})
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_CREATE_FIELDS = frozenset({
    "survey_id", "round_refs", "department_conclusions",
    "module_conclusions", "evidence_refs", "open_issue_refs",
    "ai_task_refs", "supersedes_ref",
})
_DEPARTMENT_FIELDS = frozenset({
    "department_id", "title", "statement", "response_refs",
})
_MODULE_FIELDS = frozenset({
    "module_key", "title", "statement", "response_refs",
})
_EVIDENCE_FIELDS = frozenset({"evidence_id", "reference_role"})
_ISSUE_FIELDS = frozenset({"action_item_id", "is_blocking"})
_REVIEW_FIELDS = frozenset({
    "reviewer_ids", "policy_ref", "due_at", "submission_note",
})


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SURVEY_CONCLUSION_SOURCE_INVALID":
            "SURVEY_CONCLUSION_SOURCE_INVALID",
        "BUSINESS_REVIEW_NOT_ELIGIBLE": "BUSINESS_REVIEW_NOT_ELIGIBLE",
        "REVIEW_REVIEWER_INELIGIBLE": "REVIEW_REVIEWER_INELIGIBLE",
        "REVIEW_SUBJECT_LOCKED": "REVIEW_SUBJECT_LOCKED",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _uuid_or_none(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _summary(value: SurveyConclusionSummaryView) -> dict[str, object]:
    if (type(value) is not SurveyConclusionSummaryView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_conclusion_id, value.conclusion_series_id,
                value.project_id, value.survey_id, value.created_by,
            ))
            or type(value.round_refs) is not tuple or not value.round_refs
            or type(value.ai_task_refs) is not tuple
            or any(type(item) is not uuid.UUID or item.int == 0
                   for item in (*value.round_refs, *value.ai_task_refs))
            or value.conclusion_state not in _STATES
            or type(value.version_no) is not int or value.version_no < 1
            or type(value.content_fingerprint) is not str
            or _FINGERPRINT.fullmatch(value.content_fingerprint) is None
            or any(type(item) is not int or item < 0 for item in (
                value.declared_department_count, value.declared_module_count,
                value.declared_evidence_count, value.declared_open_issue_count,
            ))):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "survey_conclusion_id": str(value.survey_conclusion_id),
        "conclusion_series_id": str(value.conclusion_series_id),
        "project_id": str(value.project_id), "survey_id": str(value.survey_id),
        "round_refs": [str(item) for item in value.round_refs],
        "ai_task_refs": [str(item) for item in value.ai_task_refs],
        "version_no": value.version_no, "state": value.conclusion_state,
        "content_fingerprint": value.content_fingerprint,
        "department_count": value.declared_department_count,
        "module_count": value.declared_module_count,
        "evidence_count": value.declared_evidence_count,
        "open_issue_count": value.declared_open_issue_count,
        "supersedes_ref": _uuid_or_none(value.supersedes_ref),
        "review_id": _uuid_or_none(value.review_ref),
        "review_round_id": _uuid_or_none(value.review_round_ref),
        "created_by": str(value.created_by),
        "created_at": _instant(value.created_at),
    }


def _department(value: DepartmentConclusionView) -> dict[str, object]:
    if (type(value) is not DepartmentConclusionView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.department_conclusion_id, value.department_id,
            ))
            or type(value.title) is not str or type(value.statement) is not str
            or type(value.ordinal) is not int or value.ordinal < 0
            or any(type(item) is not uuid.UUID or item.int == 0
                   for item in value.response_refs)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"department_id": str(value.department_id), "title": value.title,
            "statement": value.statement,
            "response_refs": [str(item) for item in value.response_refs],
            "ordinal": value.ordinal}


def _module(value: ModuleConclusionView) -> dict[str, object]:
    if (type(value) is not ModuleConclusionView
            or type(value.module_conclusion_id) is not uuid.UUID
            or value.module_conclusion_id.int == 0
            or type(value.module_key) is not str
            or type(value.title) is not str or type(value.statement) is not str
            or type(value.ordinal) is not int or value.ordinal < 0
            or any(type(item) is not uuid.UUID or item.int == 0
                   for item in value.response_refs)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"module_key": value.module_key, "title": value.title,
            "statement": value.statement,
            "response_refs": [str(item) for item in value.response_refs],
            "ordinal": value.ordinal}


def _evidence(value: ConclusionEvidenceView) -> dict[str, object]:
    if (type(value) is not ConclusionEvidenceView
            or value.reference_role not in ("SUPPORT", "CONFLICT")
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.conclusion_evidence_ref_id, value.document_id,
                value.document_version_id, value.evidence_id,
            ))
            or type(value.observed_evidence_lock_version) is not int
            or value.observed_evidence_lock_version < 0
            or type(value.content_fingerprint) is not str
            or _FINGERPRINT.fullmatch(value.content_fingerprint) is None
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"reference_role": value.reference_role,
            "document_id": str(value.document_id),
            "document_version_id": str(value.document_version_id),
            "evidence_id": str(value.evidence_id),
            "observed_evidence_lock_version":
                value.observed_evidence_lock_version,
            "content_fingerprint": value.content_fingerprint,
            "ordinal": value.ordinal}


def _issue(value: ConclusionOpenIssueView) -> dict[str, object]:
    if (type(value) is not ConclusionOpenIssueView
            or value.issue_owner_module != "handover"
            or value.issue_object_type != "HND-03"
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.conclusion_open_issue_ref_id, value.issue_id,
            ))
            or type(value.observed_issue_state) is not str
            or type(value.observed_lock_version) is not int
            or value.observed_lock_version < 0
            or type(value.is_blocking) is not bool
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"issue_owner_module": value.issue_owner_module,
            "issue_object_type": value.issue_object_type,
            "issue_id": str(value.issue_id),
            "observed_issue_state": value.observed_issue_state,
            "observed_lock_version": value.observed_lock_version,
            "is_blocking": value.is_blocking, "ordinal": value.ordinal}


def _detail(value: SurveyConclusionView) -> dict[str, object]:
    if type(value) is not SurveyConclusionView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    summary = _summary(value.summary)
    groups = (
        value.department_conclusions, value.module_conclusions,
        value.evidence_refs, value.open_issue_refs,
    )
    if (any(type(group) is not tuple for group in groups)
            or tuple(map(len, groups)) != (
                value.summary.declared_department_count,
                value.summary.declared_module_count,
                value.summary.declared_evidence_count,
                value.summary.declared_open_issue_count,
            )):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    summary.update({
        "department_conclusions": [
            _department(item) for item in value.department_conclusions],
        "module_conclusions": [
            _module(item) for item in value.module_conclusions],
        "evidence_refs": [_evidence(item) for item in value.evidence_refs],
        "open_issue_refs": [_issue(item) for item in value.open_issue_refs],
    })
    return summary


def _department_input(value: object) -> DepartmentConclusionInput:
    if (type(value) is not dict or set(value) != _DEPARTMENT_FIELDS
            or type(value["title"]) is not str
            or type(value["statement"]) is not str):
        raise ApplicationError("REQUEST_MALFORMED")
    return DepartmentConclusionInput(
        _canonical_uuid(value["department_id"]), value["title"],
        value["statement"], _uuid_list(value["response_refs"]),
    )


def _module_input(value: object) -> ModuleConclusionInput:
    if (type(value) is not dict or set(value) != _MODULE_FIELDS
            or type(value["module_key"]) is not str
            or type(value["title"]) is not str
            or type(value["statement"]) is not str):
        raise ApplicationError("REQUEST_MALFORMED")
    return ModuleConclusionInput(
        value["module_key"], value["title"], value["statement"],
        _uuid_list(value["response_refs"]),
    )


def _evidence_input(value: object) -> ConclusionEvidenceInput:
    if (type(value) is not dict or set(value) != _EVIDENCE_FIELDS
            or type(value["reference_role"]) is not str):
        raise ApplicationError("REQUEST_MALFORMED")
    return ConclusionEvidenceInput(
        _canonical_uuid(value["evidence_id"]), value["reference_role"],
    )


def _issue_input(value: object) -> ConclusionOpenIssueInput:
    if (type(value) is not dict or set(value) != _ISSUE_FIELDS
            or type(value["is_blocking"]) is not bool):
        raise ApplicationError("REQUEST_MALFORMED")
    return ConclusionOpenIssueInput(
        _canonical_uuid(value["action_item_id"]), value["is_blocking"],
    )


def _items(value: object, parser) -> tuple:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(parser(item) for item in value)


def _validation(value: SurveyConclusionValidationReport) -> dict[str, object]:
    if (type(value) is not SurveyConclusionValidationReport
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.audit_event_id, value.trace_id,
                value.survey_conclusion_id, value.conclusion_series_id,
                value.project_id, value.survey_id,
            ))
            or value.conclusion_state not in _STATES
            or type(value.version_no) is not int or value.version_no < 1
            or type(value.valid) is not bool
            or type(value.issue_codes) is not tuple
            or any(type(item) is not str for item in value.issue_codes)
            or any(type(item) is not int or item < 0 for item in (
                value.department_count, value.module_count,
                value.evidence_count, value.open_issue_count,
                value.response_count, value.support_evidence_count,
                value.conflict_evidence_count,
                value.current_open_blocking_issue_count,
            ))):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "audit_event_id": str(value.audit_event_id),
        "survey_conclusion_id": str(value.survey_conclusion_id),
        "conclusion_series_id": str(value.conclusion_series_id),
        "project_id": str(value.project_id), "survey_id": str(value.survey_id),
        "version_no": value.version_no, "state": value.conclusion_state,
        "valid": value.valid,
        "blocking_issues": list(value.issue_codes), "warnings": [],
        "coverage_summary": {
            "department_count": value.department_count,
            "module_count": value.module_count,
            "evidence_count": value.evidence_count,
            "open_issue_count": value.open_issue_count,
            "response_count": value.response_count,
            "support_evidence_count": value.support_evidence_count,
            "conflict_evidence_count": value.conflict_evidence_count,
            "current_open_blocking_issue_count":
                value.current_open_blocking_issue_count,
        },
        "checked_at": _instant(value.observed_at),
    }


def create_survey_conclusion_read_router(
    *, sessions, origins, reads: SurveyConclusionReadService,
    cursors: SurveyConclusionCursorCodec,
) -> APIRouter:
    if any(item is None for item in (sessions, origins, reads, cursors)):
        raise ValueError("SurveyConclusion read dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/survey-conclusions")
    async def list_conclusions(project_id: str, request: Request):
        token, trace = await _query(request, sessions, origins)
        project = _canonical_uuid(project_id)
        size, cursor = _page(request)
        after_at, after_id = None, None
        if cursor is not None:
            after_at, after_id = cursors.decode(
                cursor, project_id=project, session_token=token,
                page_size=size,
            )
        query = SurveyConclusionReadQuery(token, trace, project)
        try:
            page = await run_in_threadpool(
                reads.list_conclusions, query, page_size=size,
                after_created_at=after_at, after_conclusion_id=after_id,
            )
        except SurveyConclusionReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not SurveyConclusionPage or len(page.items) > size
                or any(type(item) is not SurveyConclusionSummaryView
                       or item.project_id != project for item in page.items)
                or page.has_more != (page.next_created_at is not None
                                     and page.next_conclusion_id is not None)
                or page.has_more and (not page.items
                    or page.next_created_at != page.items[-1].created_at
                    or page.next_conclusion_id
                    != page.items[-1].survey_conclusion_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, session_token=token, page_size=size,
            created_at=page.next_created_at,
            conclusion_id=page.next_conclusion_id,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_summary(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get(
        "/api/v1/projects/{project_id}/survey-conclusions/{conclusion_id}"
    )
    async def get_conclusion(project_id: str, conclusion_id: str,
                             request: Request):
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, identity = (
            _canonical_uuid(project_id), _canonical_uuid(conclusion_id))
        try:
            value = await run_in_threadpool(
                reads.get_conclusion,
                SurveyConclusionReadQuery(token, trace, project), identity,
            )
        except SurveyConclusionReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) is not SurveyConclusionView
                or value.summary.project_id != project
                or value.summary.survey_conclusion_id != identity):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _detail(value), "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store"})

    return router


def create_survey_conclusion_command_router(
    *, sessions, origins, creates: SurveyConclusionCreateService,
    validations: SurveyConclusionValidationService,
    submissions: SurveyConclusionReviewSubmissionService,
    reads: SurveyConclusionReadService,
) -> APIRouter:
    if any(item is None for item in (
            sessions, origins, creates, validations, submissions, reads)):
        raise ValueError("complete SurveyConclusion write dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/survey-conclusions")
    async def create_conclusion(project_id: str, request: Request):
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _CREATE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        command = CreateSurveyConclusion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(body["survey_id"]),
            _uuid_list(body["round_refs"]),
            _items(body["department_conclusions"], _department_input),
            _items(body["module_conclusions"], _module_input),
            _items(body["evidence_refs"], _evidence_input),
            _items(body["open_issue_refs"], _issue_input),
            _uuid_list(body["ai_task_refs"]),
            _nullable_uuid(body["supersedes_ref"]), key,
        )
        try:
            value = await run_in_threadpool(creates.create, command)
        except SurveyConclusionCreateError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) is not SurveyConclusionView
                or value.summary.project_id != command.project_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        identity = value.summary.survey_conclusion_id
        location = (f"/api/v1/projects/{project_id}/survey-conclusions/"
                    f"{identity}")
        return JSONResponse({"data": _detail(value),
                             "trace_id": request.state.trace_id},
                            status_code=201, headers={
                                "Cache-Control": "no-store",
                                "Location": location,
                            })

    @router.post(
        "/api/v1/projects/{project_id}/survey-conclusions/"
        "{conclusion_id}:validate"
    )
    async def validate_conclusion(project_id: str, conclusion_id: str,
                                  request: Request):
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        await _require_empty(request)
        command = ValidateSurveyConclusion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(conclusion_id), key,
        )
        try:
            value = await run_in_threadpool(validations.validate, command)
        except SurveyConclusionValidationError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({"data": _validation(value),
                             "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store"})

    @router.post(
        "/api/v1/projects/{project_id}/survey-conclusions/"
        "{conclusion_id}:submit-review"
    )
    async def submit_review(project_id: str, conclusion_id: str,
                            request: Request):
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _REVIEW_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        reviewers = body["reviewer_ids"]
        if (type(reviewers) is not list
                or body["policy_ref"] != "SURVEY_CONCLUSION_ALL_V1"
                or body["due_at"] is not None
                or body["submission_note"] is not None):
            raise ApplicationError("VALIDATION_FAILED")
        project, identity = (
            _canonical_uuid(project_id), _canonical_uuid(conclusion_id))
        trace = uuid.UUID(request.state.trace_id)
        try:
            current = await run_in_threadpool(
                reads.get_conclusion,
                SurveyConclusionReadQuery(token, trace, project), identity,
            )
            if (type(current) is not SurveyConclusionView
                    or current.summary.project_id != project
                    or current.summary.survey_conclusion_id != identity):
                raise SurveyConclusionReadError()
            result = await run_in_threadpool(
                submissions.submit, SubmitSurveyConclusionReview(
                    token, csrf, trace, project,
                    current.summary.conclusion_series_id, identity,
                    tuple(_canonical_uuid(value) for value in reviewers),
                    body["policy_ref"], key,
                ),
            )
        except SurveyConclusionReadError as exc:
            raise _failure(exc.code) from None
        except SurveyConclusionReviewSubmissionError as exc:
            raise _failure(exc.code) from None
        except ApplicationError:
            raise
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not SubmittedProjectReviewRef
                or result.project_id != project
                or result.subject_type != "SRV-05"
                or result.subject_id != current.summary.conclusion_series_id
                or result.subject_version_id != identity):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        etag = f'"v{result.review_after_version}"'
        return JSONResponse({"data": {
            "review_id": str(result.review_id),
            "review_round_id": str(result.round_id),
            "subject_type": result.subject_type,
            "project_id": str(result.project_id),
            "conclusion_series_id": str(result.subject_id),
            "survey_conclusion_id": str(result.subject_version_id),
            "policy_ref": result.policy_code,
            "reviewer_ids": [str(value) for value in result.reviewer_ids],
            "state": "IN_REVIEW", "round_no": result.round_no,
            "review_etag": etag, "submitted_by": str(result.submitted_by),
            "submitted_at": _instant(result.submitted_at),
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": etag,
        })

    return router
