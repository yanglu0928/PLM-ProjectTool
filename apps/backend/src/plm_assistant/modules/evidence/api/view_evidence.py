"""Opt-in fixed Evidence Viewer descriptor over authorized Document content URL."""

from __future__ import annotations

import re
import uuid
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.evidence.api.read_evidence import _query
from plm_assistant.modules.evidence.application.read_evidence import EvidenceReadQuery
from plm_assistant.modules.evidence.application.view_evidence import (
    EvidenceViewerDescriptor, EvidenceViewerError,
)
from plm_assistant.modules.evidence.domain.locator import (
    EvidenceLocatorError, validate_evidence_locator,
)
from plm_assistant.modules.platform.application.errors import ApplicationError

_MIME = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+\Z", re.ASCII)


class EvidenceViewerPort(Protocol):
    def view(self, query: EvidenceReadQuery,
             evidence_id: uuid.UUID) -> EvidenceViewerDescriptor: ...


def _error(error: EvidenceViewerError) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "EVIDENCE_RESOLUTION_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
        "EVIDENCE_FINGERPRINT_MISMATCH": "EVIDENCE_FINGERPRINT_MISMATCH",
    }.get(error.code, "SYSTEM_UNAVAILABLE"))


def _public(view: EvidenceViewerDescriptor, *, scope: str,
            project_id: uuid.UUID | None, evidence_id: uuid.UUID) -> dict[str, object]:
    if (type(view) is not EvidenceViewerDescriptor
            or view.evidence_id != evidence_id or view.scope != scope
            or view.project_id != project_id
            or type(view.document_id) is not uuid.UUID or view.document_id.int == 0
            or type(view.document_version_id) is not uuid.UUID
            or view.document_version_id.int == 0
            or type(view.version_no) is not int or view.version_no <= 0
            or type(view.size_bytes) is not int or not 0 <= view.size_bytes <= 100_000_000
            or type(view.detected_mime) is not str or _MIME.fullmatch(view.detected_mime) is None
            or view.precision not in ("DOCUMENT", "PARSED_NODE")
            or type(view.display_label) is not str or not 1 <= len(view.display_label) <= 255
            or view.short_preview is not None and (
                type(view.short_preview) is not str or len(view.short_preview) > 500)):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    try:
        locator = validate_evidence_locator(view.locator)
    except EvidenceLocatorError:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if locator != view.locator:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    base = (f"/api/v1/projects/{project_id}" if scope == "PROJECT"
            else "/api/v1/global")
    return {
        "evidence_id": str(view.evidence_id),
        "document_id": str(view.document_id),
        "document_version_id": str(view.document_version_id),
        "document_version_no": view.version_no,
        "detected_mime": view.detected_mime,
        "size_bytes": view.size_bytes,
        "locator": locator,
        "precision": view.precision,
        "display_label": view.display_label,
        "short_preview": view.short_preview,
        "content_url": (
            f"{base}/documents/{view.document_id}/versions/"
            f"{view.document_version_id}/content"
        ),
    }


def create_evidence_viewer_router(*, sessions: SessionService,
                                  origins: LoginOriginPolicy,
                                  viewer: EvidenceViewerPort) -> APIRouter:
    if any(item is None for item in (sessions, origins, viewer)):
        raise ValueError("Evidence Viewer dependencies required")
    router = APIRouter()

    async def get_for(request: Request, *, scope: str, project_id: uuid.UUID | None,
                      evidence_id: uuid.UUID) -> JSONResponse:
        query = await _query(request, sessions=sessions, origins=origins,
                             scope=scope, project_id=project_id)
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            descriptor = await run_in_threadpool(viewer.view, query, evidence_id)
        except EvidenceViewerError as error:
            raise _error(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({"data": _public(descriptor, scope=scope, project_id=project_id,
                                              evidence_id=evidence_id),
                             "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store"})

    @router.get("/api/v1/projects/{project_id}/evidence/{evidence_id}/viewer")
    async def project_viewer(project_id: uuid.UUID, evidence_id: uuid.UUID,
                             request: Request) -> JSONResponse:
        return await get_for(request, scope="PROJECT", project_id=project_id,
                             evidence_id=evidence_id)

    @router.get("/api/v1/global/evidence/{evidence_id}/viewer")
    async def global_viewer(evidence_id: uuid.UUID, request: Request) -> JSONResponse:
        return await get_for(request, scope="GLOBAL", project_id=None,
                             evidence_id=evidence_id)

    return router
