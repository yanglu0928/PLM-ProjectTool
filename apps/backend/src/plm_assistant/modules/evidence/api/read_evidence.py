"""Opt-in Evidence metadata list/detail HTTP; source Viewer remains separate."""

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
from plm_assistant.modules.evidence.api.list_cursor import EvidenceListCursorCodec
from plm_assistant.modules.evidence.application.read_evidence import (
    EvidencePage, EvidenceReadError, EvidenceReadQuery, EvidenceReadService, EvidenceView,
)
from plm_assistant.modules.evidence.domain.locator import EvidenceLocatorError, validate_evidence_locator
from plm_assistant.modules.platform.application.errors import ApplicationError


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)


def _date(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public(view: EvidenceView, *, include_excerpt: bool) -> dict[str, object]:
    if (type(view) is not EvidenceView
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.evidence_id, view.document_id, view.document_version_id))
            or view.scope not in ("GLOBAL", "PROJECT")
            or view.scope == "GLOBAL" and view.project_id is not None
            or view.scope == "PROJECT" and (
                type(view.project_id) is not uuid.UUID or view.project_id.int == 0)
            or type(view.content_fingerprint) is not bytes or len(view.content_fingerprint) != 32
            or type(view.display_label) is not str or not 1 <= len(view.display_label) <= 255
            or view.display_excerpt is not None and (
                type(view.display_excerpt) is not str or len(view.display_excerpt) > 500)
            or view.eligibility_state not in ("CANDIDATE", "ELIGIBLE", "INELIGIBLE", "REVOKED")
            or type(view.etag) is not str or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    try:
        locator = validate_evidence_locator(view.locator)
    except EvidenceLocatorError:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if locator != view.locator:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    result: dict[str, object] = {
        "evidence_id": str(view.evidence_id),
        "document_id": str(view.document_id),
        "document_version_id": str(view.document_version_id),
        "locator": locator,
        "content_fingerprint": view.content_fingerprint.hex(),
        "display_label": view.display_label,
        "eligibility_state": view.eligibility_state,
        "created_at": _date(view.created_at), "etag": view.etag,
    }
    if include_excerpt:
        result["display_excerpt"] = view.display_excerpt
    return result


def _error(error: EvidenceReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


async def _query(request: Request, *, sessions: SessionService,
                 origins: LoginOriginPolicy, scope: str,
                 project_id: uuid.UUID | None) -> EvidenceReadQuery:
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
    return EvidenceReadQuery(token, uuid.UUID(request.state.trace_id), scope, project_id)


def create_evidence_read_router(*, sessions: SessionService,
                                evidence: EvidenceReadService,
                                origins: LoginOriginPolicy,
                                cursors: EvidenceListCursorCodec) -> APIRouter:
    if any(item is None for item in (sessions, evidence, origins, cursors)):
        raise ValueError("Evidence read dependencies are required")
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
            page = await run_in_threadpool(evidence.list, query,
                                           after=after, limit=page_size)
        except EvidenceReadError as error:
            raise _error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not EvidencePage or len(page.items) > page_size
                or any(type(item) is not EvidenceView or item.scope != scope
                       or item.project_id != project_id for item in page.items)
                or page.has_more and (not page.items or page.next_after != (
                    page.items[-1].created_at, page.items[-1].evidence_id))
                or not page.has_more and page.next_after is not None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (cursors.encode(
            session_token=query.session_token, scope=scope, project_id=project_id,
            page_size=page_size, created_at=page.next_after[0],
            evidence_id=page.next_after[1],
        ) if page.has_more else None)
        return JSONResponse({"data": {
            "items": [_public(item, include_excerpt=True) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    async def get_for(request: Request, scope: str, project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins,
                             scope=scope, project_id=project_id)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(evidence.get, query, evidence_id)
        except EvidenceReadError as error:
            raise _error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.scope != scope or view.project_id != project_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": _public(view, include_excerpt=False),
                             "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store", "ETag": view.etag})

    @router.get("/api/v1/projects/{project_id}/evidence")
    async def list_project(project_id: uuid.UUID, request: Request) -> JSONResponse:
        return await list_for(request, "PROJECT", project_id)

    @router.get("/api/v1/projects/{project_id}/evidence/{evidence_id}")
    async def get_project(project_id: uuid.UUID, evidence_id: uuid.UUID,
                          request: Request) -> JSONResponse:
        return await get_for(request, "PROJECT", project_id, evidence_id)

    @router.get("/api/v1/global/evidence")
    async def list_global(request: Request) -> JSONResponse:
        return await list_for(request, "GLOBAL", None)

    @router.get("/api/v1/global/evidence/{evidence_id}")
    async def get_global(evidence_id: uuid.UUID, request: Request) -> JSONResponse:
        return await get_for(request, "GLOBAL", None, evidence_id)

    return router
