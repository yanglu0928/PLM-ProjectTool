"""Opt-in Evidence candidate create HTTP; no default or production mounting."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.document.application.read_documents import DocumentReadError
from plm_assistant.modules.evidence.application.create_access import EvidenceCreateAccessError
from plm_assistant.modules.evidence.application.create_evidence import (
    CreateEvidence, CreatedEvidence, EvidenceCreateError, EvidenceCreateService,
)
from plm_assistant.modules.evidence.application.document_source_proof import EvidenceSourceError
from plm_assistant.modules.evidence.application.parsed_node_proof import EvidenceNodeProofError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.project.api.create_project import _canonical_uuid, _read_json


_FIELDS = frozenset({"document_id", "document_version_id", "locator",
                     "display_label", "display_excerpt", "parse_record_id"})


def _command(body: object, *, actor_id: uuid.UUID, token: bytes, csrf: bytes,
             trace_id: uuid.UUID, scope: str,
             project_id: uuid.UUID | None) -> CreateEvidence:
    if (type(body) is not dict
            or not {"document_id", "document_version_id", "locator", "display_label"}.issubset(body)
            or set(body) - _FIELDS):
        raise ApplicationError("REQUEST_MALFORMED")
    if type(body["locator"]) is not dict or type(body["display_label"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    if "display_excerpt" in body and body["display_excerpt"] is not None and type(body["display_excerpt"]) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    return CreateEvidence(
        actor_id, token, csrf, trace_id, scope, project_id,
        _canonical_uuid(body["document_id"]),
        _canonical_uuid(body["document_version_id"]),
        body["locator"], body["display_label"], body.get("display_excerpt"),
        _canonical_uuid(body["parse_record_id"]) if body.get("parse_record_id") is not None else None,
    )


def _error(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "EVIDENCE_LOCATOR_INVALID": "EVIDENCE_LOCATOR_INVALID",
        "EVIDENCE_RESOLUTION_UNAVAILABLE": "EVIDENCE_LOCATOR_INVALID",
        "EVIDENCE_FINGERPRINT_MISMATCH": "EVIDENCE_FINGERPRINT_MISMATCH",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "FILE_INTEGRITY_MISMATCH": "EVIDENCE_FINGERPRINT_MISMATCH",
        "DOCUMENT_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
        "EVIDENCE_UNAVAILABLE": "SYSTEM_UNAVAILABLE",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def create_evidence_create_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    service_factory: Callable[[bytes, bytes], EvidenceCreateService],
) -> APIRouter:
    if any(item is None for item in (sessions, origins, service_factory)):
        raise ValueError("Evidence HTTP dependencies are required")
    router = APIRouter()

    async def _create(request: Request, *, scope: str,
                      project_id: uuid.UUID | None) -> JSONResponse:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf, key = (_session_cookie(headers), _csrf_header(headers),
                            _idempotency_header(headers))
        try:
            principal = await run_in_threadpool(
                sessions.validate, token, csrf_token=csrf, require_csrf=True,
            )
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        actor_id = getattr(principal, "user_id", None)
        if type(actor_id) is not uuid.UUID or actor_id.int == 0:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        if scope == "PROJECT" and (type(project_id) is not uuid.UUID or project_id.int == 0):
            raise ApplicationError("RESOURCE_NOT_FOUND")
        body = await _read_json(request, headers)
        command = _command(body, actor_id=actor_id, token=token, csrf=csrf,
                           trace_id=uuid.UUID(request.state.trace_id),
                           scope=scope, project_id=project_id)
        try:
            service = service_factory(token, csrf)
            view = await run_in_threadpool(service.create, command, idempotency_key=key)
        except (EvidenceCreateError, EvidenceCreateAccessError, EvidenceSourceError,
                EvidenceNodeProofError, DocumentReadError) as error:
            raise _error(error.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not CreatedEvidence or view.scope != scope
                or view.project_id != project_id or view.eligibility_state != "CANDIDATE"
                or view.etag != '"v0"' or type(view.content_fingerprint) is not bytes
                or len(view.content_fingerprint) != 32
                or view.created_at.tzinfo is None):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        base = "/api/v1/global" if scope == "GLOBAL" else f"/api/v1/projects/{project_id}"
        return JSONResponse({"data": {
            "evidence_id": str(view.evidence_id),
            "document_id": str(view.document_id),
            "document_version_id": str(view.document_version_id),
            "locator": view.locator,
            "content_fingerprint": view.content_fingerprint.hex(),
            "display_label": view.display_label,
            "display_excerpt": view.display_excerpt,
            "eligibility_state": view.eligibility_state,
            "created_at": view.created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "etag": view.etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": view.etag,
            "Location": f"{base}/evidence/{view.evidence_id}",
        })

    @router.post("/api/v1/global/evidence")
    async def create_global(request: Request) -> JSONResponse:
        return await _create(request, scope="GLOBAL", project_id=None)

    @router.post("/api/v1/projects/{project_id}/evidence")
    async def create_project(project_id: uuid.UUID, request: Request) -> JSONResponse:
        return await _create(request, scope="PROJECT", project_id=project_id)

    return router
