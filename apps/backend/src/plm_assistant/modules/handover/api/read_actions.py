"""Opt-in Handover Action LIST/GET HTTP projection."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.handover.application.read_actions import (
    HandoverActionCurrentEventView, HandoverActionDetailView,
    HandoverActionEvidenceView, HandoverActionPage, HandoverActionReadError,
    HandoverActionReadQuery, HandoverActionReadService,
    HandoverActionResponseView, HandoverActionSummaryView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

from .action_list_cursor import HandoverActionListCursorCodec


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _date(value: datetime | None) -> str | None:
    if value is None:
        return None
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _uid(value: uuid.UUID | None) -> str | None:
    if value is None:
        return None
    if type(value) is not uuid.UUID or value.int == 0:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return str(value)


def _valid_uid(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _summary(view: HandoverActionSummaryView, project_id: uuid.UUID) -> dict[str, object]:
    if (type(view) is not HandoverActionSummaryView
            or view.project_id != project_id
            or type(view.action_item_id) is not uuid.UUID or view.action_item_id.int == 0
            or view.source_kind not in ("ANALYSIS_ITEM", "HUMAN")
            or view.action_type not in ("PROVIDE_INFO", "CONFIRM_DECISION", "RESOLVE_CONFLICT",
                                        "MITIGATE_RISK", "DEFINE_SCOPE", "OTHER")
            or type(view.title) is not str or not view.title
            or type(view.owner_ref) is not uuid.UUID or view.owner_ref.int == 0
            or view.priority not in ("LOW", "MEDIUM", "HIGH", "URGENT")
            or view.action_state not in ("OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED",
                                         "CLOSED", "CANCELLED")
            or type(view.etag) is not str or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "action_item_id": str(view.action_item_id), "source_kind": view.source_kind,
        "action_type": view.action_type, "title": view.title,
        "owner_ref": str(view.owner_ref), "due_at": _date(view.due_at),
        "priority": view.priority, "action_state": view.action_state,
        "submitted_at": _date(view.submitted_at), "verified_at": _date(view.verified_at),
        "closed_at": _date(view.closed_at),
        "resolution_trace_ref": _uid(view.resolution_trace_ref),
        "updated_at": _date(view.updated_at), "etag": view.etag,
    }


def _detail(view: HandoverActionDetailView, project_id: uuid.UUID) -> dict[str, object]:
    if (type(view) is not HandoverActionDetailView
            or type(view.summary) is not HandoverActionSummaryView
            or type(view.requested_input_spec) is not dict
            or type(view.responses) is not tuple
            or len(view.responses) > 500
            or any(type(item) is not HandoverActionResponseView
                   or not _valid_uid(item.document_id)
                   or not _valid_uid(item.document_version_id)
                   or type(item.ordinal) is not int or item.ordinal < 0
                   for item in view.responses)
            or type(view.evidence) is not tuple or len(view.evidence) > 1000
            or any(type(item) is not HandoverActionEvidenceView
                   or not _valid_uid(item.evidence_id)
                   or item.purpose not in ("SUBMISSION", "VERIFICATION", "RESOLUTION")
                   or type(item.ordinal) is not int or item.ordinal < 0
                   for item in view.evidence)
            or [item.ordinal for item in view.responses]
               != sorted({item.ordinal for item in view.responses})
            or [item.ordinal for item in view.evidence]
               != sorted({item.ordinal for item in view.evidence})
            or not _valid_uid(view.created_by)
            or type(view.current_event) is not HandoverActionCurrentEventView
            or not _valid_uid(view.current_event.action_state_event_id)
            or type(view.current_event.sequence_no) is not int
            or view.current_event.sequence_no < 0
            or not _valid_uid(view.current_event.actor_id)
            or view.current_event.to_state != view.summary.action_state
            or view.current_event.from_state is not None
               and view.current_event.from_state not in (
                   "OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED", "CLOSED", "CANCELLED")
            or type(view.current_event.reason) is not str or not view.current_event.reason
            or type(view.created_reason) is not str or not view.created_reason):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    if ((view.summary.source_kind == "ANALYSIS_ITEM") != (
            _valid_uid(view.source_analysis_version_ref)
            and _valid_uid(view.source_item_id)
            and view.human_source_reason is None)
            or (view.summary.source_kind == "HUMAN") != (
                view.source_analysis_version_ref is None
                and view.source_item_id is None
                and type(view.human_source_reason) is str
                and bool(view.human_source_reason))):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    data = _summary(view.summary, project_id)
    data.update({
        "source_analysis_version_ref": _uid(view.source_analysis_version_ref),
        "source_item_id": _uid(view.source_item_id),
        "human_source_reason": view.human_source_reason,
        "requested_input_spec": view.requested_input_spec,
        "responses": [{"document_id": str(item.document_id),
                       "document_version_id": str(item.document_version_id),
                       "ordinal": item.ordinal} for item in view.responses],
        "evidence": [{"evidence_id": str(item.evidence_id), "purpose": item.purpose,
                      "ordinal": item.ordinal} for item in view.evidence],
        "created_by": _uid(view.created_by), "created_reason": view.created_reason,
        "created_at": _date(view.created_at), "verified_by": _uid(view.verified_by),
        "current_event": {
            "action_state_event_id": str(view.current_event.action_state_event_id),
            "sequence_no": view.current_event.sequence_no,
            "from_state": view.current_event.from_state,
            "to_state": view.current_event.to_state,
            "actor_id": str(view.current_event.actor_id),
            "reason": view.current_event.reason,
            "occurred_at": _date(view.current_event.occurred_at),
        },
    })
    return data


def _error(exc: HandoverActionReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


async def _query(request: Request, project_id: uuid.UUID, *,
                 sessions: SessionService,
                 origins: LoginOriginPolicy) -> HandoverActionReadQuery:
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
    if project_id.int == 0:
        raise ApplicationError("RESOURCE_NOT_FOUND")
    return HandoverActionReadQuery(
        token, uuid.UUID(request.state.trace_id), project_id,
    )


def create_handover_action_read_router(*, sessions: SessionService,
                                       actions: HandoverActionReadService,
                                       origins: LoginOriginPolicy,
                                       cursors: HandoverActionListCursorCodec) -> APIRouter:
    if any(value is None for value in (sessions, actions, origins, cursors)):
        raise ValueError("Handover Action read dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/handover-action-items")
    async def list_actions(project_id: uuid.UUID, request: Request) -> JSONResponse:
        query = await _query(request, project_id, sessions=sessions, origins=origins)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        position = (cursors.decode(
            params["cursor"], session_token=query.session_token,
            project_id=project_id, page_size=page_size,
        ) if "cursor" in params else (None, None))
        try:
            page = await run_in_threadpool(
                actions.list_page, query, page_size=page_size,
                after_updated_at=position[0], after_action_item_id=position[1],
            )
        except HandoverActionReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not HandoverActionPage or len(page.items) > page_size
                or any(type(item) is not HandoverActionSummaryView
                       or item.project_id != project_id for item in page.items)
                or page.has_more and (
                    not page.items
                    or page.next_updated_at != page.items[-1].updated_at
                    or page.next_action_item_id != page.items[-1].action_item_id)
                or not page.has_more and (
                    page.next_updated_at is not None
                    or page.next_action_item_id is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=query.session_token, project_id=project_id,
            page_size=page_size, updated_at=page.next_updated_at,
            action_item_id=page.next_action_item_id,
        ) if page.has_more else None)
        return JSONResponse({
            "data": {"items": [_summary(item, project_id) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/handover-action-items/{action_item_id}")
    async def get_action(project_id: uuid.UUID, action_item_id: uuid.UUID,
                         request: Request) -> JSONResponse:
        query = await _query(request, project_id, sessions=sessions, origins=origins)
        if request.url.query or action_item_id.int == 0:
            raise ApplicationError(
                "REQUEST_MALFORMED" if request.url.query else "RESOURCE_NOT_FOUND",
            )
        try:
            view = await run_in_threadpool(actions.get, query, action_item_id)
        except HandoverActionReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.summary.project_id != project_id or view.summary.action_item_id != action_item_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _detail(view, project_id), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.summary.etag},
        )
    return router
