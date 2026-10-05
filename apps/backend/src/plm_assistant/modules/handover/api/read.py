"""Opt-in HTTP boundary for five Handover Analysis read operations."""

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
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisItemPage, HandoverAnalysisItemView, HandoverAnalysisPage,
    HandoverAnalysisReadError, HandoverAnalysisReadQuery,
    HandoverAnalysisReadService, HandoverAnalysisVersionPage,
    HandoverAnalysisVersionView, HandoverAnalysisView, HandoverAITaskView,
    HandoverItemCapabilityView, HandoverItemOptionView,
    HandoverSourceDocumentView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

from .commands import _canonical_uuid, _instant
from .read_cursor import (
    HandoverAnalysisCursorCodec, HandoverItemCursorCodec,
    HandoverVersionCursorCodec,
)


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_SOURCE = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_ANALYSIS_STATES = frozenset({"ACTIVE", "ARCHIVED", "RESTRICTED"})
_VERSION_STATES = frozenset({
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED",
})
_ITEM_TYPES = frozenset({"GAP", "MISSING", "CONFLICT", "RISK", "SCOPE",
                         "NEED_CONFIRM"})
_SEVERITIES = frozenset({"LOW", "MEDIUM", "HIGH", "CRITICAL"})
_PRIORITIES = frozenset({"LOW", "MEDIUM", "HIGH", "URGENT"})
_ITEM_STATES = frozenset({
    "CANDIDATE", "CONFIRMED", "RESOLVED", "ACCEPTED_RISK", "REJECTED",
    "SUPERSEDED",
})


def _error(exc: HandoverAnalysisReadError) -> ApplicationError:
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


def _uuid_or_none(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _analysis(view: HandoverAnalysisView) -> dict[str, object]:
    if (type(view) is not HandoverAnalysisView
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.handover_analysis_id, view.project_id, view.created_by))
            or type(view.analysis_purpose) is not str or not view.analysis_purpose
            or _SOURCE.fullmatch(view.source_set_ref) is None
            or view.analysis_state not in _ANALYSIS_STATES
            or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "handover_analysis_id": str(view.handover_analysis_id),
        "project_id": str(view.project_id),
        "analysis_purpose": view.analysis_purpose,
        "source_set_ref": view.source_set_ref,
        "state": view.analysis_state,
        "current_approved_version_ref": _uuid_or_none(
            view.current_approved_version_ref
        ),
        "created_by": str(view.created_by), "created_at": _instant(view.created_at),
        "updated_at": _instant(view.updated_at), "etag": view.etag,
    }


def _source(value: HandoverSourceDocumentView) -> dict[str, object]:
    if (type(value) is not HandoverSourceDocumentView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.document_id, value.document_version_id))
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"document_id": str(value.document_id),
            "document_version_id": str(value.document_version_id),
            "ordinal": value.ordinal}


def _ai_task(value: HandoverAITaskView) -> dict[str, object]:
    if (type(value) is not HandoverAITaskView
            or type(value.ai_task_id) is not uuid.UUID or value.ai_task_id.int == 0
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"ai_task_id": str(value.ai_task_id), "ordinal": value.ordinal}


def _version(view: HandoverAnalysisVersionView) -> dict[str, object]:
    ids = (view.handover_analysis_version_id, view.handover_analysis_id,
           view.project_id, view.capability_baseline_id,
           view.capability_baseline_version_ref, view.created_by)
    optional = (view.supersedes_version_ref, view.review_ref, view.review_round_ref)
    counts = (view.declared_source_count, view.declared_item_count,
              view.declared_evidence_count, view.declared_capability_ref_count,
              view.declared_ai_task_count)
    if (type(view) is not HandoverAnalysisVersionView
            or any(type(value) is not uuid.UUID or value.int == 0 for value in ids)
            or any(value is not None and (
                type(value) is not uuid.UUID or value.int == 0) for value in optional)
            or type(view.version_no) is not int or view.version_no <= 0
            or view.version_state not in _VERSION_STATES
            or _SOURCE.fullmatch(view.source_set_ref) is None
            or _HASH.fullmatch(view.content_fingerprint) is None
            or any(type(value) is not int or value < 0 for value in counts)
            or type(view.source_documents) is not tuple
            or type(view.ai_tasks) is not tuple):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "handover_analysis_version_id": str(view.handover_analysis_version_id),
        "handover_analysis_id": str(view.handover_analysis_id),
        "project_id": str(view.project_id), "version_no": view.version_no,
        "state": view.version_state, "source_set_ref": view.source_set_ref,
        "capability_baseline_id": str(view.capability_baseline_id),
        "capability_baseline_version_ref": str(view.capability_baseline_version_ref),
        "content_fingerprint": view.content_fingerprint,
        "declared_source_count": view.declared_source_count,
        "declared_item_count": view.declared_item_count,
        "declared_evidence_count": view.declared_evidence_count,
        "declared_capability_ref_count": view.declared_capability_ref_count,
        "declared_ai_task_count": view.declared_ai_task_count,
        "supersedes_version_ref": _uuid_or_none(view.supersedes_version_ref),
        "review_ref": _uuid_or_none(view.review_ref),
        "review_round_ref": _uuid_or_none(view.review_round_ref),
        "created_by": str(view.created_by), "created_at": _instant(view.created_at),
        "source_documents": [_source(value) for value in view.source_documents],
        "ai_tasks": [_ai_task(value) for value in view.ai_tasks],
    }


def _option(value: HandoverItemOptionView) -> dict[str, object]:
    if (type(value) is not HandoverItemOptionView
            or type(value.option_code) is not str or not value.option_code
            or type(value.label) is not str or not value.label
            or value.description is not None and type(value.description) is not str
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"option_code": value.option_code, "label": value.label,
            "description": value.description, "ordinal": value.ordinal}


def _capability(value: HandoverItemCapabilityView) -> dict[str, object]:
    if (type(value) is not HandoverItemCapabilityView
            or any(type(item) is not uuid.UUID or item.int == 0 for item in (
                value.baseline_version_id, value.capability_item_id))
            or type(value.ordinal) is not int or value.ordinal < 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {"baseline_version_id": str(value.baseline_version_id),
            "capability_item_id": str(value.capability_item_id),
            "ordinal": value.ordinal}


def _json_object(value: dict[str, object]) -> dict[str, object]:
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


def _item(view: HandoverAnalysisItemView) -> dict[str, object]:
    ids = (view.analysis_item_id, view.handover_analysis_version_id,
           view.handover_analysis_id, view.project_id)
    texts = (view.title, view.statement, view.impact)
    optional_texts = (view.recommendation, view.confirmation_question)
    if (type(view) is not HandoverAnalysisItemView
            or any(type(value) is not uuid.UUID or value.int == 0 for value in ids)
            or type(view.ordinal) is not int or view.ordinal < 0
            or view.item_type not in _ITEM_TYPES
            or any(type(value) is not str or not value for value in texts)
            or any(value is not None and type(value) is not str
                   for value in optional_texts)
            or view.severity not in _SEVERITIES or view.priority not in _PRIORITIES
            or type(view.source_missing) is not bool
            or view.item_state not in _ITEM_STATES
            or type(view.evidence_refs) is not tuple
            or any(type(value) is not uuid.UUID or value.int == 0
                   for value in view.evidence_refs)
            or type(view.capability_refs) is not tuple
            or type(view.options) is not tuple):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "analysis_item_id": str(view.analysis_item_id),
        "handover_analysis_version_id": str(view.handover_analysis_version_id),
        "handover_analysis_id": str(view.handover_analysis_id),
        "project_id": str(view.project_id), "ordinal": view.ordinal,
        "item_type": view.item_type, "title": view.title,
        "statement": view.statement, "impact": view.impact,
        "severity": view.severity, "priority": view.priority,
        "recommendation": view.recommendation,
        "confirmation_question": view.confirmation_question,
        "required_input_spec": _json_object(view.required_input_spec),
        "source_missing": view.source_missing, "state": view.item_state,
        "evidence_refs": [str(value) for value in view.evidence_refs],
        "capability_refs": [_capability(value) for value in view.capability_refs],
        "options": [_option(value) for value in view.options],
    }


def create_handover_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: HandoverAnalysisReadService,
    analysis_cursors: HandoverAnalysisCursorCodec,
    version_cursors: HandoverVersionCursorCodec,
    item_cursors: HandoverItemCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, analysis_cursors, version_cursors,
            item_cursors)):
        raise ValueError("Handover read HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/handover-analyses")
    async def list_analyses(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project = _canonical_uuid(project_id)
        size, cursor = _page_query(request)
        updated_at, after_id = (None, None)
        if cursor is not None:
            updated_at, after_id = analysis_cursors.decode(
                cursor, project_id=project, session_token=token, page_size=size,
            )
        try:
            page = await run_in_threadpool(
                reads.list_analyses, HandoverAnalysisReadQuery(token, trace, project),
                page_size=size, after_updated_at=updated_at,
                after_handover_analysis_id=after_id,
            )
        except HandoverAnalysisReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not HandoverAnalysisPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not HandoverAnalysisView
                       or item.project_id != project for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_updated_at is not None
                                     and page.next_handover_analysis_id is not None)
                or page.has_more and (not page.items
                                      or page.next_updated_at != page.items[-1].updated_at
                                      or page.next_handover_analysis_id
                                      != page.items[-1].handover_analysis_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = analysis_cursors.encode(
            project_id=project, session_token=token, page_size=size,
            updated_at=page.next_updated_at,
            analysis_id=page.next_handover_analysis_id,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_analysis(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/handover-analyses/{analysis_id}")
    async def get_analysis(project_id: str, analysis_id: str,
                           request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, analysis_id_value = (
            _canonical_uuid(project_id), _canonical_uuid(analysis_id),
        )
        try:
            view = await run_in_threadpool(
                reads.get_analysis,
                HandoverAnalysisReadQuery(token, trace, project), analysis_id_value,
            )
        except HandoverAnalysisReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not HandoverAnalysisView
                or view.project_id != project
                or view.handover_analysis_id != analysis_id_value):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _analysis(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.get(
        "/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions"
    )
    async def list_versions(project_id: str, analysis_id: str,
                            request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project, analysis = _canonical_uuid(project_id), _canonical_uuid(analysis_id)
        size, cursor = _page_query(request)
        after = version_cursors.decode(
            cursor, project_id=project, analysis_id=analysis,
            session_token=token, page_size=size,
        ) if cursor is not None else None
        try:
            page = await run_in_threadpool(
                reads.list_versions,
                HandoverAnalysisReadQuery(token, trace, project),
                handover_analysis_id=analysis, page_size=size,
                after_version_no=after,
            )
        except HandoverAnalysisReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not HandoverAnalysisVersionPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not HandoverAnalysisVersionView
                       or item.project_id != project
                       or item.handover_analysis_id != analysis for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_version_no is not None)
                or page.has_more and (not page.items
                                      or page.next_version_no
                                      != page.items[-1].version_no)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = version_cursors.encode(
            project_id=project, analysis_id=analysis, session_token=token,
            page_size=size, position=page.next_version_no,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_version(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get(
        "/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/"
        "{analysis_version_id}"
    )
    async def get_version(project_id: str, analysis_id: str,
                          analysis_version_id: str,
                          request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, analysis, version = (
            _canonical_uuid(project_id), _canonical_uuid(analysis_id),
            _canonical_uuid(analysis_version_id),
        )
        try:
            view = await run_in_threadpool(
                reads.get_version,
                HandoverAnalysisReadQuery(token, trace, project),
                handover_analysis_id=analysis,
                handover_analysis_version_id=version,
            )
        except HandoverAnalysisReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not HandoverAnalysisVersionView
                or view.project_id != project
                or view.handover_analysis_id != analysis
                or view.handover_analysis_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _version(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    @router.get(
        "/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/"
        "{analysis_version_id}/items"
    )
    async def list_items(project_id: str, analysis_id: str,
                         analysis_version_id: str,
                         request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project, analysis, version = (
            _canonical_uuid(project_id), _canonical_uuid(analysis_id),
            _canonical_uuid(analysis_version_id),
        )
        size, cursor = _page_query(request)
        after = item_cursors.decode(
            cursor, project_id=project, analysis_id=analysis, version_id=version,
            session_token=token, page_size=size,
        ) if cursor is not None else None
        try:
            page = await run_in_threadpool(
                reads.list_items, HandoverAnalysisReadQuery(token, trace, project),
                handover_analysis_id=analysis,
                handover_analysis_version_id=version, page_size=size,
                after_ordinal=after,
            )
        except HandoverAnalysisReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not HandoverAnalysisItemPage
                or type(page.items) is not tuple or len(page.items) > size
                or any(type(item) is not HandoverAnalysisItemView
                       or item.project_id != project
                       or item.handover_analysis_id != analysis
                       or item.handover_analysis_version_id != version
                       for item in page.items)
                or type(page.has_more) is not bool
                or page.has_more != (page.next_ordinal is not None)
                or page.has_more and (not page.items
                                      or page.next_ordinal != page.items[-1].ordinal)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = item_cursors.encode(
            project_id=project, analysis_id=analysis, version_id=version,
            session_token=token, page_size=size, position=page.next_ordinal,
        ) if page.has_more else None
        return JSONResponse({"data": {
            "items": [_item(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    return router
