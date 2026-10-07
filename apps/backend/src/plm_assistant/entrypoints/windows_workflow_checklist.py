"""Fail-closed Windows composition for Workflow Checklist recording."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.modules.ai.infrastructure.task_read_repository import (
    SqlAlchemyAITaskReadRepository,
)
from plm_assistant.modules.ai.infrastructure.survey_conclusion_task import (
    SqlAlchemySurveyConclusionAITaskProof,
)
from plm_assistant.modules.auth.infrastructure.project_read_access import (
    SqlAlchemyProjectReadAccess,
)
from plm_assistant.modules.auth.infrastructure.project_write_access import (
    SqlAlchemyProjectWriteAccess,
)
from plm_assistant.modules.capability.infrastructure.read_repository import (
    SqlAlchemyCapabilityReadRepository,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    DocumentFixedSourceProofService,
)
from plm_assistant.modules.document.infrastructure.parse_result_read_repository import (
    SqlAlchemyParseResultReadRepository,
)
from plm_assistant.modules.document.infrastructure.read_repository import (
    SqlAlchemyDocumentReadRepository,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectSourceService,
)
from plm_assistant.modules.evidence.infrastructure.fixed_source_repository import (
    SqlAlchemyEvidenceFixedSourceRepository,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverSourceValidator,
)
from plm_assistant.modules.handover.application.workflow_qualification_owner import (
    HandoverWorkflowQualificationOwner,
)
from plm_assistant.modules.handover.infrastructure.survey_conclusion_issue import (
    SqlAlchemySurveyConclusionIssueProof,
)
from plm_assistant.modules.handover.infrastructure.workflow_qualification_repository import (
    SqlAlchemyHandoverWorkflowQualificationRepository,
)
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationService,
)
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)
from plm_assistant.modules.review.infrastructure.read_repository import (
    SqlAlchemyReviewSnapshotReadRepository,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    SurveyConclusionProjectRecordProofService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionCurrentValidator,
)
from plm_assistant.modules.survey.application.workflow_qualification import (
    SurveyWorkflowQualificationOwner,
)
from plm_assistant.modules.survey.infrastructure.conclusion_response_source import (
    SqlAlchemyConclusionResponseProof,
)
from plm_assistant.modules.survey.infrastructure.workflow_qualification_repository import (
    SqlAlchemySurveyWorkflowQualificationRepository,
)
from plm_assistant.modules.trace.application.resolution_proof import (
    TraceResolutionProofService,
)
from plm_assistant.modules.trace.application.target_proof import TraceTargetProofService
from plm_assistant.modules.trace.infrastructure.resolution_repository import (
    SqlAlchemyTraceResolutionRepository,
)
from plm_assistant.modules.workflow.api.record_checklist import (
    create_workflow_checklist_record_router,
)
from plm_assistant.modules.workflow.api.qualification_preview import (
    create_workflow_checklist_qualification_router,
)
from plm_assistant.modules.workflow.api.transition_stage import (
    create_workflow_stage_transition_router,
)
from plm_assistant.modules.workflow.application.preview_checklist_qualification import (
    WorkflowChecklistQualificationPreviewService,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationRegistration,
    ChecklistQualificationRegistry,
)
from plm_assistant.modules.workflow.application.handover_qualification_adapter import (
    HandoverChecklistQualificationAdapter,
)
from plm_assistant.modules.workflow.application.record_checklist import (
    WorkflowChecklistRecordService,
)
from plm_assistant.modules.workflow.application.transition_stage import (
    WorkflowStageTransitionService,
)
from plm_assistant.modules.workflow.infrastructure.checklist_record_append_repository import (
    SqlAlchemyChecklistRecordAppendRepository,
)
from plm_assistant.modules.workflow.infrastructure.checklist_record_replay_repository import (
    SqlAlchemyChecklistRecordReplayRepository,
)
from plm_assistant.modules.workflow.infrastructure.read_repository import (
    SqlAlchemyWorkflowReadRepository,
)
from plm_assistant.modules.workflow.infrastructure.stage_transition_repository import (
    SqlAlchemyStageTransitionRepository,
)


class ProductionWorkflowChecklistStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Workflow Checklist composition unavailable")


def _create_handover_qualification(
    *, documents, downloads, parse_results,
    project_repository=None, target_proofs=None,
):
    if project_repository is None:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
    if target_proofs is None:
        target_proofs = TraceTargetProofService({})
    document_proofs = DocumentFixedSourceProofService(
        documents=documents,
        downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results,
    )
    return HandoverWorkflowQualificationOwner(
        repository=SqlAlchemyHandoverWorkflowQualificationRepository(),
        sources=HandoverSourceValidator(SqlAlchemyDocumentReadRepository()),
        documents=document_proofs,
        evidence=EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=project_repository,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=document_proofs,
        ),
        capabilities=SqlAlchemyCapabilityReadRepository(),
        ai_tasks=SqlAlchemyAITaskReadRepository(),
        reviews=SqlAlchemyReviewSnapshotReadRepository(),
        trace_proofs=TraceResolutionProofService(
            SqlAlchemyTraceResolutionRepository(),
            target_proofs,
        ),
    )


def _create_qualification_registry(
    *, documents, downloads, parse_results,
    project_repository=None, target_proofs=None,
) -> ChecklistQualificationRegistry:
    """Compose the explicit Handover and Survey fact-owner allowlist."""

    if project_repository is None:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
    document_proofs = DocumentFixedSourceProofService(
        documents=documents,
        downloads=downloads,
        parse_metadata=SqlAlchemyParseResultReadRepository(),
        parse_results=parse_results,
    )
    survey_project_records = SurveyConclusionProjectRecordProofService(
        evidence=EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=project_repository,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=document_proofs,
            allowed_project_roles=frozenset({"PROJECT_MANAGER"}),
            required_document_category="PROJECT_RECORD",
        ),
        allowed_verified_roles=frozenset({"PROJECT_MANAGER"}),
    )
    survey = SurveyWorkflowQualificationOwner(
        repository=SqlAlchemySurveyWorkflowQualificationRepository(),
        current=SurveyConclusionCurrentValidator(
            response_owner=SqlAlchemyConclusionResponseProof(),
            evidence_owner=survey_project_records,
            issue_owner=SqlAlchemySurveyConclusionIssueProof(),
            ai_owner=SqlAlchemySurveyConclusionAITaskProof(),
        ),
        responses=SqlAlchemyConclusionResponseProof(),
        evidence=EvidenceFixedProjectSourceService(
            sessions=SqlAlchemyProjectReadAccess(),
            projects=project_repository,
            evidence=SqlAlchemyEvidenceFixedSourceRepository(),
            documents=document_proofs,
            allowed_project_roles=frozenset({"PROJECT_MANAGER"}),
        ),
        reviews=SqlAlchemyReviewSnapshotReadRepository(),
    )
    handover = HandoverChecklistQualificationAdapter(
        _create_handover_qualification(
            documents=documents, downloads=downloads,
            parse_results=parse_results,
            project_repository=project_repository,
            target_proofs=target_proofs,
        ),
    )
    return ChecklistQualificationRegistry((
        ChecklistQualificationRegistration((
            "HANDOVER_BASELINE", "HANDOVER_ISSUES",
        ), handover),
        ChecklistQualificationRegistration((
            "SURVEY_ACTUAL_SOURCES", "SURVEY_CONCLUSION",
        ), survey),
    ))


def create_windows_workflow_checklist_record_router(
    runtime, *, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
    target_proofs: TraceTargetProofService | None = None,
) -> APIRouter:
    """Compose the frozen Checklist record endpoint with real fact owners."""

    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionWorkflowChecklistStartupError()
    try:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        qualification = _create_qualification_registry(
            documents=documents, downloads=downloads,
            parse_results=parse_results, project_repository=project_repository,
            target_proofs=target_proofs,
        )
        records = WorkflowChecklistRecordService(
            unit_of_work=runtime.unit_of_work,
            sessions=SqlAlchemyProjectWriteAccess(),
            projects=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=project_repository,
            ),
            license_guard=license_guard,
            qualification=qualification,
            appender=SqlAlchemyChecklistRecordAppendRepository(),
            replay=SqlAlchemyChecklistRecordReplayRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit,
        )
        return create_workflow_checklist_record_router(
            sessions=sessions, records=records, origins=origins,
        )
    except Exception:
        raise ProductionWorkflowChecklistStartupError() from None


def create_windows_workflow_checklist_qualification_router(
    runtime, *, sessions, origins, license_guard,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose the opt-in Checklist qualification preview with real owners."""

    if any(value is None for value in (
            runtime, sessions, origins, license_guard,
            documents, downloads, parse_results)):
        raise ProductionWorkflowChecklistStartupError()
    try:
        previews = WorkflowChecklistQualificationPreviewService(
            unit_of_work=runtime.unit_of_work,
            sessions=SqlAlchemyProjectReadAccess(),
            projects=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ),
            license_guard=license_guard,
            workflows=SqlAlchemyWorkflowReadRepository(),
            qualification=_create_qualification_registry(
                documents=documents, downloads=downloads,
                parse_results=parse_results,
            ),
        )
        return create_workflow_checklist_qualification_router(
            sessions=sessions, previews=previews, origins=origins,
        )
    except Exception:
        raise ProductionWorkflowChecklistStartupError() from None


def create_windows_workflow_stage_transition_router(
    runtime, *, sessions, origins, license_guard, audit,
    documents, downloads, parse_results,
) -> APIRouter:
    """Compose the opt-in Stage Transition endpoint with real owners."""

    if any(value is None for value in (
            runtime, sessions, origins, license_guard, audit,
            documents, downloads, parse_results)):
        raise ProductionWorkflowChecklistStartupError()
    try:
        project_repository = SqlAlchemyProjectAuthorizationRepository()
        transitions = WorkflowStageTransitionService(
            unit_of_work=runtime.unit_of_work,
            sessions=SqlAlchemyProjectWriteAccess(),
            projects=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=project_repository,
            ),
            license_guard=license_guard,
            qualification=_create_qualification_registry(
                documents=documents, downloads=downloads,
                parse_results=parse_results,
                project_repository=project_repository,
            ),
            transitions=SqlAlchemyStageTransitionRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit,
        )
        return create_workflow_stage_transition_router(
            sessions=sessions, transitions=transitions, origins=origins,
        )
    except Exception:
        raise ProductionWorkflowChecklistStartupError() from None
