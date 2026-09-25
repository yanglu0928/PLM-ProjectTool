"""Opt-in, fixed-version ParseRecord history HTTP projection."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.document.api.parse_list_cursor import ParseListCursorCodec
from plm_assistant.modules.document.api.read_documents import _date, _error, _query
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadService, ParseRecordPage, ParseRecordView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_STATES = frozenset({"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"})


def _public(view: ParseRecordView) -> dict[str, object]:
    if (type(view) is not ParseRecordView
            or type(view.parse_record_id) is not uuid.UUID or view.parse_record_id.int == 0
            or type(view.document_version_id) is not uuid.UUID
            or view.document_version_id.int == 0
            or type(view.parser_profile) is not str or not view.parser_profile
            or type(view.parser_version) is not str or not view.parser_version
            or view.parse_state not in _STATES
            or type(view.attempt_no) is not int or view.attempt_no <= 0
            or type(view.job_ref) is not uuid.UUID or view.job_ref.int == 0
            or view.result_ref is not None and (
                view.parse_state != "SUCCEEDED" or type(view.result_ref) is not uuid.UUID
                or view.result_ref.int == 0)
            or view.parse_state == "SUCCEEDED" and view.result_ref is None
            or view.error_code is not None and (
                type(view.error_code) is not str
                or _ERROR_CODE.fullmatch(view.error_code) is None)
            or view.retryable is not None and type(view.retryable) is not bool):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "parse_record_id": str(view.parse_record_id),
        "parser_profile": view.parser_profile,
        "parser_version": view.parser_version,
        "parse_state": view.parse_state,
        "attempt_no": view.attempt_no,
        "job_ref": str(view.job_ref),
        "result_ref": str(view.result_ref) if view.result_ref else None,
        "error_code": view.error_code,
        "retryable": view.retryable,
        "created_at": _date(view.created_at),
        "started_at": _date(view.started_at) if view.started_at else None,
        "completed_at": _date(view.completed_at) if view.completed_at else None,
    }


def create_document_parse_read_router(*, sessions: SessionService,
                                      documents: DocumentReadService,
                                      origins: LoginOriginPolicy,
                                      cursors: ParseListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, documents, origins, cursors)):
        raise ValueError("Document parse read dependencies are required")
    router = APIRouter()

    async def list_for(request: Request, *, scope: str,
                       project_id: uuid.UUID | None, document_id: uuid.UUID,
                       version_id: uuid.UUID) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins,
                             scope=scope, project_id=project_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
            raise ApplicationError("VALIDATION_FAILED")
        page_size = int(raw_size)
        before = (cursors.decode(
            params["cursor"], session_token=query.session_token, scope=scope,
            project_id=project_id, document_id=document_id,
            document_version_id=version_id, page_size=page_size,
        ) if "cursor" in params else None)
        try:
            page = await run_in_threadpool(
                documents.list_parses, query, document_id, version_id,
                before=before, limit=page_size,
            )
        except DocumentReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not ParseRecordPage or len(page.items) > page_size
                or any(type(item) is not ParseRecordView
                       or item.document_version_id != version_id for item in page.items)
                or page.has_more and (not page.items or page.next_before != (
                    page.items[-1].created_at, page.items[-1].parse_record_id))
                or not page.has_more and page.next_before is not None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=query.session_token, scope=scope, project_id=project_id,
            document_id=document_id, document_version_id=version_id,
            page_size=page_size, before=page.next_before,
        ) if page.has_more else None)
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/documents/{document_id}/versions/{version_id}/parses")
    async def list_project(project_id: uuid.UUID, document_id: uuid.UUID,
                           version_id: uuid.UUID, request: Request) -> JSONResponse:
        return await list_for(request, scope="PROJECT", project_id=project_id,
                              document_id=document_id, version_id=version_id)

    @router.get("/api/v1/global/documents/{document_id}/versions/{version_id}/parses")
    async def list_global(document_id: uuid.UUID, version_id: uuid.UUID,
                          request: Request) -> JSONResponse:
        return await list_for(request, scope="GLOBAL", project_id=None,
                              document_id=document_id, version_id=version_id)

    return router
