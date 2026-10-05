"""Opt-in HTTP boundary for Handover Action create and metadata patch."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.handover.application.create_action import (
    CreateHandoverAction,
    HandoverActionCreateError,
    HandoverActionCreateService,
    HandoverActionInitialView,
)
from plm_assistant.modules.handover.application.patch_action import (
    HandoverActionPatchError,
    HandoverActionPatchService,
    HandoverActionPatchView,
    PatchHandoverAction,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError

from .commands import _canonical_uuid, _instant, _read_json, _security


_CREATE_FIELDS = frozenset({
    "source_analysis_version_ref", "source_item_id", "human_source_reason",
    "action_type", "title", "requested_input_spec", "owner_ref", "due_at",
    "priority", "created_reason",
})
_PATCH_FIELDS = frozenset({
    "title", "requested_input_spec", "owner_ref", "due_at", "priority",
})


def _optional_uuid(value: object) -> uuid.UUID | None:
    return None if value is None else _canonical_uuid(value)


def _utc_instant(value: object) -> datetime:
    if type(value) is not str:
        raise ApplicationError("VALIDATION_FAILED")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise ApplicationError("VALIDATION_FAILED") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ApplicationError("VALIDATION_FAILED")
    parsed = parsed.astimezone(timezone.utc)
    if _instant(parsed) != value:
        raise ApplicationError("VALIDATION_FAILED")
    return parsed


def _failure(code: str) -> ApplicationError:
    mapped = {
        "AUTH_ACCESS_DENIED": "RESOURCE_NOT_FOUND",
        "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
        "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
        "VALIDATION_FAILED": "VALIDATION_FAILED",
        "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
        "CONFLICT_VERSION": "CONFLICT_VERSION",
        "HANDOVER_STATE_INVALID": "HANDOVER_ACTION_STATE_INVALID",
        "HANDOVER_ACTION_STATE_INVALID": "HANDOVER_ACTION_STATE_INVALID",
        "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def _initial_data(view: HandoverActionInitialView) -> dict[str, object]:
    if type(view) is not HandoverActionInitialView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "action_item_id": str(view.action_item_id),
        "project_id": str(view.project_id),
        "source_kind": view.source_kind,
        "source_analysis_version_ref": (
            None if view.source_analysis_version_ref is None
            else str(view.source_analysis_version_ref)
        ),
        "source_item_id": (
            None if view.source_item_id is None else str(view.source_item_id)
        ),
        "human_source_reason": view.human_source_reason,
        "action_type": view.action_type,
        "title": view.title,
        "requested_input_spec": view.requested_input_spec,
        "owner_ref": str(view.owner_ref),
        "due_at": _instant(view.due_at),
        "priority": view.priority,
        "created_by": str(view.created_by),
        "created_reason": view.created_reason,
        "created_at": _instant(view.created_at),
        "initial_event_id": str(view.initial_event_id),
        "action_state": view.action_state,
        "etag": view.etag,
    }


def _patch_data(view: HandoverActionPatchView) -> dict[str, object]:
    if type(view) is not HandoverActionPatchView:
        raise ApplicationError("SYSTEM_UNAVAILABLE")
    return {
        "action_item_id": str(view.action_item_id),
        "project_id": str(view.project_id),
        "title": view.title,
        "requested_input_spec": view.requested_input_spec,
        "owner_ref": str(view.owner_ref),
        "due_at": _instant(view.due_at),
        "priority": view.priority,
        "action_state": view.action_state,
        "updated_at": _instant(view.updated_at),
        "etag": view.etag,
    }


def create_handover_action_command_router(
    *, sessions: SessionService, origins: LoginOriginPolicy,
    creates: HandoverActionCreateService, patches: HandoverActionPatchService,
) -> APIRouter:
    """Create the explicitly injected Action create/patch transport boundary."""

    if any(value is None for value in (sessions, origins, creates, patches)):
        raise ValueError("Handover Action command HTTP dependencies required")
    router = APIRouter()

    @router.post("/api/v1/projects/{project_id}/handover-action-items")
    async def create_action(project_id: str, request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        key = _idempotency_header(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _CREATE_FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        text_fields = ("action_type", "title", "priority", "created_reason")
        nullable_text = ("human_source_reason",)
        if (any(type(body[field]) is not str for field in text_fields)
                or any(body[field] is not None and type(body[field]) is not str
                       for field in nullable_text)
                or type(body["requested_input_spec"]) is not dict):
            raise ApplicationError("VALIDATION_FAILED")
        command = CreateHandoverAction(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id),
            _optional_uuid(body["source_analysis_version_ref"]),
            _optional_uuid(body["source_item_id"]),
            body["human_source_reason"], body["action_type"], body["title"],
            body["requested_input_spec"], _canonical_uuid(body["owner_ref"]),
            _utc_instant(body["due_at"]), body["priority"],
            body["created_reason"], key,
        )
        try:
            view = await run_in_threadpool(creates.create, command)
        except HandoverActionCreateError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if view.project_id != command.project_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        path = (f"/api/v1/projects/{view.project_id}/handover-action-items/"
                f"{view.action_item_id}")
        return JSONResponse(
            {"data": _initial_data(view), "trace_id": request.state.trace_id},
            status_code=201,
            headers={"Cache-Control": "no-store", "ETag": view.etag,
                     "Location": path},
        )

    @router.patch(
        "/api/v1/projects/{project_id}/handover-action-items/{action_item_id}"
    )
    async def patch_action(project_id: str, action_item_id: str,
                           request: Request) -> JSONResponse:
        token, csrf = await _security(request, sessions, origins)
        headers = tuple(request.scope.get("headers", ()))
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if (type(body) is not dict or not body
                or not set(body).issubset(_PATCH_FIELDS)):
            raise ApplicationError("REQUEST_MALFORMED")
        if ("title" in body and type(body["title"]) is not str
                or "requested_input_spec" in body
                and type(body["requested_input_spec"]) is not dict
                or "owner_ref" in body and type(body["owner_ref"]) is not str
                or "due_at" in body and type(body["due_at"]) is not str
                or "priority" in body and type(body["priority"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        command = PatchHandoverAction(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), _canonical_uuid(action_item_id), expected,
            title=body.get("title"),
            requested_input_spec=body.get("requested_input_spec"),
            owner_ref=(None if "owner_ref" not in body
                       else _canonical_uuid(body["owner_ref"])),
            due_at=(None if "due_at" not in body else _utc_instant(body["due_at"])),
            priority=body.get("priority"),
        )
        try:
            view = await run_in_threadpool(patches.patch, command)
        except HandoverActionPatchError as exc:
            raise _failure(exc.code) from None
        except RuntimeLicenseError:
            raise ApplicationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (view.project_id != command.project_id
                or view.action_item_id != command.action_item_id):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        return JSONResponse(
            {"data": _patch_data(view), "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": view.etag},
        )

    return router
