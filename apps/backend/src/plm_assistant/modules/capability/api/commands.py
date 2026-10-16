"""Opt-in HTTP boundary for the six ordinary GLOBAL Capability commands."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import (
    _csrf_header, _idempotency_header, _session_cookie, _session_failure,
)
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.capability.application.change_state import (
    ArchiveCapabilityBaseline, CapabilityStateError, CapabilityStateService,
    PatchCapabilityBaseline, RestrictCapabilityVersion, RestrictedCapabilityVersion,
)
from plm_assistant.modules.capability.application.create_baseline import (
    CapabilityBaselineCreateError, CapabilityBaselineCreateService,
    CapabilityBaselineInitialView, CreateCapabilityBaseline,
)
from plm_assistant.modules.capability.application.create_version import (
    CapabilityItemDraft, CapabilityVersionCreateError,
    CapabilityVersionCreateService, CreateCapabilityVersion,
    CreatedCapabilityVersion,
)
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityBaselineView, CapabilityVersionView,
)
from plm_assistant.modules.capability.application.source_validation import CapabilityDocumentRef
from plm_assistant.modules.capability.application.validate_version import (
    CapabilityVersionValidationError, CapabilityVersionValidationReport,
    CapabilityVersionValidationService, ValidateCapabilityVersion,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


_MAX_BODY = 2 * 1024 * 1024
_BASELINE_FIELDS = frozenset({"baseline_code", "name", "description", "source_documents"})
_PATCH_FIELDS = frozenset({"name", "description"})
_ITEM_FIELDS = frozenset({
    "stable_item_id", "capability_code", "domain_name", "module_name",
    "feature_name", "name", "description", "boundary", "prerequisites",
    "interface_refs", "document_refs", "evidence_refs", "item_state",
})
_DOCUMENT_FIELDS = frozenset({"document_id", "document_version_id"})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_json(request: Request, headers: tuple[tuple[bytes, bytes], ...]) -> object:
    values = [value for name, value in headers if name.lower() == b"content-type"]
    if (len(values) != 1 or values[0].strip().lower() not in (
            b"application/json", b"application/json; charset=utf-8")):
        raise ApplicationError("REQUEST_MALFORMED")
    raw = bytearray()
    try:
        async for chunk in request.stream():
            if len(raw) + len(chunk) > _MAX_BODY:
                raise ApplicationError("REQUEST_MALFORMED")
            raw.extend(chunk)
        try:
            return json.loads(
                raw.decode("utf-8", errors="strict"),
                object_pairs_hook=_unique_pairs, parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


async def _require_empty(request: Request) -> None:
    async for chunk in request.stream():
        if chunk:
            raise ApplicationError("REQUEST_MALFORMED")


def _canonical_uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.int == 0 or str(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _instant(value: datetime) -> str:
    if (type(value) is not datetime or value.tzinfo is None
            or value.utcoffset() is None):
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _security(request: Request, sessions: SessionService,
                    origins: LoginOriginPolicy) -> tuple[bytes, bytes]:
    headers = tuple(request.scope.get("headers", ()))
    try:
        origins.require_trusted(headers)
    except LoginOriginError:
        raise ApplicationError("AUTH_CSRF_INVALID") from None
    token, csrf = _session_cookie(headers), _csrf_header(headers)
    try:
        await run_in_threadpool(
            sessions.validate, token, csrf_token=csrf, require_csrf=True,
        )
    except SessionError as exc:
        raise _session_failure(exc) from None
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if request.url.query:
        raise ApplicationError("REQUEST_MALFORMED")
    return token, csrf


def _document(value: object) -> CapabilityDocumentRef:
    if type(value) is not dict or set(value) != _DOCUMENT_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    try:
        return CapabilityDocumentRef(
            _canonical_uuid(value["document_id"]),
            _canonical_uuid(value["document_version_id"]),
        )
    except ApplicationError:
        raise
    except Exception:
        raise ApplicationError("VALIDATION_FAILED") from None


def _documents(value: object) -> tuple[CapabilityDocumentRef, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_document(item) for item in value)


def _strings(value: object) -> tuple[str, ...]:
    if type(value) is not list or any(type(item) is not str for item in value):
        raise ApplicationError("VALIDATION_FAILED")
    return tuple(value)


def _item(value: object) -> CapabilityItemDraft:
    if type(value) is not dict or set(value) != _ITEM_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    string_fields = (
        "capability_code", "domain_name", "module_name", "feature_name",
        "name", "description", "boundary", "item_state",
    )
    if any(type(value[field]) is not str for field in string_fields):
        raise ApplicationError("VALIDATION_FAILED")
    evidence = value["evidence_refs"]
    if type(evidence) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return CapabilityItemDraft(
        capability_item_id=_canonical_uuid(value["stable_item_id"]),
        capability_code=value["capability_code"],
        domain_name=value["domain_name"], module_name=value["module_name"],
        feature_name=value["feature_name"], name=value["name"],
        description=value["description"], boundary_text=value["boundary"],
        prerequisites=_strings(value["prerequisites"]),
        interface_refs=_strings(value["interface_refs"]),
        item_state=value["item_state"],
        document_refs=_documents(value["document_refs"]),
        evidence_refs=tuple(_canonical_uuid(item) for item in evidence),
    )


def _items(value: object) -> tuple[CapabilityItemDraft, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_item(item) for item in value)


def _baseline_data(view: CapabilityBaselineView) -> dict[str, object]:
    if type(view) is not CapabilityBaselineView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "baseline_id": str(view.baseline_id), "baseline_code": view.baseline_code,
        "name": view.name, "description": view.description, "state": view.state,
        "source_collection_ref": view.source_collection_ref,
        "current_approved_version_ref": (
            None if view.current_approved_version_ref is None
            else str(view.current_approved_version_ref)
        ),
        "created_at": _instant(view.created_at), "updated_at": _instant(view.updated_at),
        "etag": view.etag,
    }


def _version_data(view: CapabilityVersionView) -> dict[str, object]:
    if type(view) is not CapabilityVersionView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "baseline_version_id": str(view.baseline_version_id),
        "baseline_id": str(view.baseline_id), "version_no": view.version_no,
        "state": view.state, "source_collection_ref": view.source_collection_ref,
        "content_fingerprint": view.content_fingerprint,
        "declared_item_count": view.declared_item_count,
        "declared_document_ref_count": view.declared_document_ref_count,
        "declared_evidence_ref_count": view.declared_evidence_ref_count,
        "supersedes_version_ref": (
            None if view.supersedes_version_ref is None else str(view.supersedes_version_ref)
        ),
        "review_ref": None if view.review_ref is None else str(view.review_ref),
        "review_round_ref": (
            None if view.review_round_ref is None else str(view.review_round_ref)
        ),
        "created_at": _instant(view.created_at),
    }


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "CAPABILITY_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CAPABILITY_STATE_CONFLICT": "CONFLICT_STATE",
        "CAPABILITY_SOURCE_CONFLICT": "CONFLICT_STATE",
        "CAPABILITY_SOURCE_UNAVAILABLE": "VALIDATION_FAILED",
        "CAPABILITY_EVIDENCE_UNAVAILABLE": "CAPABILITY_EVIDENCE_REQUIRED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def create_capability_command_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    baselines: CapabilityBaselineCreateService,
    versions: CapabilityVersionCreateService,
    validations: CapabilityVersionValidationService,
    states: CapabilityStateService,
) -> APIRouter:
    """Create one explicitly injected router; no production composition occurs here."""
    if any(value is None for value in (
            sessions, origins, baselines, versions, validations, states)):
        raise ValueError("Capability command HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/global/capability-baselines")
    async def create_baseline(request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _BASELINE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if (type(body["baseline_code"]) is not str or type(body["name"]) is not str
                or body["description"] is not None
                and type(body["description"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        command = CreateCapabilityBaseline(
            token, csrf, uuid.UUID(request.state.trace_id), body["baseline_code"],
            body["name"], body["description"], _documents(body["source_documents"]), key,
        )
        try:
            view = await run_in_threadpool(baselines.create, command)
        except CapabilityBaselineCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not CapabilityBaselineInitialView:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = f"/api/v1/global/capability-baselines/{view.baseline_id}"
        return JSONResponse({"data": {
            "baseline_id": str(view.baseline_id), "baseline_code": view.baseline_code,
            "name": view.name, "description": view.description,
            "state": view.baseline_state,
            "source_collection_ref": view.source_collection_ref,
            "current_approved_version_ref": None,
            "created_at": _instant(view.created_at), "etag": view.etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": view.etag, "Location": path,
        })

    @router.patch("/api/v1/global/capability-baselines/{baseline_id}")
    async def patch_baseline(baseline_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if (type(body) is not dict or not body or not set(body).issubset(_PATCH_FIELDS)):
            raise ApplicationError("REQUEST_MALFORMED")
        if ("name" in body and type(body["name"]) is not str
                or "description" in body and body["description"] is not None
                and type(body["description"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchCapabilityBaseline(
            token, csrf, uuid.UUID(request.state.trace_id), _canonical_uuid(baseline_id),
            expected, body.get("name"), body.get("description"),
            "name" in body, "description" in body,
        )
        try:
            view = await run_in_threadpool(states.patch, command)
        except CapabilityStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _baseline_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post("/api/v1/global/capability-baselines/{baseline_id}:archive")
    async def archive_baseline(baseline_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        await _require_empty(request)
        command = ArchiveCapabilityBaseline(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(baseline_id), expected, key,
        )
        try:
            view = await run_in_threadpool(states.archive, command)
        except CapabilityStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not CapabilityBaselineView or view.state != "ARCHIVED":
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _baseline_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post("/api/v1/global/capability-baselines/{baseline_id}/versions")
    async def create_version(baseline_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"items"}:
            raise ApplicationError("REQUEST_MALFORMED")
        command = CreateCapabilityVersion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(baseline_id), expected, _items(body["items"]), key,
        )
        try:
            view = await run_in_threadpool(versions.create, command)
        except CapabilityVersionCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not CreatedCapabilityVersion:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = (f"/api/v1/global/capability-baselines/{view.baseline_id}/versions/"
                f"{view.baseline_version_id}")
        etag = f'"v{view.lock_version}"'
        return JSONResponse({"data": {
            "baseline_version_id": str(view.baseline_version_id),
            "baseline_id": str(view.baseline_id), "version_no": view.version_no,
            "state": view.version_state,
            "source_collection_ref": view.source_collection_ref,
            "content_fingerprint": view.content_fingerprint.hex(),
            "supersedes_version_ref": (
                None if view.supersedes_version_ref is None
                else str(view.supersedes_version_ref)
            ),
            "created_at": _instant(view.created_at), "baseline_etag": etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": etag, "Location": path,
        })

    @router.post(
        "/api/v1/global/capability-baselines/{baseline_id}/versions/"
        "{baseline_version_id}:validate"
    )
    async def validate_version(baseline_id: str, baseline_version_id: str,
                               request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        await _require_empty(request)
        command = ValidateCapabilityVersion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(baseline_id), _canonical_uuid(baseline_version_id), key,
        )
        try:
            report = await run_in_threadpool(validations.validate, command)
        except CapabilityVersionValidationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(report) is not CapabilityVersionValidationReport:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            "audit_event_id": str(report.audit_event_id),
            "baseline_id": str(report.baseline_id),
            "baseline_version_id": str(report.baseline_version_id),
            "version_no": report.version_no, "state": report.version_state,
            "source_collection_ref": report.source_collection_ref,
            "content_fingerprint": report.content_fingerprint.hex(),
            "item_count": report.item_count,
            "document_ref_count": report.document_ref_count,
            "evidence_ref_count": report.evidence_ref_count,
            "valid": report.valid, "blocking_issues": list(report.issue_codes),
            "warnings": [], "checked_at": _instant(report.observed_at),
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    @router.post(
        "/api/v1/global/capability-baselines/{baseline_id}/versions/"
        "{baseline_version_id}:restrict"
    )
    async def restrict_version(baseline_id: str, baseline_version_id: str,
                               request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if (type(body) is not dict or set(body) != {"reason_code"}
                or type(body["reason_code"]) is not str):
            raise ApplicationError("REQUEST_MALFORMED")
        command = RestrictCapabilityVersion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(baseline_id), _canonical_uuid(baseline_version_id),
            body["reason_code"], key,
        )
        try:
            result = await run_in_threadpool(states.restrict, command)
        except CapabilityStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(result) is not RestrictedCapabilityVersion:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            **_version_data(result.version), "reason_code": result.reason_code,
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    return router
