"""Opt-in HTTP boundary for four Survey definition read operations."""

from __future__ import annotations

import json
import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.application.read_surveys import (
    SurveyOptionView, SurveyPage, SurveyQuestionView, SurveyReadError,
    SurveyReadQuery, SurveyReadService, SurveySourceView,
    SurveyTargetDepartmentView, SurveyVersionPage, SurveyVersionView, SurveyView,
)

from .commands import _canonical_uuid, _instant
from .read_cursor import SurveyCursorCodec, SurveyVersionCursorCodec


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_SURVEY_STATES = frozenset({"ACTIVE", "ARCHIVED", "RESTRICTED"})
_VERSION_STATES = frozenset({
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED",
})
_ANSWERS = frozenset({
    "TEXT", "SINGLE_CHOICE", "MULTIPLE_CHOICE", "DATE", "NUMBER", "ATTACHMENT",
})
_SOURCES = frozenset({
    "HANDOVER_ITEM", "CAPABILITY_ITEM", "TEMPLATE_DOCUMENT_VERSION", "MANUAL",
})


def _error(exc: SurveyReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


async def _query(request: Request, sessions: SessionService,
                 origins: LoginOriginPolicy) -> tuple[bytes, uuid.UUID]:
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


def _page(request: Request) -> tuple[int, str | None]:
    entries = list(request.query_params.multi_items())
    if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
            or any(key not in {"page_size", "cursor"} for key, _ in entries)):
        raise ApplicationError("REQUEST_MALFORMED")
    params = dict(entries)
    raw = params.get("page_size", "50")
    if _PAGE_SIZE.fullmatch(raw) is None or int(raw) > 200:
        raise ApplicationError("VALIDATION_FAILED")
    return int(raw), params.get("cursor")


def _uid(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _object(value: dict[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        if type(value) is not dict:
            raise ValueError()
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False,
                         sort_keys=True, separators=(",", ":"))
        if len(raw.encode("utf-8")) > 65536:
            raise ValueError()
        result = json.loads(raw)
        if type(result) is not dict:
            raise ValueError()
        return result
    except (TypeError, ValueError, OverflowError, json.JSONDecodeError):
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def _survey(value: SurveyView) -> dict[str, object]:
    if (type(value) is not SurveyView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_id, value.project_id, value.created_by))
            or value.updated_by is not None and (
                type(value.updated_by) is not uuid.UUID or value.updated_by.int == 0)
            or type(value.name) is not str or not value.name
            or value.survey_state not in _SURVEY_STATES
            or _ETAG.fullmatch(value.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"survey_id": str(value.survey_id), "project_id": str(value.project_id),
            "name": value.name, "state": value.survey_state,
            "current_approved_version_ref": _uid(value.current_approved_version_ref),
            "created_by": str(value.created_by), "created_at": _instant(value.created_at),
            "updated_by": _uid(value.updated_by), "updated_at": _instant(value.updated_at),
            "etag": value.etag}


def _option(value: SurveyOptionView) -> dict[str, object]:
    if (type(value) is not SurveyOptionView or not value.option_code or not value.label
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"option_code": value.option_code, "label": value.label,
            "description": value.description, "ordinal": value.ordinal}


def _source(value: SurveySourceView) -> dict[str, object]:
    if (type(value) is not SurveySourceView or value.source_kind not in _SOURCES
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"source_kind": value.source_kind,
            "handover_item_row_id": _uid(value.handover_item_row_id),
            "handover_analysis_version_id": _uid(value.handover_analysis_version_id),
            "handover_analysis_id": _uid(value.handover_analysis_id),
            "capability_item_row_id": _uid(value.capability_item_row_id),
            "capability_baseline_version_id": _uid(value.capability_baseline_version_id),
            "capability_baseline_id": _uid(value.capability_baseline_id),
            "template_document_version_id": _uid(value.template_document_version_id),
            "template_document_id": _uid(value.template_document_id),
            "manual_source_note": value.manual_source_note, "ordinal": value.ordinal}


def _question(value: SurveyQuestionView) -> dict[str, object]:
    if (type(value) is not SurveyQuestionView
            or type(value.question_id) is not uuid.UUID or value.question_id.int == 0
            or type(value.sequence_no) is not int or value.sequence_no <= 0
            or value.answer_type not in _ANSWERS
            or any(type(item) is not str or not item for item in (
                value.topic, value.question_text, value.objective, value.expected_output))
            or type(value.required) is not bool or type(value.evidence_required) is not bool
            or type(value.options) is not tuple or type(value.sources) is not tuple):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"question_id": str(value.question_id), "sequence_no": value.sequence_no,
            "topic": value.topic, "question_text": value.question_text,
            "objective": value.objective, "answer_type": value.answer_type,
            "validation_rule": _object(value.validation_rule), "required": value.required,
            "condition_rule": _object(value.condition_rule),
            "expected_output": value.expected_output,
            "evidence_required": value.evidence_required,
            "options": [_option(item) for item in value.options],
            "sources": [_source(item) for item in value.sources]}


def _version(value: SurveyVersionView) -> dict[str, object]:
    if (type(value) is not SurveyVersionView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.survey_version_id, value.survey_id, value.project_id, value.created_by))
            or type(value.version_no) is not int or value.version_no <= 0
            or value.version_state not in _VERSION_STATES
            or _HASH.fullmatch(value.content_fingerprint) is None
            or type(value.questions) is not tuple
            or type(value.target_departments) is not tuple):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    targets = []
    for item in value.target_departments:
        if (type(item) is not SurveyTargetDepartmentView
                or type(item.department_id) is not uuid.UUID or item.department_id.int == 0
                or type(item.ordinal) is not int or item.ordinal < 0):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        targets.append({"department_id": str(item.department_id), "ordinal": item.ordinal})
    return {"survey_version_id": str(value.survey_version_id),
            "survey_id": str(value.survey_id), "project_id": str(value.project_id),
            "version_no": value.version_no, "state": value.version_state,
            "content_fingerprint": value.content_fingerprint,
            "declared_question_count": value.declared_question_count,
            "declared_option_count": value.declared_option_count,
            "declared_source_count": value.declared_source_count,
            "declared_target_department_count": value.declared_target_department_count,
            "supersedes_version_ref": _uid(value.supersedes_version_ref),
            "review_ref": _uid(value.review_ref),
            "review_round_ref": _uid(value.review_round_ref),
            "created_by": str(value.created_by), "created_at": _instant(value.created_at),
            "questions": [_question(item) for item in value.questions],
            "target_departments": targets}


def create_survey_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy, reads: SurveyReadService,
    survey_cursors: SurveyCursorCodec, version_cursors: SurveyVersionCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, survey_cursors, version_cursors)):
        raise ValueError("Survey read HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/surveys")
    async def list_surveys(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project, (size, cursor) = _canonical_uuid(project_id), _page(request)
        after_at, after_id = (None, None)
        if cursor is not None:
            after_at, after_id = survey_cursors.decode(
                cursor, project_id=project, session_token=token, page_size=size)
        try:
            result = await run_in_threadpool(reads.list_surveys,
                SurveyReadQuery(token, trace, project), page_size=size,
                after_updated_at=after_at, after_survey_id=after_id)
        except SurveyReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not SurveyPage or type(result.items) is not tuple
                or len(result.items) > size
                or any(type(item) is not SurveyView or item.project_id != project
                       for item in result.items)
                or result.has_more != (result.next_updated_at is not None
                                       and result.next_survey_id is not None)
                or result.has_more and (not result.items
                    or result.next_updated_at != result.items[-1].updated_at
                    or result.next_survey_id != result.items[-1].survey_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = survey_cursors.encode(
            project_id=project, session_token=token, page_size=size,
            updated_at=result.next_updated_at, survey_id=result.next_survey_id,
        ) if result.has_more else None
        return JSONResponse({"data": {"items": [_survey(item) for item in result.items],
            "next_cursor": next_cursor, "has_more": result.has_more},
            "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/surveys/{survey_id}")
    async def get_survey(project_id: str, survey_id: str,
                         request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, identity = _canonical_uuid(project_id), _canonical_uuid(survey_id)
        try:
            result = await run_in_threadpool(reads.get_survey,
                SurveyReadQuery(token, trace, project), identity)
        except SurveyReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if result.project_id != project or result.survey_id != identity:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _survey(result), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": result.etag})

    @router.get("/api/v1/projects/{project_id}/surveys/{survey_id}/versions")
    async def list_versions(project_id: str, survey_id: str,
                            request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project, identity = _canonical_uuid(project_id), _canonical_uuid(survey_id)
        size, cursor = _page(request)
        after = version_cursors.decode(
            cursor, project_id=project, survey_id=identity,
            session_token=token, page_size=size) if cursor is not None else None
        try:
            result = await run_in_threadpool(reads.list_versions,
                SurveyReadQuery(token, trace, project), survey_id=identity,
                page_size=size, after_version_no=after)
        except SurveyReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(result) is not SurveyVersionPage or type(result.items) is not tuple
                or len(result.items) > size
                or any(type(item) is not SurveyVersionView or item.project_id != project
                       or item.survey_id != identity for item in result.items)
                or result.has_more != (result.next_version_no is not None)
                or result.has_more and (not result.items
                    or result.next_version_no != result.items[-1].version_no)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = version_cursors.encode(
            project_id=project, survey_id=identity, session_token=token,
            page_size=size, position=result.next_version_no,
        ) if result.has_more else None
        return JSONResponse({"data": {"items": [_version(item) for item in result.items],
            "next_cursor": next_cursor, "has_more": result.has_more},
            "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get(
        "/api/v1/projects/{project_id}/surveys/{survey_id}/versions/{version_id}"
    )
    async def get_version(project_id: str, survey_id: str, version_id: str,
                          request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, survey, version = (_canonical_uuid(project_id),
            _canonical_uuid(survey_id), _canonical_uuid(version_id))
        try:
            result = await run_in_threadpool(reads.get_version,
                SurveyReadQuery(token, trace, project), survey_id=survey,
                survey_version_id=version)
        except SurveyReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (result.project_id != project or result.survey_id != survey
                or result.survey_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _version(result), "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store"})

    return router
