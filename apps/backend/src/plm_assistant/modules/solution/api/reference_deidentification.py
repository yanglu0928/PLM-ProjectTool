"""Opt-in GLOBAL source preview and explicit administrator attestation HTTP API."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.solution.api.reference_create import _ids, _read_body, _uuid
from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ConfirmReferenceDeidentification, ReferenceDeidentificationConfirmError,
    ReferenceDeidentificationConfirmService, ReferenceDeidentificationConfirmationView,
)
from plm_assistant.modules.solution.application.lookup_reference_deidentification_operation import (
    LookupReferenceDeidentificationOperation, ReferenceDeidentificationLookupError,
    ReferenceDeidentificationOperationLookupService,
    ReferenceDeidentificationOperationStatus,
)
from plm_assistant.modules.solution.application.preview_reference_deidentification import (
    PreviewReferenceDeidentification, ReferenceDeidentificationPreviewError,
    ReferenceDeidentificationPreviewService, ReferenceDeidentificationPreviewView,
)
from plm_assistant.modules.solution.application.reference_source_qualification import ReferenceSourceRequest
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    ReferenceDeidentificationRevokeError, ReferenceDeidentificationRevokeService,
    RevokeReferenceDeidentification, RevocationView,
)


_SOURCE_FIELDS = frozenset({
    "document_version_ids", "evidence_ids", "source_project_class",
    "deidentification_class", "applicability",
})
_CONFIRM_FIELDS = _SOURCE_FIELDS | frozenset({
    "expected_source_fingerprint", "attestation_statement", "expires_at",
})
_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_REASONS = frozenset({"SOURCE_EXPOSED", "SCOPE_CHANGED", "ADMIN_REVIEW"})


def _failure(code: str) -> ApplicationError:
    return ApplicationError({
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "SOLUTION_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "SOLUTION_CONFLICT": "CONFLICT_STATE",
        "SOURCE_SNAPSHOT_CHANGED": "SOURCE_SNAPSHOT_CHANGED",
    }.get(code, "SYSTEM_UNAVAILABLE"))


def _instant(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source(body: dict[str, object], token: bytes, trace: uuid.UUID) -> ReferenceSourceRequest:
    docs, evidence = _ids(body["document_version_ids"]), _ids(body["evidence_ids"])
    source_class, deidentification_class = (
        body["source_project_class"], body["deidentification_class"])
    if (not 1 <= len(docs) <= 100 or len(evidence) > 500
            or type(source_class) is not str
            or not 1 <= len(source_class) <= 128 or source_class != source_class.strip()
            or type(deidentification_class) is not str
            or not 1 <= len(deidentification_class) <= 128
            or deidentification_class != deidentification_class.strip()
            or type(body["applicability"]) is not dict):
        raise ApplicationError("VALIDATION_FAILED")
    return ReferenceSourceRequest(
        token, trace, "GLOBAL", None, docs, evidence,
        source_class, deidentification_class, body["applicability"],
    )


def _preview_data(view: ReferenceDeidentificationPreviewView,
                  sources: ReferenceSourceRequest) -> dict[str, object]:
    if (type(view) is not ReferenceDeidentificationPreviewView
            or type(view.source_fingerprint) is not bytes
            or len(view.source_fingerprint) != 32
            or type(view.document_refs) is not tuple or not view.document_refs
            or type(view.evidence_ids) is not tuple):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    from plm_assistant.modules.solution.application.preview_reference_deidentification import PreviewDocumentRef
    if any(type(item) is not PreviewDocumentRef
           or type(item.document_id) is not uuid.UUID or item.document_id.int == 0
           or type(item.document_version_id) is not uuid.UUID
           or item.document_version_id.int == 0 for item in view.document_refs):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    if any(type(item) is not uuid.UUID or item.int == 0 for item in view.evidence_ids):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    if (tuple(item.document_version_id for item in view.document_refs)
            != sources.document_version_ids or view.evidence_ids != sources.evidence_ids):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "source_fingerprint": view.source_fingerprint.hex(),
        "document_refs": [{"document_id": str(item.document_id),
                           "document_version_id": str(item.document_version_id)}
                          for item in view.document_refs],
        "evidence_ids": [str(item) for item in view.evidence_ids],
        "previewed_at": _instant(view.previewed_at),
    }


def _confirm_data(view: ReferenceDeidentificationConfirmationView) -> dict[str, object]:
    if (type(view) is not ReferenceDeidentificationConfirmationView
            or type(view.confirmation_id) is not uuid.UUID or view.confirmation_id.int == 0
            or type(view.source_fingerprint) is not bytes or len(view.source_fingerprint) != 32
            or type(view.confirmed_by) is not uuid.UUID or view.confirmed_by.int == 0
            or type(view.trace_id) is not uuid.UUID or view.trace_id.int == 0):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "confirmation_id": str(view.confirmation_id),
        "source_fingerprint": view.source_fingerprint.hex(),
        "confirmed_by": str(view.confirmed_by),
        "confirmed_at": _instant(view.confirmed_at),
        "expires_at": _instant(view.expires_at),
        "trace_id": str(view.trace_id),
    }


def create_reference_deidentification_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    previews: ReferenceDeidentificationPreviewService,
    confirmations: ReferenceDeidentificationConfirmService,
    revocations: ReferenceDeidentificationRevokeService,
    lookups: ReferenceDeidentificationOperationLookupService | None = None,
) -> APIRouter:
    if any(item is None for item in (sessions, origins, previews, confirmations, revocations)):
        raise ValueError("GLOBAL Reference attestation HTTP dependencies required")
    router = APIRouter()

    async def admission(request: Request) -> tuple[tuple[tuple[bytes, bytes], ...], bytes, bytes, uuid.UUID]:
        headers = tuple(request.scope.get("headers", ()))
        try:
            origins.require_trusted(headers)
        except LoginOriginError:
            raise ApplicationError("AUTH_CSRF_INVALID") from None
        token, csrf = _session_cookie(headers), _csrf_header(headers)
        try:
            await run_in_threadpool(sessions.validate, token, csrf_token=csrf, require_csrf=True)
        except SessionError as error:
            raise _session_failure(error) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        return headers, token, csrf, uuid.UUID(request.state.trace_id)

    @router.post("/api/v1/global/reference-deidentification-confirmations:preview")
    async def preview(request: Request) -> JSONResponse:
        headers, token, csrf, trace = await admission(request)
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != _SOURCE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        sources = _source(body, token, trace)
        try:
            view = await run_in_threadpool(previews.preview,
                PreviewReferenceDeidentification(sources, csrf))
        except ReferenceDeidentificationPreviewError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({"data": _preview_data(view, sources), "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/global/reference-deidentification-confirmations")
    async def confirm(request: Request) -> JSONResponse:
        headers, token, csrf, trace = await admission(request)
        key = _idempotency_header(headers)
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != _CONFIRM_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        fingerprint = body["expected_source_fingerprint"]
        expires_at = body["expires_at"]
        if (type(fingerprint) is not str or _FINGERPRINT.fullmatch(fingerprint) is None
                or type(expires_at) is not str or not expires_at.endswith("Z")
                or body["attestation_statement"] != "I_VERIFIED_DEIDENTIFICATION"):
            raise ApplicationError("VALIDATION_FAILED")
        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            raise ApplicationError("VALIDATION_FAILED") from None
        if expiry.tzinfo is None or expiry.utcoffset() != timezone.utc.utcoffset(None):
            raise ApplicationError("VALIDATION_FAILED")
        sources = _source(body, token, trace)
        try:
            view = await run_in_threadpool(confirmations.confirm,
                ConfirmReferenceDeidentification(
                    sources, csrf, expiry,
                    body["attestation_statement"], key, bytes.fromhex(fingerprint)))
        except ReferenceDeidentificationConfirmError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse({"data": _confirm_data(view), "trace_id": str(trace)},
                            status_code=201, headers={"Cache-Control": "no-store"})

    @router.post("/api/v1/global/reference-deidentification-confirmations/{confirmation_id}:revoke")
    async def revoke(confirmation_id: str, request: Request) -> JSONResponse:
        headers, token, csrf, trace = await admission(request)
        key, target = _idempotency_header(headers), _uuid(confirmation_id)
        body = await _read_body(request, headers)
        if type(body) is not dict or set(body) != {"reason_code"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["reason_code"]) is not str or body["reason_code"] not in _REASONS:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            view = await run_in_threadpool(revocations.revoke,
                RevokeReferenceDeidentification(target, token, csrf, trace,
                                                 body["reason_code"], key))
        except ReferenceDeidentificationRevokeError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not RevocationView or view.confirmation_id != target):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {"confirmation_id": str(target),
                                       "revoked_at": _instant(view.revoked_at),
                                       "trace_id": str(trace)},
                             "trace_id": str(trace)},
                            headers={"Cache-Control": "no-store"})

    if lookups is not None:
        @router.post("/api/v1/global/reference-deidentification-confirmations:lookup-operation")
        async def lookup(request: Request) -> JSONResponse:
            headers, token, csrf, trace = await admission(request)
            body = await _read_body(request, headers)
            if type(body) is not dict or set(body) != {"operation_kind", "operation_key"}:
                raise ApplicationError("REQUEST_MALFORMED")
            if (type(body["operation_kind"]) is not str
                    or body["operation_kind"] not in ("CONFIRM", "REVOKE")
                    or type(body["operation_key"]) is not str):
                raise ApplicationError("VALIDATION_FAILED")
            try:
                result = await run_in_threadpool(lookups.lookup,
                    LookupReferenceDeidentificationOperation(
                        token, csrf, trace, body["operation_kind"], body["operation_key"]))
            except ReferenceDeidentificationLookupError as error:
                raise _failure(error.code) from None
            except Exception:
                raise ApplicationError("SYSTEM_UNAVAILABLE") from None
            if type(result) is not ReferenceDeidentificationOperationStatus:
                raise ApplicationError("SYSTEM_UNAVAILABLE")
            if (result.status == "UNCONFIRMED" and result.confirmation_id is None
                    and result.first_status_code is None and result.current_state is None):
                data = {"status": "UNCONFIRMED"}
            elif (result.status == "COMPLETED"
                    and type(result.confirmation_id) is uuid.UUID
                    and result.confirmation_id.int != 0
                    and result.first_status_code in (200, 201)
                    and result.current_state in (
                        "CONFIRMED", "REVOKED", "EXPIRED", "SUPERSEDED")):
                data = {"status": "COMPLETED",
                        "confirmation_id": str(result.confirmation_id),
                        "first_status_code": result.first_status_code,
                        "current_state": result.current_state}
            else:
                raise ApplicationError("SYSTEM_UNAVAILABLE")
            return JSONResponse({"data": data, "trace_id": str(trace)},
                                headers={"Cache-Control": "no-store"})

    return router
