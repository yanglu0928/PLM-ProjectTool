"""Opt-in frozen Trace graph GET endpoints; production mounting is separate."""

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
from plm_assistant.modules.trace.application.page_graph import TraceGraphPage
from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency, TraceQueryError
from plm_assistant.modules.trace.application.read_public_graph import (
    TracePublicGraphQuery, TracePublicGraphReadService,
)
from plm_assistant.modules.trace.application.target_proof import TraceResourceVersionRef
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


_FIELDS = frozenset({
    "resource_type", "resource_id", "version_id", "relation_type",
    "max_depth", "max_nodes", "page_size", "cursor",
})


def _uuid(value: str) -> uuid.UUID:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _number(value: str, maximum: int) -> int:
    if re.fullmatch(r"[1-9][0-9]{0,2}", value, flags=re.ASCII) is None:
        raise ApplicationError("VALIDATION_FAILED")
    parsed = int(value)
    if parsed > maximum:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _parameters(request: Request) -> dict[str, str]:
    if len(request.scope.get("query_string", b"")) > 4096:
        raise ApplicationError("REQUEST_MALFORMED")
    pairs = list(request.query_params.multi_items())
    if len(pairs) > len(_FIELDS) or any(key not in _FIELDS for key, _ in pairs):
        raise ApplicationError("REQUEST_MALFORMED")
    params = dict(pairs)
    if len(params) != len(pairs) or not {
            "resource_type", "resource_id", "version_id"}.issubset(params):
        raise ApplicationError("REQUEST_MALFORMED")
    return params


def _ref(ref: TraceVersionRef) -> dict[str, str | None]:
    if type(ref) is not TraceVersionRef:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "resource_type": ref.object_type,
        "resource_id": str(ref.object_id),
        "version_id": str(ref.version_id),
        "scope": ref.scope,
        "project_id": str(ref.project_id) if ref.project_id is not None else None,
    }


def create_trace_graph_router(*, sessions: SessionService,
                              origins: LoginOriginPolicy,
                              graphs: TracePublicGraphReadService) -> APIRouter:
    if any(value is None for value in (sessions, origins, graphs)):
        raise ValueError("Trace graph HTTP dependencies required")
    router = APIRouter()

    async def read(project_id: str, request: Request, direction: str) -> JSONResponse:
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
        params = _parameters(request)
        project = _uuid(project_id)
        resource_type = params["resource_type"]
        if not resource_type or len(resource_type) > 64 or not resource_type.isascii():
            raise ApplicationError("VALIDATION_FAILED")
        relation = params.get("relation_type")
        if relation == "":
            raise ApplicationError("VALIDATION_FAILED")
        cursor = params.get("cursor")
        if cursor is not None and (not cursor or len(cursor) > 2051):
            raise ApplicationError("VALIDATION_FAILED")
        trace_id = _uuid(request.state.trace_id)
        query = TracePublicGraphQuery(
            token, trace_id, project,
            TraceResourceVersionRef(
                resource_type, _uuid(params["resource_id"]),
                _uuid(params["version_id"])),
            direction, relation,
            _number(params.get("max_depth", "3"), 10),
            _number(params.get("max_nodes", "100"), 500),
            _number(params.get("page_size", "100"), 100), cursor)
        try:
            page = await run_in_threadpool(graphs.query_page, query)
        except TraceQueryError as error:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
                "TRACE_CURSOR_STALE": "CONFLICT_VERSION",
            }.get(error.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(page) is not TraceGraphPage
                or type(page.root) is not TraceVersionRef
                or page.root.object_type != resource_type
                or page.root.object_id != query.root.resource_id
                or page.root.version_id != query.root.version_id
                or page.root.scope == "PROJECT" and page.root.project_id != project
                or type(page.truncated) is not bool
                or type(page.nodes) is not tuple or type(page.links) is not tuple
                or len(page.nodes) > query.max_nodes
                or not page.nodes or page.nodes[0] != page.root
                or any(type(node) is not TraceVersionRef
                       or node.scope == "PROJECT" and node.project_id != project
                       for node in page.nodes)
                or any(type(link) is not TraceAdjacency
                       or type(link.trace_link_id) is not uuid.UUID
                       or link.trace_link_id.int == 0
                       or type(link.edge) is not TraceEdgeShape
                       or link.edge.scope != "PROJECT"
                       or link.edge.project_id != project
                       or link.edge.source not in page.nodes
                       or link.edge.target not in page.nodes
                       for link in page.links)
                or page.next_cursor is not None
                and (type(page.next_cursor) is not str
                     or len(page.next_cursor) > 2051)):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = {
            "root": _ref(page.root),
            "nodes": [_ref(node) for node in page.nodes],
            "links": [{
                "trace_link_id": str(link.trace_link_id),
                "source": _ref(link.edge.source),
                "target": _ref(link.edge.target),
                "relation_type": link.edge.relation_type,
            } for link in page.links],
            "next_cursor": page.next_cursor,
            "truncated": page.truncated,
        }
        return JSONResponse(
            {"data": data, "trace_id": str(trace_id)},
            headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/trace-graph:upstream",
                operation_id="TRACE_GRAPH_UPSTREAM")
    async def upstream(project_id: str, request: Request) -> JSONResponse:
        return await read(project_id, request, "UPSTREAM")

    @router.get("/api/v1/projects/{project_id}/trace-graph:downstream",
                operation_id="TRACE_GRAPH_DOWNSTREAM")
    async def downstream(project_id: str, request: Request) -> JSONResponse:
        return await read(project_id, request, "DOWNSTREAM")

    return router
