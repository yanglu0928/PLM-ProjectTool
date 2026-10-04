"""Opt-in HTTP boundary for the five ordinary Handover analysis commands."""

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
from plm_assistant.modules.handover.application.change_analysis import (
    ArchiveHandoverAnalysis, HandoverAnalysisStateError,
    HandoverAnalysisStateService, PatchHandoverAnalysis,
)
from plm_assistant.modules.handover.application.create_analysis import (
    CreateHandoverAnalysis, HandoverAnalysisCreateError,
    HandoverAnalysisCreateService, HandoverAnalysisInitialView,
)
from plm_assistant.modules.handover.application.create_version import (
    CreateHandoverVersion, CreatedHandoverVersion,
    HandoverAnalysisItemDraft, HandoverCapabilityItemRef,
    HandoverItemOptionDraft, HandoverVersionCreateError,
    HandoverVersionCreateService,
)
from plm_assistant.modules.handover.application.read_analyses import HandoverAnalysisView
from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.handover.application.validate_version import (
    HandoverVersionValidationError, HandoverVersionValidationReport,
    HandoverVersionValidationService, ValidateHandoverVersion,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError


_MAX_BODY = 2 * 1024 * 1024
_ANALYSIS_FIELDS = frozenset({"analysis_purpose", "source_documents"})
_VERSION_FIELDS = frozenset({
    "source_documents", "capability_baseline_id",
    "capability_baseline_version_id", "items", "ai_task_refs",
})
_DOCUMENT_FIELDS = frozenset({"document_id", "document_version_id"})
_ITEM_FIELDS = frozenset({
    "analysis_item_id", "item_type", "title", "statement", "impact",
    "severity", "priority", "recommendation", "confirmation_question",
    "required_input_spec", "source_missing", "evidence_refs",
    "capability_refs", "options",
})
_OPTION_FIELDS = frozenset({"option_code", "label", "description"})


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
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
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


def _document(value: object) -> HandoverDocumentRef:
    if type(value) is not dict or set(value) != _DOCUMENT_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    try:
        return HandoverDocumentRef(
            _canonical_uuid(value["document_id"]),
            _canonical_uuid(value["document_version_id"]),
        )
    except ApplicationError:
        raise
    except Exception:
        raise ApplicationError("VALIDATION_FAILED") from None


def _documents(value: object) -> tuple[HandoverDocumentRef, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_document(item) for item in value)


def _uuid_list(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_canonical_uuid(item) for item in value)


def _option(value: object) -> HandoverItemOptionDraft:
    if type(value) is not dict or set(value) != _OPTION_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(value["option_code"]) is not str or type(value["label"]) is not str
            or value["description"] is not None
            and type(value["description"]) is not str):
        raise ApplicationError("VALIDATION_FAILED")
    return HandoverItemOptionDraft(
        value["option_code"], value["label"], value["description"],
    )


def _item(value: object) -> HandoverAnalysisItemDraft:
    if type(value) is not dict or set(value) != _ITEM_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    strings = ("item_type", "title", "statement", "impact", "severity", "priority")
    if (any(type(value[field]) is not str for field in strings)
            or value["recommendation"] is not None
            and type(value["recommendation"]) is not str
            or value["confirmation_question"] is not None
            and type(value["confirmation_question"]) is not str
            or type(value["required_input_spec"]) is not dict
            or type(value["source_missing"]) is not bool
            or type(value["options"]) is not list):
        raise ApplicationError("VALIDATION_FAILED")
    return HandoverAnalysisItemDraft(
        analysis_item_id=_canonical_uuid(value["analysis_item_id"]),
        item_type=value["item_type"], title=value["title"],
        statement=value["statement"], impact=value["impact"],
        severity=value["severity"], priority=value["priority"],
        recommendation=value["recommendation"],
        confirmation_question=value["confirmation_question"],
        required_input_spec=value["required_input_spec"],
        source_missing=value["source_missing"],
        evidence_refs=_uuid_list(value["evidence_refs"]),
        capability_refs=tuple(
            HandoverCapabilityItemRef(ref) for ref in _uuid_list(value["capability_refs"])
        ),
        options=tuple(_option(item) for item in value["options"]),
    )


def _items(value: object) -> tuple[HandoverAnalysisItemDraft, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_item(item) for item in value)


def _analysis_data(view: HandoverAnalysisView) -> dict[str, object]:
    if type(view) is not HandoverAnalysisView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "handover_analysis_id": str(view.handover_analysis_id),
        "project_id": str(view.project_id), "analysis_purpose": view.analysis_purpose,
        "source_set_ref": view.source_set_ref, "state": view.analysis_state,
        "current_approved_version_ref": (
            None if view.current_approved_version_ref is None
            else str(view.current_approved_version_ref)
        ),
        "created_at": _instant(view.created_at), "updated_at": _instant(view.updated_at),
        "etag": view.etag,
    }


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "HANDOVER_STATE_CONFLICT": "CONFLICT_STATE",
        "HANDOVER_SOURCE_CONFLICT": "HANDOVER_SOURCE_REQUIRED",
        "HANDOVER_SOURCE_UNAVAILABLE": "HANDOVER_SOURCE_REQUIRED",
        "HANDOVER_EVIDENCE_UNAVAILABLE": "HANDOVER_ITEM_INCOMPLETE",
        "HANDOVER_CAPABILITY_UNAVAILABLE": "VALIDATION_FAILED",
        "HANDOVER_AI_PROVENANCE_UNAVAILABLE": "VALIDATION_FAILED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def create_handover_command_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    analyses: HandoverAnalysisCreateService,
    states: HandoverAnalysisStateService,
    versions: HandoverVersionCreateService,
    validations: HandoverVersionValidationService,
) -> APIRouter:
    """Create an explicitly injected router; production composition remains opt-in."""
    if any(value is None for value in (
            sessions, origins, analyses, states, versions, validations)):
        raise ValueError("Handover command HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/handover-analyses")
    async def create_analysis(project_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _ANALYSIS_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["analysis_purpose"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = CreateHandoverAnalysis(
            token, csrf, uuid.UUID(request.state.trace_id), _canonical_uuid(project_id),
            body["analysis_purpose"], _documents(body["source_documents"]), key,
        )
        try:
            view = await run_in_threadpool(analyses.create, command)
        except HandoverAnalysisCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not HandoverAnalysisInitialView:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = (f"/api/v1/projects/{view.project_id}/handover-analyses/"
                f"{view.handover_analysis_id}")
        return JSONResponse({"data": {
            "handover_analysis_id": str(view.handover_analysis_id),
            "project_id": str(view.project_id),
            "analysis_purpose": view.analysis_purpose,
            "source_set_ref": view.source_set_ref, "state": view.analysis_state,
            "current_approved_version_ref": None,
            "created_at": _instant(view.created_at), "etag": view.etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": view.etag, "Location": path,
        })

    @router.patch("/api/v1/projects/{project_id}/handover-analyses/{analysis_id}")
    async def patch_analysis(project_id: str, analysis_id: str,
                             request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"analysis_purpose"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["analysis_purpose"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchHandoverAnalysis(
            token, csrf, uuid.UUID(request.state.trace_id), _canonical_uuid(project_id),
            _canonical_uuid(analysis_id), expected, body["analysis_purpose"],
        )
        try:
            view = await run_in_threadpool(states.patch, command)
        except HandoverAnalysisStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _analysis_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post("/api/v1/projects/{project_id}/handover-analyses/{analysis_id}:archive")
    async def archive_analysis(project_id: str, analysis_id: str,
                               request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        await _require_empty(request)
        command = ArchiveHandoverAnalysis(
            token, csrf, uuid.UUID(request.state.trace_id), _canonical_uuid(project_id),
            _canonical_uuid(analysis_id), expected, key,
        )
        try:
            view = await run_in_threadpool(states.archive, command)
        except HandoverAnalysisStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not HandoverAnalysisView or view.analysis_state != "ARCHIVED":
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _analysis_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post(
        "/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions"
    )
    async def create_version(project_id: str, analysis_id: str,
                             request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _VERSION_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        command = CreateHandoverVersion(
            token, csrf, uuid.UUID(request.state.trace_id), _canonical_uuid(project_id),
            _canonical_uuid(analysis_id), expected,
            _documents(body["source_documents"]),
            _canonical_uuid(body["capability_baseline_id"]),
            _canonical_uuid(body["capability_baseline_version_id"]),
            _items(body["items"]), _uuid_list(body["ai_task_refs"]), key,
        )
        try:
            view = await run_in_threadpool(versions.create, command)
        except HandoverVersionCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not CreatedHandoverVersion:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = (f"/api/v1/projects/{view.project_id}/handover-analyses/"
                f"{view.handover_analysis_id}/versions/"
                f"{view.handover_analysis_version_id}")
        etag = f'"v{view.lock_version}"'
        return JSONResponse({"data": {
            "handover_analysis_version_id": str(view.handover_analysis_version_id),
            "handover_analysis_id": str(view.handover_analysis_id),
            "project_id": str(view.project_id), "version_no": view.version_no,
            "state": view.version_state, "source_set_ref": view.source_set_ref,
            "capability_baseline_id": str(view.capability_baseline_id),
            "capability_baseline_version_ref": str(
                view.capability_baseline_version_ref
            ),
            "content_fingerprint": view.content_fingerprint.hex(),
            "supersedes_version_ref": (
                None if view.supersedes_version_ref is None
                else str(view.supersedes_version_ref)
            ),
            "created_at": _instant(view.created_at), "analysis_etag": etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": etag, "Location": path,
        })

    @router.post(
        "/api/v1/projects/{project_id}/handover-analyses/{analysis_id}/versions/"
        "{analysis_version_id}:validate"
    )
    async def validate_version(project_id: str, analysis_id: str,
                               analysis_version_id: str,
                               request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        await _require_empty(request)
        command = ValidateHandoverVersion(
            token, csrf, uuid.UUID(request.state.trace_id), _canonical_uuid(project_id),
            _canonical_uuid(analysis_id), _canonical_uuid(analysis_version_id), key,
        )
        try:
            report = await run_in_threadpool(validations.validate, command)
        except HandoverVersionValidationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(report) is not HandoverVersionValidationReport:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            "audit_event_id": str(report.audit_event_id),
            "handover_analysis_id": str(report.handover_analysis_id),
            "handover_analysis_version_id": str(report.handover_analysis_version_id),
            "project_id": str(report.project_id), "version_no": report.version_no,
            "state": report.version_state, "item_count": report.item_count,
            "source_count": report.source_count,
            "evidence_count": report.evidence_count,
            "capability_ref_count": report.capability_ref_count,
            "ai_task_count": report.ai_task_count, "valid": report.valid,
            "blocking_issues": list(report.issue_codes), "warnings": [],
            "checked_at": _instant(report.observed_at),
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    return router
