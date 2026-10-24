"""Opt-in HTTP boundary for the seven frozen Survey Round operations."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.application.change_round import (
    CancelSurveyRound, CloseSurveyRound, OpenSurveyRound, PatchSurveyRound,
    SurveyRoundStateError, SurveyRoundStateService,
)
from plm_assistant.modules.survey.application.create_round import (
    CreateSurveyRound, SurveyRoundCreateError, SurveyRoundCreateService,
)
from plm_assistant.modules.survey.application.read_rounds import (
    SurveyRoundReadError, SurveyRoundReadQuery, SurveyRoundReadService,
)
from plm_assistant.modules.survey.application.round_views import (
    SurveyRoundPage, SurveyRoundSourceView, SurveyRoundView,
)

from .commands import (
    _canonical_uuid, _idempotency_header, _read_json, _require_empty, _security,
)
from .read import _page, _query
from .read_cursor import SurveyRoundCursorCodec


_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_STATES = frozenset({"PLANNED", "OPEN", "CLOSED", "CANCELLED"})
_SCHEDULE_FIELDS = frozenset({
    "scheduled_start_at", "scheduled_end_at", "location_note",
})
_CREATE_FIELDS = _SCHEDULE_FIELDS | frozenset({"survey_id", "survey_version_id"})


def _optional_instant(value: object) -> datetime | None:
    if value is None:
        return None
    if type(value) is not str or not value.endswith("Z"):
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise ApplicationError("VALIDATION_FAILED") from None
    if (parsed.tzinfo is None or parsed.utcoffset() is None
            or parsed.astimezone(timezone.utc).isoformat().replace(
                "+00:00", "Z") != value):
        raise ApplicationError("VALIDATION_FAILED")
    return parsed.astimezone(timezone.utc)


def _schedule(value: object, *, fields: frozenset[str]) -> tuple[
        datetime | None, datetime | None, str | None]:
    if type(value) is not dict or set(value) != fields:
        raise ApplicationError("REQUEST_MALFORMED")
    start = _optional_instant(value["scheduled_start_at"])
    end = _optional_instant(value["scheduled_end_at"])
    location = value["location_note"]
    if ((start is None) != (end is None)
            or start is not None and end <= start
            or location is not None and type(location) is not str):
        raise ApplicationError("VALIDATION_FAILED")
    return start, end, location


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


def _source(value: SurveyRoundSourceView) -> dict[str, object]:
    if (type(value) is not SurveyRoundSourceView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.round_source_record_ref_id, value.document_id,
                value.document_version_id, value.evidence_id, value.recorded_by))
            or value.question_id is not None and (
                type(value.question_id) is not uuid.UUID or value.question_id.int == 0)
            or type(value.content_fingerprint) is not bytes
            or len(value.content_fingerprint) != 32
            or type(value.observed_evidence_lock_version) is not int
            or value.observed_evidence_lock_version < 0
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "round_source_record_ref_id": str(value.round_source_record_ref_id),
        "question_id": _uid(value.question_id),
        "document_id": str(value.document_id),
        "document_version_id": str(value.document_version_id),
        "evidence_id": str(value.evidence_id),
        "observed_evidence_lock_version": value.observed_evidence_lock_version,
        "content_fingerprint": value.content_fingerprint.hex(),
        "recorded_by": str(value.recorded_by),
        "recorded_at": _instant(value.recorded_at), "ordinal": value.ordinal,
    }


def _round(value: SurveyRoundView, *, detail: bool) -> dict[str, object]:
    if (type(value) is not SurveyRoundView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_round_id, value.survey_id,
                value.survey_version_id, value.project_id))
            or value.round_state not in _STATES
            or type(value.round_no) is not int or value.round_no <= 0
            or _ETAG.fullmatch(value.etag) is None
            or type(value.source_record_count) is not int
            or value.source_record_count < 0
            or type(value.source_records) is not tuple
            or detail and value.source_record_count != len(value.source_records)
            or value.close_report_fingerprint is not None and (
                type(value.close_report_fingerprint) is not bytes
                or len(value.close_report_fingerprint) != 32)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result = {
        "survey_round_id": str(value.survey_round_id),
        "survey_id": str(value.survey_id),
        "survey_version_id": str(value.survey_version_id),
        "project_id": str(value.project_id), "round_no": value.round_no,
        "state": value.round_state,
        "scheduled_start_at": _instant(value.scheduled_start_at),
        "scheduled_end_at": _instant(value.scheduled_end_at),
        "location_note": value.location_note,
        "opened_by": _uid(value.opened_by), "opened_at": _instant(value.opened_at),
        "closed_by": _uid(value.closed_by), "closed_at": _instant(value.closed_at),
        "close_report_fingerprint": (
            None if value.close_report_fingerprint is None
            else value.close_report_fingerprint.hex()),
        "cancelled_by": _uid(value.cancelled_by),
        "cancelled_at": _instant(value.cancelled_at),
        "cancellation_reason": value.cancellation_reason,
        "created_by": _uid(value.created_by), "created_at": _instant(value.created_at),
        "updated_by": _uid(value.updated_by), "updated_at": _instant(value.updated_at),
        "etag": value.etag, "source_record_count": value.source_record_count,
    }
    if detail:
        result["source_records"] = [_source(item) for item in value.source_records]
    return result


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "SURVEY_VERSION_NOT_APPROVED": "CONFLICT_STATE",
        "SURVEY_ROUND_STATE_CONFLICT": "CONFLICT_STATE",
        "SURVEY_ROUND_INCOMPLETE": "VALIDATION_FAILED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def create_survey_round_read_router(
    *, sessions, origins, reads: SurveyRoundReadService,
    cursors: SurveyRoundCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("Survey Round read HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/survey-rounds")
    async def list_rounds(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project, (size, cursor) = _canonical_uuid(project_id), _page(request)
        after_at, after_id = (None, None)
        if cursor is not None:
            after_at, after_id = cursors.decode(
                cursor, project_id=project, session_token=token, page_size=size)
        try:
            page = await run_in_threadpool(
                reads.list_rounds, SurveyRoundReadQuery(token, trace, project),
                page_size=size, after_created_at=after_at, after_round_id=after_id)
        except SurveyRoundReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not SurveyRoundPage or len(page.items) > size
                or any(type(item) is not SurveyRoundView
                       or item.project_id != project for item in page.items)
                or page.has_more != (page.next_created_at is not None
                                     and page.next_round_id is not None)
                or page.has_more and (not page.items
                    or page.next_created_at != page.items[-1].created_at
                    or page.next_round_id != page.items[-1].survey_round_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = cursors.encode(
            project_id=project, session_token=token, page_size=size,
            created_at=page.next_created_at, round_id=page.next_round_id,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_round(item, detail=False) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/survey-rounds/{round_id}")
    async def get_round(project_id: str, round_id: str,
                        request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, identity = _canonical_uuid(project_id), _canonical_uuid(round_id)
        try:
            value = await run_in_threadpool(
                reads.get_round, SurveyRoundReadQuery(token, trace, project), identity)
        except SurveyRoundReadError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if value.project_id != project or value.survey_round_id != identity:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _round(value, detail=True),
                             "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store", "ETag": value.etag})

    return router


def create_survey_round_command_router(
    *, sessions, origins, creates: SurveyRoundCreateService,
    states: SurveyRoundStateService,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, creates, states)):
        raise ValueError("Survey Round command HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/survey-rounds")
    async def create_round(project_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        start, end, location = _schedule(body, fields=_CREATE_FIELDS)
        command = CreateSurveyRound(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(body["survey_id"]),
            _canonical_uuid(body["survey_version_id"]), start, end, location, key)
        try:
            value = await run_in_threadpool(creates.create, command)
        except SurveyRoundCreateError as exc:
            raise _failure(exc.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        path = f"/api/v1/projects/{value.project_id}/survey-rounds/{value.survey_round_id}"
        return JSONResponse({"data": _round(value, detail=True),
                             "trace_id": request.state.trace_id}, status_code=201,
                            headers={"Cache-Control": "no-store", "ETag": value.etag,
                                     "Location": path})

    @router.patch("/api/v1/projects/{project_id}/survey-rounds/{round_id}")
    async def patch_round(project_id: str, round_id: str,
                          request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        start, end, location = _schedule(body, fields=_SCHEDULE_FIELDS)
        command = PatchSurveyRound(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(round_id), expected,
            start, end, location)
        return await _change(request, states.patch, command)

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}:open")
    async def open_round(project_id: str, round_id: str,
                         request: Request) -> JSONResponse:
        return await _empty_change(request, project_id, round_id, states.open,
                                   OpenSurveyRound, sessions, origins)

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}:close")
    async def close_round(project_id: str, round_id: str,
                          request: Request) -> JSONResponse:
        return await _empty_change(request, project_id, round_id, states.close,
                                   CloseSurveyRound, sessions, origins)

    @router.post("/api/v1/projects/{project_id}/survey-rounds/{round_id}:cancel")
    async def cancel_round(project_id: str, round_id: str,
                           request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"reason"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["reason"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = CancelSurveyRound(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(round_id), expected,
            body["reason"], key)
        return await _change(request, states.cancel, command)

    return router


async def _empty_change(request, project_id, round_id, method, command_type,
                        sessions, origins) -> JSONResponse:
    token, csrf = await _security(request, sessions, origins)
    headers = tuple(request.scope.get("headers", ()))
    expected, key = parse_if_match(headers), _idempotency_header(headers)
    await _require_empty(request)
    command = command_type(
        token, csrf, uuid.UUID(request.state.trace_id),
        _canonical_uuid(project_id), _canonical_uuid(round_id), expected, key)
    return await _change(request, method, command)


async def _change(request, method, command) -> JSONResponse:
    try:
        value = await run_in_threadpool(method, command)
    except SurveyRoundStateError as exc:
        raise _failure(exc.code) from None
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if (type(value) is not SurveyRoundView
            or value.project_id != command.project_id
            or value.survey_round_id != command.survey_round_id):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return JSONResponse({"data": _round(value, detail=True),
                         "trace_id": request.state.trace_id},
                        headers={"Cache-Control": "no-store", "ETag": value.etag})
