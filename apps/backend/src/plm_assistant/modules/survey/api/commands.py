"""Opt-in HTTP boundary for the five ordinary Survey commands."""

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
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.survey.application.change_survey import (
    ArchiveSurvey, PatchSurvey, SurveyStateError, SurveyStateService,
)
from plm_assistant.modules.survey.application.create_survey import (
    CreateSurvey, SurveyCreateError, SurveyCreateService, SurveyInitialView,
)
from plm_assistant.modules.survey.application.create_version import (
    CreatedSurveyVersion, CreateSurveyVersion, SurveyOptionDraft,
    SurveyQuestionDraft, SurveySourceDraft, SurveyVersionCreateError,
    SurveyVersionCreateService,
)
from plm_assistant.modules.survey.application.read_surveys import SurveyView
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionValidationError, SurveyVersionValidationReport,
    SurveyVersionValidationService, ValidateSurveyVersion,
)


_MAX_BODY = 2 * 1024 * 1024
_VERSION_FIELDS = frozenset({"questions", "target_department_ids"})
_QUESTION_FIELDS = frozenset({
    "question_id", "topic", "question_text", "objective", "answer_type",
    "validation_rule", "required", "condition_rule", "expected_output",
    "evidence_required", "options", "sources",
})
_OPTION_FIELDS = frozenset({"option_code", "label", "description"})
_SOURCE_FIELDS = frozenset({
    "source_kind", "handover_item_row_id", "handover_analysis_version_id",
    "handover_analysis_id", "capability_item_row_id",
    "capability_baseline_version_id", "capability_baseline_id",
    "template_document_version_id", "template_document_id",
    "manual_source_note",
})
_SOURCE_UUID_FIELDS = tuple(_SOURCE_FIELDS - {"source_kind", "manual_source_note"})


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


def _nullable_uuid(value: object) -> uuid.UUID | None:
    return None if value is None else _canonical_uuid(value)


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


def _uuid_list(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_canonical_uuid(item) for item in value)


def _option(value: object) -> SurveyOptionDraft:
    if type(value) is not dict or set(value) != _OPTION_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(value["option_code"]) is not str
            or type(value["label"]) is not str
            or value["description"] is not None
            and type(value["description"]) is not str):
        raise ApplicationError("VALIDATION_FAILED")
    return SurveyOptionDraft(
        value["option_code"], value["label"], value["description"],
    )


def _source(value: object) -> SurveySourceDraft:
    if type(value) is not dict or set(value) != _SOURCE_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    if (type(value["source_kind"]) is not str
            or value["manual_source_note"] is not None
            and type(value["manual_source_note"]) is not str):
        raise ApplicationError("VALIDATION_FAILED")
    parsed = {field: _nullable_uuid(value[field]) for field in _SOURCE_UUID_FIELDS}
    return SurveySourceDraft(
        source_kind=value["source_kind"],
        handover_item_row_id=parsed["handover_item_row_id"],
        handover_analysis_version_id=parsed["handover_analysis_version_id"],
        handover_analysis_id=parsed["handover_analysis_id"],
        capability_item_row_id=parsed["capability_item_row_id"],
        capability_baseline_version_id=parsed["capability_baseline_version_id"],
        capability_baseline_id=parsed["capability_baseline_id"],
        template_document_version_id=parsed["template_document_version_id"],
        template_document_id=parsed["template_document_id"],
        manual_source_note=value["manual_source_note"],
    )


def _question(value: object) -> SurveyQuestionDraft:
    if type(value) is not dict or set(value) != _QUESTION_FIELDS:
        raise ApplicationError("REQUEST_MALFORMED")
    strings = ("topic", "question_text", "objective", "answer_type", "expected_output")
    if (any(type(value[field]) is not str for field in strings)
            or type(value["validation_rule"]) is not dict
            or value["condition_rule"] is not None
            and type(value["condition_rule"]) is not dict
            or type(value["required"]) is not bool
            or type(value["evidence_required"]) is not bool
            or type(value["options"]) is not list
            or type(value["sources"]) is not list):
        raise ApplicationError("VALIDATION_FAILED")
    return SurveyQuestionDraft(
        question_id=_canonical_uuid(value["question_id"]),
        topic=value["topic"], question_text=value["question_text"],
        objective=value["objective"], answer_type=value["answer_type"],
        validation_rule=value["validation_rule"], required=value["required"],
        condition_rule=value["condition_rule"],
        expected_output=value["expected_output"],
        evidence_required=value["evidence_required"],
        options=tuple(_option(item) for item in value["options"]),
        sources=tuple(_source(item) for item in value["sources"]),
    )


def _questions(value: object) -> tuple[SurveyQuestionDraft, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_question(item) for item in value)


def _survey_data(view: SurveyView) -> dict[str, object]:
    if type(view) is not SurveyView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "survey_id": str(view.survey_id), "project_id": str(view.project_id),
        "name": view.name, "state": view.survey_state,
        "current_approved_version_ref": (
            None if view.current_approved_version_ref is None
            else str(view.current_approved_version_ref)
        ),
        "created_at": _instant(view.created_at),
        "updated_at": _instant(view.updated_at), "etag": view.etag,
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
        "SURVEY_STATE_CONFLICT": "CONFLICT_STATE",
        "SURVEY_SOURCE_UNAVAILABLE": "VALIDATION_FAILED",
        "SURVEY_DEPARTMENT_UNAVAILABLE": "VALIDATION_FAILED",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def create_survey_command_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    surveys: SurveyCreateService, states: SurveyStateService,
    versions: SurveyVersionCreateService,
    validations: SurveyVersionValidationService,
) -> APIRouter:
    """Create an explicitly injected router; production composition remains opt-in."""
    if any(value is None for value in (
            sessions, origins, surveys, states, versions, validations)):
        raise ValueError("Survey command HTTP dependencies are required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/surveys")
    async def create_survey(project_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"name"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["name"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = CreateSurvey(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), body["name"], key,
        )
        try:
            view = await run_in_threadpool(surveys.create, command)
        except SurveyCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not SurveyInitialView:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = f"/api/v1/projects/{view.project_id}/surveys/{view.survey_id}"
        return JSONResponse({"data": {
            "survey_id": str(view.survey_id), "project_id": str(view.project_id),
            "name": view.name, "state": view.survey_state,
            "current_approved_version_ref": None,
            "created_at": _instant(view.created_at), "etag": view.etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": view.etag, "Location": path,
        })

    @router.patch("/api/v1/projects/{project_id}/surveys/{survey_id}")
    async def patch_survey(project_id: str, survey_id: str,
                           request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != {"name"}:
            raise ApplicationError("REQUEST_MALFORMED")
        if type(body["name"]) is not str:
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchSurvey(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(survey_id),
            expected, body["name"],
        )
        try:
            view = await run_in_threadpool(states.patch, command)
        except SurveyStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        return JSONResponse(
            {"data": _survey_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post("/api/v1/projects/{project_id}/surveys/{survey_id}:archive")
    async def archive_survey(project_id: str, survey_id: str,
                             request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        await _require_empty(request)
        command = ArchiveSurvey(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(survey_id), expected, key,
        )
        try:
            view = await run_in_threadpool(states.archive, command)
        except SurveyStateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not SurveyView or view.survey_state != "ARCHIVED":
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _survey_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    @router.post("/api/v1/projects/{project_id}/surveys/{survey_id}/versions")
    async def create_version(project_id: str, survey_id: str,
                             request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected, key = parse_if_match(headers), _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _VERSION_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        command = CreateSurveyVersion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(survey_id), expected,
            _questions(body["questions"]),
            _uuid_list(body["target_department_ids"]), key,
        )
        try:
            view = await run_in_threadpool(versions.create, command)
        except SurveyVersionCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not CreatedSurveyVersion:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = (f"/api/v1/projects/{view.project_id}/surveys/{view.survey_id}/"
                f"versions/{view.survey_version_id}")
        etag = f'"v{view.lock_version}"'
        return JSONResponse({"data": {
            "survey_version_id": str(view.survey_version_id),
            "survey_id": str(view.survey_id), "project_id": str(view.project_id),
            "version_no": view.version_no, "state": view.version_state,
            "content_fingerprint": view.content_fingerprint.hex(),
            "supersedes_version_ref": (
                None if view.supersedes_version_ref is None
                else str(view.supersedes_version_ref)
            ),
            "created_at": _instant(view.created_at), "survey_etag": etag,
        }, "trace_id": request.state.trace_id}, status_code=201, headers={
            "Cache-Control": "no-store", "ETag": etag, "Location": path,
        })

    @router.post(
        "/api/v1/projects/{project_id}/surveys/{survey_id}/versions/"
        "{survey_version_id}:validate"
    )
    async def validate_version(project_id: str, survey_id: str,
                               survey_version_id: str,
                               request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        await _require_empty(request)
        command = ValidateSurveyVersion(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(survey_id),
            _canonical_uuid(survey_version_id), key,
        )
        try:
            report = await run_in_threadpool(validations.validate, command)
        except SurveyVersionValidationError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(report) is not SurveyVersionValidationReport:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse({"data": {
            "audit_event_id": str(report.audit_event_id),
            "survey_id": str(report.survey_id),
            "survey_version_id": str(report.survey_version_id),
            "project_id": str(report.project_id), "version_no": report.version_no,
            "state": report.version_state, "question_count": report.question_count,
            "option_count": report.option_count, "source_count": report.source_count,
            "target_department_count": report.target_department_count,
            "conditional_question_count": report.conditional_question_count,
            "valid": report.valid, "blocking_issues": list(report.issue_codes),
            "warnings": [], "checked_at": _instant(report.observed_at),
        }, "trace_id": request.state.trace_id}, headers={"Cache-Control": "no-store"})

    return router
