"""Opt-in Document metadata list/detail HTTP projection."""

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
from plm_assistant.modules.document.api.document_list_cursor import DocumentListCursorCodec
from plm_assistant.modules.document.application.read_documents import (
    DocumentPage, DocumentReadError, DocumentReadQuery, DocumentReadService, DocumentView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _date(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public(view: DocumentView) -> dict[str, object]:
    if (type(view) is not DocumentView
            or type(view.document_id) is not uuid.UUID or view.document_id.int == 0
            or view.scope not in ("GLOBAL", "PROJECT")
            or view.scope == "GLOBAL" and view.project_id is not None
            or view.scope == "PROJECT" and (
                type(view.project_id) is not uuid.UUID or view.project_id.int == 0)
            or type(view.document_category) is not str
            or view.document_subtype is not None and type(view.document_subtype) is not str
            or type(view.title) is not str
            or type(view.original_display_name) is not str
            or view.document_state not in ("ACTIVE", "ARCHIVED")
            or any(ref is not None and type(ref) is not uuid.UUID for ref in (
                view.latest_version_ref, view.effective_version_ref))
            or type(view.etag) is not str or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "document_id": str(view.document_id), "scope": view.scope,
        "category": view.document_category, "subtype": view.document_subtype,
        "title": view.title, "display_name": view.original_display_name,
        "state": view.document_state,
        "latest_version_ref": (str(view.latest_version_ref)
                               if view.latest_version_ref is not None else None),
        "effective_version_ref": (str(view.effective_version_ref)
                                  if view.effective_version_ref is not None else None),
        "created_at": _date(view.created_at), "etag": view.etag,
    }


def _error(exc: DocumentReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(exc.code, "SYSTEM_UNAVAILABLE"))


async def _query(request: Request, *, sessions: SessionService,
                 origins: LoginOriginPolicy, scope: str,
                 project_id: uuid.UUID | None) -> DocumentReadQuery:
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
    if project_id is not None and project_id.int == 0:
        raise ApplicationError("RESOURCE_NOT_FOUND")
    return DocumentReadQuery(token, uuid.UUID(request.state.trace_id), scope, project_id)


def create_document_read_router(*, sessions: SessionService,
                                documents: DocumentReadService,
                                origins: LoginOriginPolicy,
                                cursors: DocumentListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, documents, origins, cursors)):
        raise ValueError("Document read dependencies are required")
    router = APIRouter()

    async def list_for(request: Request, scope: str,
                       project_id: uuid.UUID | None) -> JSONResponse:
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
        after = (cursors.decode(params["cursor"], session_token=query.session_token,
                                scope=scope, project_id=project_id, page_size=page_size)
                 if "cursor" in params else None)
        try:
            page = await run_in_threadpool(documents.list, query,
                                           after_document_id=after, limit=page_size)
        except DocumentReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not DocumentPage or len(page.items) > page_size
                or any(type(item) is not DocumentView or item.scope != scope
                       or item.project_id != project_id for item in page.items)
                or page.has_more and (not page.items or
                                      page.next_after_document_id != page.items[-1].document_id)
                or not page.has_more and page.next_after_document_id is not None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=query.session_token, scope=scope, project_id=project_id,
            page_size=page_size, document_id=page.next_after_document_id,
        ) if page.has_more else None)
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    async def get_for(request: Request, scope: str, project_id: uuid.UUID | None,
                      document_id: uuid.UUID) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins,
                             scope=scope, project_id=project_id)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(documents.get, query, document_id)
        except DocumentReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.scope != scope or view.project_id != project_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        body = _public(view)
        return JSONResponse({"data": body, "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.get("/api/v1/projects/{project_id}/documents")
    async def list_project(project_id: uuid.UUID, request: Request) -> JSONResponse:
        return await list_for(request, "PROJECT", project_id)

    @router.get("/api/v1/projects/{project_id}/documents/{document_id}")
    async def get_project(project_id: uuid.UUID, document_id: uuid.UUID,
                          request: Request) -> JSONResponse:
        return await get_for(request, "PROJECT", project_id, document_id)

    @router.get("/api/v1/global/documents")
    async def list_global(request: Request) -> JSONResponse:
        return await list_for(request, "GLOBAL", None)

    @router.get("/api/v1/global/documents/{document_id}")
    async def get_global(document_id: uuid.UUID, request: Request) -> JSONResponse:
        return await get_for(request, "GLOBAL", None, document_id)

    return router
