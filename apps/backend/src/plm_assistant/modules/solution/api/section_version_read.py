"""Opt-in frozen SectionVersion GET/LIST HTTP history boundary."""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.application.read_section_version import (
    SectionVersionHistoryView, SectionVersionPage, SectionVersionReadError,
    SectionVersionReadQuery, SectionVersionReadService,
)
from .reference_read import _timestamp, _uuid
from .section_version_list_cursor import SectionVersionListCursorCodec


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)


def _failure(error: SectionVersionReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _summary(view: SectionVersionHistoryView, project: uuid.UUID,
             section: uuid.UUID) -> dict[str, object]:
    if (type(view) is not SectionVersionHistoryView
            or view.project_id != project
            or view.solution_section_id != section
            or type(view.solution_section_version_id) is not uuid.UUID
            or view.solution_section_version_id.int == 0
            or type(view.version_no) is not int or view.version_no < 1
            or view.version_state not in (
                "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED")
            or type(view.title) is not str or not view.title
            or type(view.content_fingerprint) is not bytes
            or len(view.content_fingerprint) != 32
            or type(view.created_by) is not uuid.UUID
            or view.created_by.int == 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "solution_section_version_id": str(view.solution_section_version_id),
        "solution_section_id": str(section), "project_id": str(project),
        "version_no": view.version_no, "version_state": view.version_state,
        "title": view.title,
        "content_fingerprint": view.content_fingerprint.hex(),
        "declared_requirement_count": len(view.requirement_refs),
        "declared_evidence_count": len(view.evidence_ids),
        "assumption_count": len(view.assumptions),
        "exclusion_count": len(view.exclusions),
        "supersedes_version_ref": (
            str(view.supersedes_version_ref)
            if view.supersedes_version_ref is not None else None),
        "review_ref": str(view.review_ref) if view.review_ref is not None else None,
        "review_round_ref": (
            str(view.review_round_ref)
            if view.review_round_ref is not None else None),
        "created_by": str(view.created_by),
        "created_at": _timestamp(view.created_at),
    }


def _detail(view: SectionVersionHistoryView, project: uuid.UUID,
            section: uuid.UUID) -> dict[str, object]:
    summary = _summary(view, project, section)
    return {
        **summary,
        "content_document_version_ref": (
            str(view.content_document_version_ref)
            if view.content_document_version_ref is not None else None),
        "content_artifact_ref": (
            str(view.content_artifact_ref)
            if view.content_artifact_ref is not None else None),
        "requirement_refs": [{
            "requirement_id": str(item.requirement_id),
            "requirement_version_id": str(item.requirement_version_id),
        } for item in view.requirement_refs],
        "evidence_ids": [str(item) for item in view.evidence_ids],
        "assumptions": list(view.assumptions),
        "exclusions": list(view.exclusions),
    }


def create_section_version_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: SectionVersionReadService,
    cursors: SectionVersionListCursorCodec,
) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("SectionVersion history HTTP dependencies required")
    router = APIRouter()

    async def _identity(request: Request) -> bytes:
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
        return token

    @router.post("/api/v1/projects/{project_id}/solution-sections/{section_id}/versions",
                 include_in_schema=False)
    async def create_closed(project_id: str, section_id: str) -> None:
        raise ApplicationError("RESOURCE_NOT_FOUND")

    @router.get("/api/v1/projects/{project_id}/solution-sections/{section_id}/versions")
    async def list_versions(project_id: str, section_id: str,
                            request: Request) -> JSONResponse:
        token = await _identity(request)
        project, section = _uuid(project_id), _uuid(section_id)
        entries = list(request.query_params.multi_items())
        if (len(entries) > 2 or len({key for key, _ in entries}) != len(entries)
                or any(key not in {"page_size", "cursor"} for key, _ in entries)):
            raise ApplicationError("REQUEST_MALFORMED")
        params = dict(entries)
        raw_size = params.get("page_size", "50")
        if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 100:
            raise ApplicationError("VALIDATION_FAILED")
        size = int(raw_size)
        before = (cursors.decode(
            params["cursor"], session_token=token,
            project_id=project, section_id=section, page_size=size)
            if "cursor" in params else None)
        trace = uuid.UUID(request.state.trace_id)
        try:
            page = await run_in_threadpool(
                reads.list, SectionVersionReadQuery(token, trace, project, section),
                page_size=size, before_version_no=before)
        except SectionVersionReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not SectionVersionPage
                or type(page.items) is not tuple or len(page.items) > size
                or type(page.has_more) is not bool
                or (page.has_more and (
                    not page.items
                    or page.next_before_version_no != page.items[-1].version_no))
                or (not page.has_more
                    and page.next_before_version_no is not None)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = [_summary(item, project, section) for item in page.items]
        try:
            next_cursor = (cursors.encode(
                session_token=token, project_id=project,
                section_id=section, page_size=size,
                before_version_no=page.next_before_version_no)
                if page.has_more else None)
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({
            "data": {"items": data, "next_cursor": next_cursor,
                     "has_more": page.has_more},
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/solution-sections/{section_id}"
                "/versions/{section_version_id}")
    async def get_version(project_id: str, section_id: str,
                          section_version_id: str,
                          request: Request) -> JSONResponse:
        token = await _identity(request)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        project, section, version = (
            _uuid(project_id), _uuid(section_id), _uuid(section_version_id))
        trace = uuid.UUID(request.state.trace_id)
        try:
            view = await run_in_threadpool(
                reads.get,
                SectionVersionReadQuery(token, trace, project, section), version)
        except SectionVersionReadError as error:
            raise _failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not SectionVersionHistoryView
                or view.solution_section_version_id != version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({
            "data": _detail(view, project, section),
            "trace_id": str(trace),
        }, headers={"Cache-Control": "no-store"})

    return router
