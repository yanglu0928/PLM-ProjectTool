"""Opt-in HTTP boundary for frozen Survey Assignment/Response operations."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.application.assignment_views import (
    SurveyAnswerEvidenceView, SurveyAssignmentDetailView, SurveyAssignmentPage,
    SurveyAssignmentView, SurveyResponseReadView,
)
from plm_assistant.modules.survey.application.create_assignment import (
    CreateSurveyAssignment, SurveyAssignmentCreateError,
    SurveyAssignmentCreateService,
)
from plm_assistant.modules.survey.application.read_assignments import (
    SurveyAssignmentReadError, SurveyAssignmentReadQuery,
    SurveyAssignmentReadService,
)
from plm_assistant.modules.survey.application.record_response import (
    RecordSurveyResponse, SurveyResponseRecordError,
    SurveyResponseRecordService,
)
from plm_assistant.modules.survey.application.response_views import (
    SurveyResponseWriteView,
)
from plm_assistant.modules.survey.application.review_assignment import (
    ReviewSurveyAssignment, SurveyAssignmentReviewError,
    SurveyAssignmentReviewService,
)
from plm_assistant.modules.survey.application.submission_views import (
    SurveyAssignmentReviewReceipt, SurveyAssignmentSubmitReceipt,
)
from plm_assistant.modules.survey.application.submit_assignment import (
    SubmitSurveyAssignment, SurveyAssignmentSubmitError,
    SurveyAssignmentSubmitService,
)

from .commands import (
    _canonical_uuid, _idempotency_header, _nullable_uuid, _read_json,
    _require_empty, _security, _uuid_list,
)
from .read import _page, _query
from .read_cursor import SurveyAssignmentCursorCodec


_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_STATES = frozenset({"ASSIGNED", "IN_PROGRESS", "SUBMITTED", "VALIDATED", "RETURNED"})
_CREATE_FIELDS = frozenset({"department_id", "assignee_user_id"})
_RESPONSE_FIELDS = frozenset({
    "question_id", "response_source", "raw_answer", "answer_value",
    "evidence_ids", "project_record_evidence_id", "correction_of_response_id",
})


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SURVEY_RESPONSE_INVALID": "VALIDATION_FAILED",
        "SURVEY_ASSIGNMENT_INCOMPLETE": "VALIDATION_FAILED",
        "EVIDENCE_FINGERPRINT_MISMATCH": "VALIDATION_FAILED",
        "SURVEY_ASSIGNMENT_STATE_INVALID": "CONFLICT_STATE",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _uid(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _instant(value: datetime | None) -> str | None:
    if value is None:
        return None
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _assignment(value: SurveyAssignmentView) -> dict[str, object]:
    if (type(value) is not SurveyAssignmentView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_assignment_id, value.survey_round_id,
                value.survey_id, value.survey_version_id, value.project_id,
                value.department_id, value.created_by))
            or value.submission_state not in _STATES
            or _ETAG.fullmatch(value.etag) is None
            or type(value.response_count) is not int or value.response_count < 0
            or type(value.created_at) is not datetime
            or type(value.updated_at) is not datetime
            or value.return_comment is not None
            and type(value.return_comment) is not str):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "survey_assignment_id": str(value.survey_assignment_id),
        "survey_round_id": str(value.survey_round_id),
        "survey_id": str(value.survey_id),
        "survey_version_id": str(value.survey_version_id),
        "project_id": str(value.project_id),
        "department_id": str(value.department_id),
        "assignee_user_id": _uid(value.assignee_user_id),
        "state": value.submission_state,
        "submitted_by": _uid(value.submitted_by),
        "submitted_at": _instant(value.submitted_at),
        "validated_by": _uid(value.validated_by),
        "validated_at": _instant(value.validated_at),
        "returned_by": _uid(value.returned_by),
        "returned_at": _instant(value.returned_at),
        "return_comment": value.return_comment,
        "created_by": str(value.created_by),
        "created_at": _instant(value.created_at),
        "updated_by": _uid(value.updated_by),
        "updated_at": _instant(value.updated_at),
        "etag": value.etag, "response_count": value.response_count,
    }


def _evidence(value: SurveyAnswerEvidenceView) -> dict[str, object]:
    if (type(value) is not SurveyAnswerEvidenceView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.evidence_id, value.document_id, value.document_version_id))
            or type(value.observed_evidence_lock_version) is not int
            or value.observed_evidence_lock_version < 0
            or type(value.content_fingerprint) is not bytes
            or len(value.content_fingerprint) != 32
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"evidence_id": str(value.evidence_id),
            "document_id": str(value.document_id),
            "document_version_id": str(value.document_version_id),
            "observed_evidence_lock_version": value.observed_evidence_lock_version,
            "content_fingerprint": value.content_fingerprint.hex(),
            "ordinal": value.ordinal}


def _response(value: SurveyResponseReadView) -> dict[str, object]:
    if (type(value) is not SurveyResponseReadView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_response_id, value.question_id, value.recorded_by))
            or value.response_source not in ("SELF_SERVICE", "FACILITATED_RECORD")
            or type(value.evidence) is not tuple
            or type(value.recorded_at) is not datetime
            or value.raw_answer is not None and type(value.raw_answer) is not str):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    try:
        json.dumps(value.answer_value, ensure_ascii=False, allow_nan=False,
                   separators=(",", ":"))
    except (TypeError, ValueError, OverflowError):
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    return {"survey_response_id": str(value.survey_response_id),
            "question_id": str(value.question_id),
            "response_source": value.response_source,
            "round_source_record_ref_id": _uid(value.round_source_record_ref_id),
            "correction_of_response_id": _uid(value.correction_of_response_id),
            "recorded_by": str(value.recorded_by),
            "recorded_at": _instant(value.recorded_at),
            "raw_answer": value.raw_answer, "answer_value": value.answer_value,
            "evidence": [_evidence(item) for item in value.evidence]}


def _detail(value: SurveyAssignmentDetailView) -> dict[str, object]:
    if type(value) is not SurveyAssignmentDetailView or type(value.responses) is not tuple:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = _assignment(value.assignment)
    if value.assignment.response_count != len(value.responses):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result["responses"] = [_response(item) for item in value.responses]
    return result


def _write_response(value: SurveyResponseWriteView) -> dict[str, object]:
    if (type(value) is not SurveyResponseWriteView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_response_id, value.survey_answer_id,
                value.survey_assignment_id, value.survey_round_id,
                value.survey_version_id, value.project_id, value.question_id,
                value.recorded_by))
            or value.response_source not in ("SELF_SERVICE", "FACILITATED_RECORD")
            or value.assignment_state not in _STATES
            or _ETAG.fullmatch(value.assignment_etag) is None
            or type(value.recorded_at) is not datetime
            or type(value.evidence_count) is not int or value.evidence_count < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"survey_response_id": str(value.survey_response_id),
            "survey_answer_id": str(value.survey_answer_id),
            "survey_assignment_id": str(value.survey_assignment_id),
            "survey_round_id": str(value.survey_round_id),
            "survey_version_id": str(value.survey_version_id),
            "project_id": str(value.project_id),
            "question_id": str(value.question_id),
            "response_source": value.response_source,
            "round_source_record_ref_id": _uid(value.round_source_record_ref_id),
            "correction_of_response_id": _uid(value.correction_of_response_id),
            "recorded_by": str(value.recorded_by),
            "recorded_at": _instant(value.recorded_at),
            "assignment_state": value.assignment_state,
            "assignment_etag": value.assignment_etag,
            "evidence_count": value.evidence_count}


def _receipt(value: SurveyAssignmentSubmitReceipt | SurveyAssignmentReviewReceipt) -> dict[str, object]:
    if (type(value) not in (SurveyAssignmentSubmitReceipt, SurveyAssignmentReviewReceipt)
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_assignment_id, value.survey_round_id, value.project_id))
            or value.submission_state not in _STATES
            or _ETAG.fullmatch(value.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = {"survey_assignment_id": str(value.survey_assignment_id),
              "survey_round_id": str(value.survey_round_id),
              "project_id": str(value.project_id),
              "state": value.submission_state, "etag": value.etag}
    if type(value) is SurveyAssignmentReviewReceipt:
        result["return_comment"] = value.return_comment
    return result


def create_survey_assignment_read_router(
    *, sessions, origins, reads: SurveyAssignmentReadService,
    cursors: SurveyAssignmentCursorCodec,
) -> APIRouter:
    if any(item is None for item in (sessions, origins, reads, cursors)):
        raise ValueError("Survey Assignment read dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments")
    async def list_assignments(project_id: str, round_id: str, request: Request):
        token, trace = await _query(request, sessions, origins)
        project, round_identity = _canonical_uuid(project_id), _canonical_uuid(round_id)
        size, cursor = _page(request); after_at, after_id = None, None
        if cursor is not None:
            after_at, after_id = cursors.decode(cursor, project_id=project,
                survey_round_id=round_identity, session_token=token, page_size=size)
        query = SurveyAssignmentReadQuery(token, trace, project, round_identity)
        try:
            page = await run_in_threadpool(reads.list_assignments, query,
                page_size=size, after_created_at=after_at, after_assignment_id=after_id)
        except SurveyAssignmentReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not SurveyAssignmentPage or len(page.items) > size
                or any(type(item) is not SurveyAssignmentView
                       or item.project_id != project
                       or item.survey_round_id != round_identity
                       for item in page.items)
                or page.has_more != (page.next_created_at is not None
                                     and page.next_assignment_id is not None)
                or page.has_more and (not page.items
                    or page.next_created_at != page.items[-1].created_at
                    or page.next_assignment_id
                    != page.items[-1].survey_assignment_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(project_id=project,
            survey_round_id=round_identity, session_token=token, page_size=size,
            created_at=page.next_created_at, assignment_id=page.next_assignment_id,
        ) if page.has_more else None
        return JSONResponse({"data": {"items": [_assignment(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}")
    async def get_assignment(project_id: str, round_id: str, assignment_id: str,
                             request: Request):
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, round_identity, identity = (_canonical_uuid(project_id),
            _canonical_uuid(round_id), _canonical_uuid(assignment_id))
        try:
            value = await run_in_threadpool(reads.get_assignment_detail,
                SurveyAssignmentReadQuery(token, trace, project, round_identity), identity)
        except SurveyAssignmentReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) is not SurveyAssignmentDetailView
                or value.assignment.project_id != project
                or value.assignment.survey_round_id != round_identity
                or value.assignment.survey_assignment_id != identity):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _detail(value), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": value.assignment.etag})

    return router


def create_survey_assignment_command_router(
    *, sessions, origins, creates: SurveyAssignmentCreateService,
    responses: SurveyResponseRecordService,
    submissions: SurveyAssignmentSubmitService,
    reviews: SurveyAssignmentReviewService,
) -> APIRouter:
    if any(item is None for item in (
            sessions, origins, creates, responses, submissions, reviews)):
        raise ValueError("complete Survey Assignment write dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments")
    async def create_assignment(project_id: str, round_id: str, request: Request):
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ())); key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _CREATE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        command = CreateSurveyAssignment(token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(round_id),
            _canonical_uuid(body["department_id"]), _nullable_uuid(body["assignee_user_id"]), key)
        try:
            value = await run_in_threadpool(creates.create, command)
        except SurveyAssignmentCreateError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) is not SurveyAssignmentView
                or value.project_id != command.project_id
                or value.survey_round_id != command.survey_round_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = f"/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{value.survey_assignment_id}"
        return JSONResponse({"data": _assignment(value), "trace_id": request.state.trace_id},
            status_code=201, headers={"Cache-Control": "no-store", "ETag": value.etag, "Location": path})

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}/responses")
    async def record_response(project_id: str, round_id: str, assignment_id: str,
                              request: Request):
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _RESPONSE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if (body["raw_answer"] is not None and type(body["raw_answer"]) is not str
                or type(body["response_source"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        command = RecordSurveyResponse(token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(round_id),
            _canonical_uuid(assignment_id), _canonical_uuid(body["question_id"]),
            expected, body["response_source"], body["raw_answer"], body["answer_value"],
            _uuid_list(body["evidence_ids"]),
            _nullable_uuid(body["project_record_evidence_id"]),
            _nullable_uuid(body["correction_of_response_id"]), key)
        try:
            value = await run_in_threadpool(responses.record, command)
        except SurveyResponseRecordError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) is not SurveyResponseWriteView
                or value.project_id != command.project_id
                or value.survey_round_id != command.survey_round_id
                or value.survey_assignment_id != command.survey_assignment_id
                or value.question_id != command.question_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        location = f"/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}/responses/{value.survey_response_id}"
        return JSONResponse({"data": _write_response(value), "trace_id": request.state.trace_id},
            status_code=201, headers={"Cache-Control": "no-store",
            "ETag": value.assignment_etag, "Location": location})

    async def transition(project_id, round_id, assignment_id, request, operation):
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        project, round_identity, identity = (_canonical_uuid(project_id),
            _canonical_uuid(round_id), _canonical_uuid(assignment_id))
        trace = uuid.UUID(request.state.trace_id)
        try:
            if operation == "submit":
                await _require_empty(request)
                value = await run_in_threadpool(submissions.submit,
                    SubmitSurveyAssignment(token, csrf, trace, project, round_identity, identity, expected, key))
            else:
                if operation == "validate":
                    await _require_empty(request); comment = None
                else:
                    body = await _read_json(request, headers)
                    if type(body) is not dict or set(body) != {"comment"} or type(body["comment"]) is not str:
                        raise ApplicationError("REQUEST_MALFORMED")
                    comment = body["comment"]
                command = ReviewSurveyAssignment(token, csrf, trace, project,
                    round_identity, identity, expected, comment, key)
                method = reviews.validate if operation == "validate" else reviews.return_assignment
                value = await run_in_threadpool(method, command)
        except (SurveyAssignmentSubmitError, SurveyAssignmentReviewError) as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) not in (
                SurveyAssignmentSubmitReceipt, SurveyAssignmentReviewReceipt)
                or value.project_id != project
                or value.survey_round_id != round_identity
                or value.survey_assignment_id != identity):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _receipt(value), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": value.etag})

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}:submit")
    async def submit(project_id: str, round_id: str, assignment_id: str, request: Request):
        return await transition(project_id, round_id, assignment_id, request, "submit")

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}:validate")
    async def validate(project_id: str, round_id: str, assignment_id: str, request: Request):
        return await transition(project_id, round_id, assignment_id, request, "validate")

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}/assignments/{assignment_id}:return")
    async def return_assignment(project_id: str, round_id: str, assignment_id: str, request: Request):
        return await transition(project_id, round_id, assignment_id, request, "return")

    return router
