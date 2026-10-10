"""Opt-in Checklist current qualification preview; never a Gate proof."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from plm_assistant.modules.auth.api.login_origin_policy import (
    LoginOriginError, LoginOriginPolicy,
)
from plm_assistant.modules.auth.api.session import _session_cookie
from plm_assistant.modules.auth.application.session_service import (
    SessionError, SessionService,
)
from plm_assistant.modules.platform.application.errors import ApplicationError
from plm_assistant.modules.workflow.application.preview_checklist_qualification import (
    WorkflowChecklistQualificationPreview,
    WorkflowChecklistQualificationPreviewError,
    WorkflowChecklistQualificationPreviewQuery,
    WorkflowChecklistQualificationPreviewService,
)


def checklist_qualification_preview_data(
    preview: WorkflowChecklistQualificationPreview,
) -> dict[str, object]:
    try:
        if type(preview) is not WorkflowChecklistQualificationPreview:
            raise ValueError("Checklist qualification preview required")
        preview.__post_init__()
        if preview.stage_key == "HANDOVER":
            return {
                "workflow_id": str(preview.workflow_id),
                "project_id": str(preview.project_id),
                "definition_version": preview.definition_version,
                "stage_key": preview.stage_key,
                "item_key": preview.item_key,
                "current_item_state": preview.current_item_state,
                "workflow_etag": preview.workflow_etag,
                "handover_analysis_version_id": str(
                    preview.handover_analysis_version_id,
                ),
                "review_round_ref": str(preview.review_round_ref),
                "evidence_refs": [
                    str(value) for value in preview.evidence_refs
                ],
            }
        if preview.stage_key == "SURVEY":
            return {
                "workflow_id": str(preview.workflow_id),
                "project_id": str(preview.project_id),
                "definition_version": preview.definition_version,
                "stage_key": preview.stage_key,
                "item_key": preview.item_key,
                "current_item_state": preview.current_item_state,
                "workflow_etag": preview.workflow_etag,
                "survey_conclusion_id": str(preview.survey_conclusion_id),
                "review_round_ref": str(preview.review_round_ref),
                "evidence_refs": [str(value) for value in preview.evidence_refs],
            }
        if preview.stage_key == "PROTOTYPE":
            return {
                "workflow_id": str(preview.workflow_id),
                "project_id": str(preview.project_id),
                "definition_version": preview.definition_version,
                "stage_key": preview.stage_key,
                "item_key": preview.item_key,
                "current_item_state": preview.current_item_state,
                "workflow_etag": preview.workflow_etag,
                "qualified_subjects": [{
                    "subject_type": value.subject_type,
                    "subject_id": str(value.subject_id),
                    "subject_version_id": str(value.subject_version_id),
                    "review_round_ref": str(value.review_round_ref),
                } for value in preview.qualified_subjects],
                "evidence_refs": [str(value) for value in preview.evidence_refs],
            }
        return {
            "workflow_id": str(preview.workflow_id),
            "project_id": str(preview.project_id),
            "definition_version": preview.definition_version,
            "stage_key": preview.stage_key,
            "item_key": preview.item_key,
            "current_item_state": preview.current_item_state,
            "workflow_etag": preview.workflow_etag,
            "requirement_version_refs": [
                str(value) for value in preview.requirement_version_refs
            ],
            "review_round_refs": [
                str(value) for value in preview.review_round_refs
            ],
            "evidence_refs": [str(value) for value in preview.evidence_refs],
        }
    except Exception:
        raise ApplicationError("SYSTEM_UNAVAILABLE") from None


def create_workflow_checklist_qualification_router(
    *, sessions: SessionService,
    previews: WorkflowChecklistQualificationPreviewService,
    origins: LoginOriginPolicy,
    enable_prototype: bool = False,
) -> APIRouter:
    """Create the explicitly injected, fail-closed preview boundary."""

    if sessions is None or previews is None or origins is None:
        raise ValueError("Workflow Checklist qualification HTTP dependencies required")
    if type(enable_prototype) is not bool:
        raise ValueError("Prototype Workflow switch must be explicit")
    router = APIRouter()

    @router.get(
        "/api/v1/projects/{project_id}/workflow/checklist-items/"
        "{item_key}/qualification",
        operation_id="WORKFLOW_CHECKLIST_QUALIFICATION_GET",
    )
    async def get_qualification(
        project_id: str, item_key: str, request: Request,
    ) -> JSONResponse:
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
            canonical_project_id = uuid.UUID(project_id)
        except (ValueError, AttributeError):
            raise ApplicationError("VALIDATION_FAILED") from None
        if (canonical_project_id.int == 0
                or str(canonical_project_id) != project_id):
            raise ApplicationError("VALIDATION_FAILED")
        allowed_items = {
            "HANDOVER_BASELINE", "HANDOVER_ISSUES",
            "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION",
            "REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE",
        }
        if enable_prototype:
            allowed_items.update((
                "PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE",
            ))
        if item_key not in allowed_items:
            raise ApplicationError("VALIDATION_FAILED")
        try:
            preview = await run_in_threadpool(
                previews.get,
                WorkflowChecklistQualificationPreviewQuery(
                    token, uuid.UUID(request.state.trace_id),
                    canonical_project_id, item_key,
                ),
            )
        except WorkflowChecklistQualificationPreviewError as error:
            code = {
                "AUTH_ACCESS_DENIED": "AUTH_SESSION_EXPIRED",
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "PROJECT_ARCHIVED": "PROJECT_ARCHIVED",
                "CONFLICT_STATE": "CONFLICT_STATE",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "WORKFLOW_GATE_NOT_SATISFIED": (
                    "WORKFLOW_GATE_NOT_SATISFIED"
                ),
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(error.code, "SYSTEM_UNAVAILABLE")
            raise ApplicationError(code) from None
        except Exception:
            raise ApplicationError("SYSTEM_UNAVAILABLE") from None
        if (type(preview) is not WorkflowChecklistQualificationPreview
                or preview.project_id != canonical_project_id
                or preview.item_key != item_key):
            raise ApplicationError("SYSTEM_UNAVAILABLE")
        data = checklist_qualification_preview_data(preview)
        return JSONResponse(
            {"data": data, "trace_id": request.state.trace_id},
            headers={"Cache-Control": "no-store", "ETag": preview.workflow_etag},
        )

    return router
