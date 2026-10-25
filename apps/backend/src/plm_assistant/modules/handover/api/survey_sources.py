"""Opt-in current approved Handover item candidates for Survey authoring."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisReadError, HandoverAnalysisReadQuery,
    HandoverAnalysisReadService, HandoverSurveySourcePage,
    HandoverSurveySourceView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

from .commands import _canonical_uuid
from .read import _error, _page_query, _query
from .read_cursor import HandoverSurveySourceCursorCodec


def create_handover_survey_source_router(*, sessions, origins,
                                         reads: HandoverAnalysisReadService,
                                         cursors: HandoverSurveySourceCursorCodec,
                                         ) -> APIRouter:
    if any(value is None for value in (sessions, origins, reads, cursors)):
        raise ValueError("Handover Survey source dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/survey-handover-sources")
    async def list_sources(project_id: str, request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        project = _canonical_uuid(project_id)
        size, cursor = _page_query(request)
        after = (cursors.decode(cursor, project_id=project,
                                session_token=token, page_size=size)
                 if cursor is not None else None)
        try:
            page = await run_in_threadpool(
                reads.list_survey_sources,
                HandoverAnalysisReadQuery(token, trace, project),
                page_size=size, after_row_id=after,
            )
        except HandoverAnalysisReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not HandoverSurveySourcePage
                or type(page.items) is not tuple or len(page.items) > size
                or type(page.has_more) is not bool
                or page.has_more != (page.next_row_id is not None)
                or page.has_more and (
                    not page.items
                    or page.next_row_id != page.items[-1].handover_item_row_id)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        items = []
        for row in page.items:
            ids = (row.handover_item_row_id,
                   row.handover_analysis_version_id,
                   row.handover_analysis_id, row.analysis_item_id,
                   row.project_id)
            if (type(row) is not HandoverSurveySourceView
                    or row.project_id != project
                    or any(type(value) is not uuid.UUID or value.int == 0
                           for value in ids)
                    or type(row.title) is not str
                    or not 1 <= len(row.title) <= 255
                    or row.state not in {"CONFIRMED", "RESOLVED", "ACCEPTED_RISK"}):
                raise ApplicationError("SYSTEM_UNAVAILABLE")
            items.append({
                "handover_item_row_id": str(row.handover_item_row_id),
                "handover_analysis_version_id": str(row.handover_analysis_version_id),
                "handover_analysis_id": str(row.handover_analysis_id),
                "analysis_item_id": str(row.analysis_item_id),
                "project_id": str(row.project_id),
                "title": row.title, "state": row.state,
            })
        next_cursor = (cursors.encode(
            project_id=project, session_token=token, page_size=size,
            row_id=page.next_row_id,
        ) if page.has_more else None)
        return JSONResponse(
            {"data": {"items": items, "next_cursor": next_cursor,
                      "has_more": page.has_more}, "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    return router
