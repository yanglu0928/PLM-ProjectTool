"""Opt-in HTTP boundary for the five GLOBAL Capability read operations."""

from __future__ import annotations

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
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselinePage, CapabilityBaselineView, CapabilityItemPage,
    CapabilityItemView, CapabilityReadError, CapabilityReadQuery,
    CapabilityReadService, CapabilityVersionPage, CapabilityVersionView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

from .commands import _baseline_data, _canonical_uuid, _version_data
from .read_cursor import CapabilityBaselineCursorCodec, CapabilityChildCursorCodec


_PAGE_SIZE = re.compile(r"[1-9][0-9]{0,2}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_SOURCE = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_ETAG = re.compile(r'"v(0|[1-9][0-9]*)"\Z', re.ASCII)
_BASELINE_STATES = frozenset({"ACTIVE", "ARCHIVED"})
_VERSION_STATES = frozenset({
    "DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "SUPERSEDED", "RESTRICTED",
})
_ITEM_STATES = frozenset({"AVAILABLE", "WITHDRAWN"})
_VISIBILITIES = frozenset({"ADMIN_HISTORY", "CURRENT_APPROVED"})


def _error(exc: CapabilityReadError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
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
    raw_size = params.get("page_size", "50")
    if _PAGE_SIZE.fullmatch(raw_size) is None or int(raw_size) > 200:
        raise ApplicationError("VALIDATION_FAILED")
    return int(raw_size), params.get("cursor")


def _baseline(view: CapabilityBaselineView) -> dict[str, object]:
    if (type(view) is not CapabilityBaselineView
            or type(view.baseline_id) is not uuid.UUID or view.baseline_id.int == 0
            or type(view.baseline_code) is not str or not view.baseline_code
            or type(view.name) is not str or not view.name
            or view.description is not None and type(view.description) is not str
            or view.state not in _BASELINE_STATES
            or type(view.source_collection_ref) is not str
            or _SOURCE.fullmatch(view.source_collection_ref) is None
            or view.current_approved_version_ref is not None and (
                type(view.current_approved_version_ref) is not uuid.UUID
                or view.current_approved_version_ref.int == 0)
            or type(view.etag) is not str or _ETAG.fullmatch(view.etag) is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return _baseline_data(view)


def _version(view: CapabilityVersionView) -> dict[str, object]:
    references = (view.supersedes_version_ref, view.review_ref, view.review_round_ref)
    if (type(view) is not CapabilityVersionView
            or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                view.baseline_version_id, view.baseline_id))
            or type(view.version_no) is not int or view.version_no <= 0
            or view.state not in _VERSION_STATES
            or type(view.source_collection_ref) is not str
            or _SOURCE.fullmatch(view.source_collection_ref) is None
            or type(view.content_fingerprint) is not str
            or _HASH.fullmatch(view.content_fingerprint) is None
            or any(type(value) is not int or value < 0 for value in (
                view.declared_item_count, view.declared_document_ref_count,
                view.declared_evidence_ref_count))
            or any(value is not None and (
                type(value) is not uuid.UUID or value.int == 0) for value in references)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return _version_data(view)


def _item(view: CapabilityItemView) -> dict[str, object]:
    ids = (view.capability_item_id, view.baseline_version_id, view.baseline_id)
    texts = (
        view.capability_code, view.domain_name, view.module_name,
        view.feature_name, view.name, view.description, view.boundary_text,
    )
    if (type(view) is not CapabilityItemView
            or any(type(value) is not uuid.UUID or value.int == 0 for value in ids)
            or type(view.ordinal) is not int or view.ordinal < 0
            or any(type(value) is not str for value in texts)
            or any(type(values) is not tuple or any(type(value) is not str for value in values)
                   for values in (view.prerequisites, view.interface_refs))
            or view.state not in _ITEM_STATES
            or any(type(values) is not tuple or any(
                type(value) is not uuid.UUID or value.int == 0 for value in values)
                for values in (view.document_version_refs, view.evidence_refs))):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "capability_item_id": str(view.capability_item_id),
        "baseline_version_id": str(view.baseline_version_id),
        "baseline_id": str(view.baseline_id), "ordinal": view.ordinal,
        "capability_code": view.capability_code,
        "domain_name": view.domain_name, "module_name": view.module_name,
        "feature_name": view.feature_name, "name": view.name,
        "description": view.description, "boundary": view.boundary_text,
        "prerequisites": list(view.prerequisites),
        "interface_refs": list(view.interface_refs), "state": view.state,
        "document_version_refs": [str(value) for value in view.document_version_refs],
        "evidence_refs": [str(value) for value in view.evidence_refs],
    }


def _page_shape(page: object, expected: type, item_type: type,
                page_size: int, visibility: str) -> None:
    if (type(page) is not expected or page.visibility != visibility
            or visibility not in _VISIBILITIES
            or type(page.items) is not tuple or len(page.items) > page_size
            or any(type(item) is not item_type for item in page.items)
            or type(page.has_more) is not bool
            or page.has_more != (page.next_position is not None)
            or page.has_more and not page.items):
        raise ApplicationError("SYSTEM_UNAVAILABLE")


def create_capability_read_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    reads: CapabilityReadService, baseline_cursors: CapabilityBaselineCursorCodec,
    child_cursors: CapabilityChildCursorCodec,
) -> APIRouter:
    if any(value is None for value in (
            sessions, origins, reads, baseline_cursors, child_cursors)):
        raise ValueError("Capability read HTTP dependencies are required")
    router = APIRouter()

    @router.get("/api/v1/global/capability-baselines")
    async def list_baselines(request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        size, cursor = _page_query(request)
        after, expected = (None, None)
        if cursor is not None:
            after, expected = baseline_cursors.decode_bound(
                cursor, session_token=token, page_size=size,
            )
        try:
            page = await run_in_threadpool(
                reads.list_baselines,
                CapabilityReadQuery(token, trace, expected),
                page_size=size, after_id=after,
            )
        except CapabilityReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        visibility = expected or page.visibility
        _page_shape(page, CapabilityBaselinePage, CapabilityBaselineView, size, visibility)
        if page.has_more and page.next_position != page.items[-1].baseline_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (baseline_cursors.encode(
            session_token=token, page_size=size, visibility=visibility,
            baseline_id=page.next_position,
        ) if page.has_more else None)
        return JSONResponse({"data": {
            "items": [_baseline(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/global/capability-baselines/{baseline_id}")
    async def get_baseline(baseline_id: str, request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        identity = _canonical_uuid(baseline_id)
        try:
            view = await run_in_threadpool(
                reads.get_baseline, CapabilityReadQuery(token, trace), identity,
            )
        except CapabilityReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        data = _baseline(view)
        return JSONResponse(
            {"data": data, "trace_id": str(trace)},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.get("/api/v1/global/capability-baselines/{baseline_id}/versions")
    async def list_versions(baseline_id: str, request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        identity = _canonical_uuid(baseline_id)
        size, cursor = _page_query(request)
        after, expected = (None, None)
        if cursor is not None:
            after, expected = child_cursors.decode_bound(
                cursor, family="capability-versions", scope_id=identity,
                session_token=token, page_size=size,
            )
        try:
            page = await run_in_threadpool(
                reads.list_versions, CapabilityReadQuery(token, trace, expected),
                baseline_id=identity, page_size=size, after_version_no=after,
            )
        except CapabilityReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        visibility = expected or page.visibility
        _page_shape(page, CapabilityVersionPage, CapabilityVersionView, size, visibility)
        if any(item.baseline_id != identity for item in page.items):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        if page.has_more and page.next_position != page.items[-1].version_no:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (child_cursors.encode(
            family="capability-versions", scope_id=identity,
            session_token=token, page_size=size, visibility=visibility,
            position=page.next_position,
        ) if page.has_more else None)
        return JSONResponse({"data": {
            "items": [_version(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    @router.get(
        "/api/v1/global/capability-baselines/{baseline_id}/versions/"
        "{baseline_version_id}"
    )
    async def get_version(baseline_id: str, baseline_version_id: str,
                          request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        baseline = _canonical_uuid(baseline_id)
        version = _canonical_uuid(baseline_version_id)
        try:
            view = await run_in_threadpool(
                reads.get_version, CapabilityReadQuery(token, trace),
                baseline_id=baseline, baseline_version_id=version,
            )
        except CapabilityReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.baseline_id != baseline or view.baseline_version_id != version:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _version(view), "trace_id": str(trace)},
            headers={"Cache-Control": "no-store"},
        )

    @router.get(
        "/api/v1/global/capability-baselines/{baseline_id}/versions/"
        "{baseline_version_id}/items"
    )
    async def list_items(baseline_id: str, baseline_version_id: str,
                         request: Request) -> JSONResponse:
        token, trace = await _query(request, sessions, origins)
        baseline = _canonical_uuid(baseline_id)
        version = _canonical_uuid(baseline_version_id)
        size, cursor = _page_query(request)
        after, expected = (None, None)
        if cursor is not None:
            after, expected = child_cursors.decode_bound(
                cursor, family="capability-items", scope_id=version,
                session_token=token, page_size=size,
            )
        try:
            page = await run_in_threadpool(
                reads.list_items, CapabilityReadQuery(token, trace, expected),
                baseline_id=baseline, baseline_version_id=version,
                page_size=size, after_ordinal=after,
            )
        except CapabilityReadError as exc:
            raise _error(exc) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        visibility = expected or page.visibility
        _page_shape(page, CapabilityItemPage, CapabilityItemView, size, visibility)
        if any(item.baseline_id != baseline
               or item.baseline_version_id != version for item in page.items):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        if page.has_more and page.next_position != page.items[-1].ordinal:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        next_cursor = (child_cursors.encode(
            family="capability-items", scope_id=version,
            session_token=token, page_size=size, visibility=visibility,
            position=page.next_position,
        ) if page.has_more else None)
        return JSONResponse({"data": {
            "items": [_item(item) for item in page.items],
            "next_cursor": next_cursor, "has_more": page.has_more,
        }, "trace_id": str(trace)}, headers={"Cache-Control": "no-store"})

    return router
