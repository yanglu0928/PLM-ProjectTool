"""Frozen WORKFLOW_GET; explicit safe projection, never bootstraps on read."""
import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginError, LoginOriginPolicy
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import SessionError, SessionService
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.workflow.application.read_workflow import (
    WorkflowReadError, WorkflowReadQuery, WorkflowReadService, WorkflowView,
)


def workflow_view_data(view: WorkflowView) -> dict[str, object]:
    try:
        if type(view) is not WorkflowView:
            raise ValueError("Workflow view required")
        view.__post_init__()
        return {
            "workflow_id": str(view.workflow_id), "version": view.version,
            "state": view.state, "current_stage": view.current_stage,
            "stages": [{
                "stage_key": stage.stage_key, "order": stage.order, "state": stage.state,
                "checklist_items": [{"item_key": item.item_key, "required": item.required,
                                     "state": item.state} for item in stage.checklist_items],
            } for stage in view.stages], "etag": view.etag,
        }
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_workflow_read_router(*, sessions: SessionService, workflows: WorkflowReadService,
                                origins: LoginOriginPolicy) -> APIRouter:
    if sessions is None or workflows is None or origins is None:
        raise ValueError("Workflow HTTP dependencies required")
    router = APIRouter()

    @router.get("/api/v1/projects/{project_id}/workflow", operation_id="WORKFLOW_GET")
    async def get_workflow(project_id: uuid.UUID, request: Request) -> JSONResponse:
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
        if request.url.query:
            raise ApplicationError("REQUEST_MALFORMED")
        try:
            view = await run_in_threadpool(workflows.get, WorkflowReadQuery(
                token, project_id, uuid.UUID(request.state.trace_id),
            ))
        except WorkflowReadError as exc:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(exc.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if type(view) is not WorkflowView or view.project_id != project_id:
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        body = workflow_view_data(view)
        return JSONResponse({"data": body, "trace_id": request.state.trace_id},
                            headers={"Cache-Control": "no-store", "ETag": view.etag})
    return router
