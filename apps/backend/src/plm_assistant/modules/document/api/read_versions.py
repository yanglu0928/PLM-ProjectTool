"""Opt-in immutable DocumentVersion metadata list/detail HTTP projection."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.document.api.read_documents import _date, _error, _query
from plm_assistant.modules.document.api.version_list_cursor import VersionListCursorCodec
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentReadService, DocumentVersionPage, DocumentVersionView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)


def _public(view: DocumentVersionView) -> dict[str, object]:
    if (type(view) is not DocumentVersionView
            or type(view.document_version_id) is not uuid.UUID
            or view.document_version_id.int == 0
            or type(view.document_id) is not uuid.UUID or view.document_id.int == 0
            or type(view.version_no) is not int or view.version_no <= 0
            or type(view.content_sha256) is not str
            or _HASH.fullmatch(view.content_sha256) is None
            or type(view.size_bytes) is not int or view.size_bytes < 0
            or type(view.detected_mime) is not str or not view.detected_mime
            or view.availability_state != "AVAILABLE"
            or view.supersedes_version_ref is not None and (
                type(view.supersedes_version_ref) is not uuid.UUID
                or view.supersedes_version_ref.int == 0)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "document_version_id": str(view.document_version_id),
        "version_no": view.version_no,
        "content_sha256": view.content_sha256,
        "size_bytes": view.size_bytes,
        "detected_mime": view.detected_mime,
        "availability_state": view.availability_state,
        "supersedes_version_ref": (str(view.supersedes_version_ref)
                                   if view.supersedes_version_ref else None),
        "created_at": _date(view.created_at),
        "integrity_checked_at": (_date(view.integrity_checked_at)
                                 if view.integrity_checked_at else None),
    }


def create_document_version_read_router(*, sessions: SessionService,
                                        documents: DocumentReadService,
                                        origins: LoginOriginPolicy,
                                        cursors: VersionListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, documents, origins, cursors)):
        raise ValueError("DocumentVersion read dependencies are required")
    router = APIRouter()

    async def list_for(request: Request, *, scope: str,
                       project_id: uuid.UUID | None,
                       document_id: uuid.UUID) -> JSONResponse:
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
            project_id=project_id, document_id=document_id, page_size=page_size,
        ) if "cursor" in params else None)
        try:
            page = await run_in_threadpool(
                documents.list_versions, query, document_id,
                before_version_no=before, limit=page_size,
            )
        except DocumentReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not DocumentVersionPage or len(page.items) > page_size
                or any(type(item) is not DocumentVersionView
                       or item.document_id != document_id for item in page.items)
                or page.has_more and (not page.items or
                                      page.next_before_version_no != page.items[-1].version_no)
                or not page.has_more and page.next_before_version_no is not None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=query.session_token, scope=scope, project_id=project_id,
            document_id=document_id, page_size=page_size,
            before_version_no=page.next_before_version_no,
        ) if page.has_more else None)
        return JSONResponse({
            "data": {"items": [_public(item) for item in page.items],
                     "next_cursor": next_cursor, "has_more": page.has_more},
            "trace_id": request.state.trace_id,
        }, headers={"Cache-Control": "no-store"})

    async def get_for(request: Request, *, scope: str,
                      project_id: uuid.UUID | None, document_id: uuid.UUID,
                      version_id: uuid.UUID) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins,
                             scope=scope, project_id=project_id)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(
                documents.get_version, query, document_id, version_id,
            )
        except DocumentReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.document_id != document_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _public(view), "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/documents/{document_id}/versions")
    async def list_project(project_id: uuid.UUID, document_id: uuid.UUID,
                           request: Request) -> JSONResponse:
        return await list_for(request, scope="PROJECT", project_id=project_id,
                              document_id=document_id)

    @router.get("/api/v1/projects/{project_id}/documents/{document_id}/versions/{version_id}")
    async def get_project(project_id: uuid.UUID, document_id: uuid.UUID,
                          version_id: uuid.UUID, request: Request) -> JSONResponse:
        return await get_for(request, scope="PROJECT", project_id=project_id,
                             document_id=document_id, version_id=version_id)

    @router.get("/api/v1/global/documents/{document_id}/versions")
    async def list_global(document_id: uuid.UUID, request: Request) -> JSONResponse:
        return await list_for(request, scope="GLOBAL", project_id=None,
                              document_id=document_id)

    @router.get("/api/v1/global/documents/{document_id}/versions/{version_id}")
    async def get_global(document_id: uuid.UUID, version_id: uuid.UUID,
                         request: Request) -> JSONResponse:
        return await get_for(request, scope="GLOBAL", project_id=None,
                             document_id=document_id, version_id=version_id)

    return router
