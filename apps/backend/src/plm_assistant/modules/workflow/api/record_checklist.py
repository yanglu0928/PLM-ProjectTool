"""Opt-in frozen WORKFLOW_CHECKLIST_RECORD HTTP boundary."""

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
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.workflow.application.current_checklist_record import (
    CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.application.record_checklist import (
    RecordWorkflowChecklist, WorkflowChecklistRecordError,
    WorkflowChecklistRecordService,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


_MAX_BODY = 2 * 1024 * 1024
_REQUIRED_FIELDS = frozenset({"result", "evidence_refs", "exception_refs"})
_OPTIONAL_FIELDS = frozenset({"reason", "impact"})


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


async def _read_json(
    request: Request, headers: tuple[tuple[bytes, bytes], ...],
) -> object:
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
                object_pairs_hook=_unique_pairs,
                parse_constant=_reject_constant,
            )
        except (UnicodeDecodeError, ValueError, TypeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
    finally:
        raw[:] = b"\x00" * len(raw)


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


def _uuid_list(value: object) -> tuple[uuid.UUID, ...]:
    if type(value) is not list:
        raise ApplicationError("REQUEST_MALFORMED")
    return tuple(_canonical_uuid(item) for item in value)


def _instant(value: datetime) -> str:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _security(
    request: Request, sessions: SessionService, origins: LoginOriginPolicy,
) -> tuple[bytes, bytes, tuple[tuple[bytes, bytes], ...]]:
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
    except SessionError as error:
        raise _session_failure(error) from None
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None
    if request.url.query:
        raise ApplicationError("REQUEST_MALFORMED")
    return token, csrf, headers


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "CONFLICT_STATE": "CONFLICT_STATE",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "WORKFLOW_GATE_NOT_SATISFIED": "WORKFLOW_GATE_NOT_SATISFIED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def checklist_record_data(view: CurrentChecklistRecord) -> dict[str, object]:
    try:
        if type(view) is not CurrentChecklistRecord:
            raise ValueError("Checklist record view required")
        view.__post_init__()
        record = view.record
        etag = f'"v{view.current_workflow_version}"'
        return {
            "record_id": str(record.record_id),
            "workflow_id": str(record.workflow_id),
            "project_id": str(record.project_id),
            "definition_version": record.definition_version,
            "stage_key": record.stage_key,
            "item_key": record.item_key,
            "result": record.result.value,
            "item_version": record.after_item_version,
            "recorded_workflow_version": record.after_workflow_version,
            "current_workflow_version": view.current_workflow_version,
            "supersedes_record_id": (
                None if record.supersedes_record_id is None
                else str(record.supersedes_record_id)
            ),
            "evidence_refs": [str(value) for value in record.evidence_refs],
            "review_round_refs": [str(value) for value in record.review_round_refs],
            "exception_refs": [str(value) for value in record.exception_refs],
            "reason": record.reason,
            "impact": record.impact,
            "occurred_at": _instant(record.occurred_at),
            "etag": etag,
        }
    except ApplicationError:
        raise
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_workflow_checklist_record_router(
    *, sessions: SessionService, records: WorkflowChecklistRecordService,
    origins: LoginOriginPolicy,
) -> APIRouter:
    """Create the explicitly injected Checklist record transport boundary."""

    if sessions is None or records is None or origins is None:
        raise ValueError("Workflow Checklist record HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/workflow/checklist-items/"
        "{item_key}:record",
        operation_id="WORKFLOW_CHECKLIST_RECORD",
    )
    async def record_checklist(
        project_id: str, item_key: str, request: Request,
    ) -> JSONResponse:
        token, csrf, headers = await _security(request, sessions, origins)
        key = _idempotency_header(headers)
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if (type(body) is not dict
                or not _REQUIRED_FIELDS.issubset(body)
                or not set(body).issubset(_REQUIRED_FIELDS | _OPTIONAL_FIELDS)):
            raise ApplicationError("REQUEST_MALFORMED")
        if (type(body["result"]) is not str
                or body.get("reason") is not None
                and type(body.get("reason")) is not str
                or body.get("impact") is not None
                and type(body.get("impact")) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        try:
            result = ChecklistState(body["result"])
        except ValueError:
            raise ApplicationError("VALIDATION_FAILED") from None
        if result not in {
                ChecklistState.PASS, ChecklistState.FAIL,
                ChecklistState.WAIVED}:
            raise ApplicationError("VALIDATION_FAILED")
        command = RecordWorkflowChecklist(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), item_key, result,
            _uuid_list(body["evidence_refs"]),
            _uuid_list(body["exception_refs"]), expected,
            body.get("reason"), body.get("impact"),
        )
        try:
            view = await run_in_threadpool(
                records.record, command, idempotency_key=key,
            )
        except WorkflowChecklistRecordError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(view) is not CurrentChecklistRecord
                or view.record.project_id != command.project_id
                or view.record.item_key != command.item_key
                or view.record.result is not command.result):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = checklist_record_data(view)
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": data["etag"]},
        )

    return router
