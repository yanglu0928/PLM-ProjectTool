from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.routing import APIRouter

from plm_assistant import __version__
from plm_assistant.modules.platform.api.error_handlers import install_error_handlers
from plm_assistant.modules.platform.api.health import create_health_router
from plm_assistant.modules.platform.api.trace_middleware import TraceMiddleware
from plm_assistant.modules.platform.api.maintenance_middleware import (
    MaintenanceAdmissionMiddleware, MaintenanceAdmissionPort,
)
from plm_assistant.modules.platform.application.health import (
    HealthService,
    ReadinessCheck,
)
from plm_assistant.modules.platform.infrastructure.structured_logging import (
    StructuredLoggers,
)


APP_TITLE = "PLM Project Implementation Assistant API"


def create_app(
    *,
    readiness_checks: Iterable[ReadinessCheck] | None = None,
    loggers: StructuredLoggers | None = None,
    login_router: APIRouter | None = None,
    session_router: APIRouter | None = None,
    session_renew_router: APIRouter | None = None,
    session_logout_router: APIRouter | None = None,
    user_detail_router: APIRouter | None = None,
    user_list_router: APIRouter | None = None,
    user_create_router: APIRouter | None = None,
    user_name_patch_router: APIRouter | None = None,
    user_state_router: APIRouter | None = None,
    password_change_router: APIRouter | None = None,
    password_reset_router: APIRouter | None = None,
    secret_metadata_router: APIRouter | None = None,
    secret_metadata_list_router: APIRouter | None = None,
    secret_create_router: APIRouter | None = None,
    secret_rotate_router: APIRouter | None = None,
    secret_disable_router: APIRouter | None = None,
    ai_provider_read_router: APIRouter | None = None,
    ai_model_read_router: APIRouter | None = None,
    ai_prompt_read_router: APIRouter | None = None,
    ai_model_create_router: APIRouter | None = None,
    ai_model_state_router: APIRouter | None = None,
    ai_prompt_version_router: APIRouter | None = None,
    ai_prompt_activation_router: APIRouter | None = None,
    ai_prompt_retire_router: APIRouter | None = None,
    ai_provider_create_router: APIRouter | None = None,
    ai_provider_patch_router: APIRouter | None = None,
    ai_provider_test_router: APIRouter | None = None,
    ai_provider_activate_router: APIRouter | None = None,
    ai_egress_router: APIRouter | None = None,
    ai_task_create_router: APIRouter | None = None,
    ai_task_read_router: APIRouter | None = None,
    ai_task_list_router: APIRouter | None = None,
    ai_task_invocation_list_router: APIRouter | None = None,
    ai_suggestion_read_router: APIRouter | None = None,
    rag_retrieval_router: APIRouter | None = None,
    rag_retrieval_cancel_router: APIRouter | None = None,
    project_read_router: APIRouter | None = None,
    workflow_read_router: APIRouter | None = None,
    workflow_start_router: APIRouter | None = None,
    workflow_checklist_record_router: APIRouter | None = None,
    workflow_checklist_qualification_router: APIRouter | None = None,
    workflow_transition_router: APIRouter | None = None,
    trace_revoke_router: APIRouter | None = None,
    trace_supersede_router: APIRouter | None = None,
    audit_read_router: APIRouter | None = None,
    audit_export_result_router: APIRouter | None = None,
    audit_export_download_router: APIRouter | None = None,
    audit_export_submit_router: APIRouter | None = None,
    job_detail_router: APIRouter | None = None,
    job_list_router: APIRouter | None = None,
    job_cancel_router: APIRouter | None = None,
    job_retry_router: APIRouter | None = None,
    project_create_router: APIRouter | None = None,
    project_patch_router: APIRouter | None = None,
    project_archive_router: APIRouter | None = None,
    project_member_read_router: APIRouter | None = None,
    project_member_candidate_router: APIRouter | None = None,
    project_member_create_router: APIRouter | None = None,
    project_member_patch_router: APIRouter | None = None,
    project_member_state_router: APIRouter | None = None,
    project_department_read_router: APIRouter | None = None,
    project_department_create_router: APIRouter | None = None,
    project_department_patch_router: APIRouter | None = None,
    project_department_deactivate_router: APIRouter | None = None,
    document_upload_create_router: APIRouter | None = None,
    document_upload_content_router: APIRouter | None = None,
    document_upload_finalize_router: APIRouter | None = None,
    document_read_router: APIRouter | None = None,
    document_version_read_router: APIRouter | None = None,
    document_parse_read_router: APIRouter | None = None,
    document_download_router: APIRouter | None = None,
    evidence_create_router: APIRouter | None = None,
    evidence_read_router: APIRouter | None = None,
    evidence_viewer_router: APIRouter | None = None,
    evidence_eligibility_router: APIRouter | None = None,
    evidence_eligibility_operation_lookup_router: APIRouter | None = None,
    capability_command_router: APIRouter | None = None,
    capability_review_router: APIRouter | None = None,
    capability_read_router: APIRouter | None = None,
    handover_command_router: APIRouter | None = None,
    handover_review_submission_router: APIRouter | None = None,
    handover_read_router: APIRouter | None = None,
    handover_action_read_router: APIRouter | None = None,
    handover_action_command_router: APIRouter | None = None,
    handover_action_lifecycle_router: APIRouter | None = None,
    survey_command_router: APIRouter | None = None,
    survey_review_submission_router: APIRouter | None = None,
    survey_read_router: APIRouter | None = None,
    requirement_package_router: APIRouter | None = None,
    requirement_router: APIRouter | None = None,
    requirement_version_router: APIRouter | None = None,
    requirement_review_submission_router: APIRouter | None = None,
    requirement_relation_router: APIRouter | None = None,
    prototype_package_router: APIRouter | None = None,
    prototype_router: APIRouter | None = None,
    prototype_template_router: APIRouter | None = None,
    prototype_version_router: APIRouter | None = None,
    prototype_review_submission_router: APIRouter | None = None,
    requirement_prototype_link_router: APIRouter | None = None,
    project_reference_create_router: APIRouter | None = None,
    solution_outline_create_router: APIRouter | None = None,
    solution_outline_read_router: APIRouter | None = None,
    global_reference_create_router: APIRouter | None = None,
    global_reference_read_router: APIRouter | None = None,
    global_reference_list_router: APIRouter | None = None,
    project_reference_read_router: APIRouter | None = None,
    project_reference_list_router: APIRouter | None = None,
    reference_deidentification_router: APIRouter | None = None,
    review_command_router: APIRouter | None = None,
    maintenance_admission: MaintenanceAdmissionPort | None = None,
    shutdown_callback: Callable[[], None] | None = None,
) -> FastAPI:
    """Create one isolated API application instance.

    Uvicorn must load this callable with ``--factory``. Runtime integrations add
    readiness probes through the composition root instead of changing the
    public health response or importing infrastructure from the health router.
    """

    health_service = HealthService(tuple(readiness_checks or ()))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        health_service.mark_started()
        try:
            yield
        finally:
            health_service.mark_stopped()
            if shutdown_callback is not None:
                shutdown_callback()

    app = FastAPI(
        title=APP_TITLE,
        version=__version__,
        debug=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.health_service = health_service
    app.state.loggers = loggers or StructuredLoggers()
    if maintenance_admission is not None:
        app.add_middleware(MaintenanceAdmissionMiddleware,
                           admission=maintenance_admission)
    app.add_middleware(TraceMiddleware, loggers=app.state.loggers)
    install_error_handlers(app)
    app.include_router(create_health_router(health_service))
    if login_router is not None:
        app.include_router(login_router)
    if session_router is not None:
        app.include_router(session_router)
    if session_renew_router is not None:
        app.include_router(session_renew_router)
    if session_logout_router is not None:
        app.include_router(session_logout_router)
    if user_detail_router is not None:
        app.include_router(user_detail_router)
    if user_list_router is not None:
        app.include_router(user_list_router)
    if user_create_router is not None:
        app.include_router(user_create_router)
    if user_name_patch_router is not None:
        app.include_router(user_name_patch_router)
    if user_state_router is not None:
        app.include_router(user_state_router)
    if password_change_router is not None:
        app.include_router(password_change_router)
    if password_reset_router is not None:
        app.include_router(password_reset_router)
    if secret_metadata_router is not None:
        app.include_router(secret_metadata_router)
    if secret_metadata_list_router is not None:
        app.include_router(secret_metadata_list_router)
    if secret_create_router is not None:
        app.include_router(secret_create_router)
    if secret_rotate_router is not None:
        app.include_router(secret_rotate_router)
    if secret_disable_router is not None:
        app.include_router(secret_disable_router)
    if ai_provider_read_router is not None:
        app.include_router(ai_provider_read_router)
    if ai_model_read_router is not None:
        app.include_router(ai_model_read_router)
    if ai_prompt_read_router is not None:
        app.include_router(ai_prompt_read_router)
    if ai_model_create_router is not None:
        app.include_router(ai_model_create_router)
    if ai_model_state_router is not None:
        app.include_router(ai_model_state_router)
    if ai_prompt_version_router is not None:
        app.include_router(ai_prompt_version_router)
    if ai_prompt_activation_router is not None:
        app.include_router(ai_prompt_activation_router)
    if ai_prompt_retire_router is not None:
        app.include_router(ai_prompt_retire_router)
    if ai_provider_create_router is not None:
        app.include_router(ai_provider_create_router)
    if ai_provider_patch_router is not None:
        app.include_router(ai_provider_patch_router)
    if ai_provider_test_router is not None:
        app.include_router(ai_provider_test_router)
    if ai_provider_activate_router is not None:
        app.include_router(ai_provider_activate_router)
    if ai_egress_router is not None:
        app.include_router(ai_egress_router)
    if ai_task_create_router is not None:
        app.include_router(ai_task_create_router)
    if ai_task_read_router is not None:
        app.include_router(ai_task_read_router)
    if ai_task_list_router is not None:
        app.include_router(ai_task_list_router)
    if ai_task_invocation_list_router is not None:
        app.include_router(ai_task_invocation_list_router)
    if ai_suggestion_read_router is not None:
        app.include_router(ai_suggestion_read_router)
    if rag_retrieval_router is not None:
        app.include_router(rag_retrieval_router)
    if rag_retrieval_cancel_router is not None:
        app.include_router(rag_retrieval_cancel_router)
    if project_read_router is not None:
        app.include_router(project_read_router)
    if workflow_read_router is not None:
        app.include_router(workflow_read_router)
    if workflow_start_router is not None:
        app.include_router(workflow_start_router)
    if workflow_checklist_record_router is not None:
        app.include_router(workflow_checklist_record_router)
    if workflow_checklist_qualification_router is not None:
        app.include_router(workflow_checklist_qualification_router)
    if workflow_transition_router is not None:
        app.include_router(workflow_transition_router)
    if trace_revoke_router is not None:
        app.include_router(trace_revoke_router)
    if trace_supersede_router is not None:
        app.include_router(trace_supersede_router)
    if audit_read_router is not None:
        app.include_router(audit_read_router)
    if audit_export_result_router is not None:
        app.include_router(audit_export_result_router)
    if audit_export_download_router is not None:
        app.include_router(audit_export_download_router)
    if audit_export_submit_router is not None:
        app.include_router(audit_export_submit_router)
    if job_detail_router is not None:
        app.include_router(job_detail_router)
    if job_list_router is not None:
        app.include_router(job_list_router)
    if job_cancel_router is not None:
        app.include_router(job_cancel_router)
    if job_retry_router is not None:
        app.include_router(job_retry_router)
    if project_create_router is not None:
        app.include_router(project_create_router)
    if project_patch_router is not None:
        app.include_router(project_patch_router)
    if project_archive_router is not None:
        app.include_router(project_archive_router)
    if project_member_read_router is not None:
        app.include_router(project_member_read_router)
    if project_member_candidate_router is not None:
        app.include_router(project_member_candidate_router)
    if project_member_create_router is not None:
        app.include_router(project_member_create_router)
    if project_member_patch_router is not None:
        app.include_router(project_member_patch_router)
    if project_member_state_router is not None:
        app.include_router(project_member_state_router)
    if project_department_read_router is not None:
        app.include_router(project_department_read_router)
    if project_department_create_router is not None:
        app.include_router(project_department_create_router)
    if project_department_patch_router is not None:
        app.include_router(project_department_patch_router)
    if project_department_deactivate_router is not None:
        app.include_router(project_department_deactivate_router)
    if document_upload_create_router is not None:
        app.include_router(document_upload_create_router)
    if document_upload_content_router is not None:
        app.include_router(document_upload_content_router)
    if document_upload_finalize_router is not None:
        app.include_router(document_upload_finalize_router)
    if document_read_router is not None:
        app.include_router(document_read_router)
    if document_version_read_router is not None:
        app.include_router(document_version_read_router)
    if document_parse_read_router is not None:
        app.include_router(document_parse_read_router)
    if document_download_router is not None:
        app.include_router(document_download_router)
    if evidence_create_router is not None:
        app.include_router(evidence_create_router)
    if evidence_read_router is not None:
        app.include_router(evidence_read_router)
    if evidence_viewer_router is not None:
        app.include_router(evidence_viewer_router)
    if evidence_eligibility_router is not None:
        app.include_router(evidence_eligibility_router)
    if evidence_eligibility_operation_lookup_router is not None:
        app.include_router(evidence_eligibility_operation_lookup_router)
    if capability_command_router is not None:
        app.include_router(capability_command_router)
    if capability_review_router is not None:
        app.include_router(capability_review_router)
    if capability_read_router is not None:
        app.include_router(capability_read_router)
    if handover_command_router is not None:
        app.include_router(handover_command_router)
    if handover_review_submission_router is not None:
        app.include_router(handover_review_submission_router)
    if handover_read_router is not None:
        app.include_router(handover_read_router)
    if handover_action_read_router is not None:
        app.include_router(handover_action_read_router)
    if handover_action_command_router is not None:
        app.include_router(handover_action_command_router)
    if handover_action_lifecycle_router is not None:
        app.include_router(handover_action_lifecycle_router)
    if survey_command_router is not None:
        app.include_router(survey_command_router)
    if survey_review_submission_router is not None:
        app.include_router(survey_review_submission_router)
    if survey_read_router is not None:
        app.include_router(survey_read_router)
    if requirement_package_router is not None:
        app.include_router(requirement_package_router)
    if requirement_router is not None:
        app.include_router(requirement_router)
    if requirement_version_router is not None:
        app.include_router(requirement_version_router)
    if requirement_review_submission_router is not None:
        app.include_router(requirement_review_submission_router)
    if requirement_relation_router is not None:
        app.include_router(requirement_relation_router)
    if prototype_package_router is not None:
        app.include_router(prototype_package_router)
    if prototype_router is not None:
        app.include_router(prototype_router)
    if project_reference_create_router is not None:
        app.include_router(project_reference_create_router)
    if solution_outline_create_router is not None:
        app.include_router(solution_outline_create_router)
    if solution_outline_read_router is not None:
        app.include_router(solution_outline_read_router)
    if global_reference_create_router is not None:
        app.include_router(global_reference_create_router)
    if global_reference_read_router is not None:
        app.include_router(global_reference_read_router)
    if global_reference_list_router is not None:
        app.include_router(global_reference_list_router)
    if project_reference_read_router is not None:
        app.include_router(project_reference_read_router)
    if project_reference_list_router is not None:
        app.include_router(project_reference_list_router)
    if reference_deidentification_router is not None:
        app.include_router(reference_deidentification_router)
    if prototype_template_router is not None:
        app.include_router(prototype_template_router)
    if prototype_version_router is not None:
        app.include_router(prototype_version_router)
    if prototype_review_submission_router is not None:
        app.include_router(prototype_review_submission_router)
    if requirement_prototype_link_router is not None:
        app.include_router(requirement_prototype_link_router)
    if review_command_router is not None:
        app.include_router(review_command_router)
    return app
