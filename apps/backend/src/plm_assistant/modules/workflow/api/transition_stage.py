"""Opt-in frozen WORKFLOW_TRANSITION HTTP boundary."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _idempotency_header
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.platform.api.if_match import parse_if_match
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.workflow.application.append_stage_transition import (
    PersistedStageTransition,
)
from plm_assistant.modules.workflow.application.transition_stage import (
    TransitionWorkflowStage, WorkflowStageTransitionError,
    WorkflowStageTransitionService,
)

from .record_checklist import (
    _canonical_uuid, _instant, _read_json, _security,
)


_FIELDS = frozenset({
    "target_stage_key", "reason", "gate_snapshot_refs",
})


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
        "WORKFLOW_TRANSITION_INVALID": "WORKFLOW_TRANSITION_INVALID",
    }.get(code, "SYSTEM_UNAVAILABLE")
    return ApplicationError(mapped)


def stage_transition_data(
    value: PersistedStageTransition,
) -> dict[str, object]:
    try:
        if type(value) is not PersistedStageTransition:
            raise ValueError("Stage Transition view required")
        value.__post_init__()
        snapshot = value.snapshot
        etag = f'"v{value.current_workflow_version}"'
        return {
            "stage_transition_id": str(value.stage_transition_id),
            "workflow_id": str(snapshot.workflow_id),
            "project_id": str(snapshot.project_id),
            "definition_version": snapshot.definition_version,
            "from_stage": snapshot.from_stage,
            "to_stage": snapshot.to_stage,
            "before_workflow_version": snapshot.before_lock_version,
            "transitioned_workflow_version": snapshot.after_lock_version,
            "current_workflow_version": value.current_workflow_version,
            "reason": snapshot.reason,
            "occurred_at": _instant(snapshot.occurred_at),
            "etag": etag,
        }
    except ApplicationError:
        raise
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_workflow_stage_transition_router(
    *, sessions: SessionService, transitions: WorkflowStageTransitionService,
    origins: LoginOriginPolicy,
) -> APIRouter:
    """Create the explicitly injected Stage Transition transport boundary."""

    if sessions is None or transitions is None or origins is None:
        raise ValueError("Workflow Stage Transition HTTP dependencies required")
    router = APIRouter()

    @router.post(
        "/api/v1/projects/{project_id}/workflow:transition",
        operation_id="WORKFLOW_TRANSITION",
    )
    async def transition_stage(
        project_id: str, request: Request,
    ) -> JSONResponse:
        token, csrf, headers = await _security(request, sessions, origins)
        key = _idempotency_header(headers)
        expected = parse_if_match(headers)
        body = await _read_json(request, headers)
        if type(body) is not dict or set(body) != _FIELDS:
            raise ApplicationError("REQUEST_MALFORMED")
        if (type(body["target_stage_key"]) is not str
                or type(body["reason"]) is not str):
            raise ApplicationError("VALIDATION_FAILED")
        # CR-WFL-009: present and empty means server-authoritative snapshot.
        if (type(body["gate_snapshot_refs"]) is not list
                or body["gate_snapshot_refs"]):
            raise ApplicationError("VALIDATION_FAILED")
        command = TransitionWorkflowStage(
            token, csrf, uuid.UUID(request.state.trace_id),
            _canonical_uuid(project_id), body["target_stage_key"],
            expected, body["reason"],
        )
        try:
            value = await run_in_threadpool(
                transitions.transition, command, idempotency_key=key,
            )
        except WorkflowStageTransitionError as error:
            raise _failure(error.code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(value) is not PersistedStageTransition
                or value.snapshot.project_id != command.project_id
                or value.snapshot.to_stage != command.target_stage_key
                or value.snapshot.before_lock_version
                   != command.expected_workflow_version):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = stage_transition_data(value)
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": data["etag"]},
        )

    return router
