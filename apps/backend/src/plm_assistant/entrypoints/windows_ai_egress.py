"""Closed-by-default Windows composition for project Egress approval HTTP."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from plm_assistant.entrypoints.ai_document_content_owner import AIDocumentContentOwner
from plm_assistant.entrypoints.ai_document_input_owner import DocumentVersionAIInputOwner
from plm_assistant.modules.ai.api.egress import create_ai_egress_router
from plm_assistant.modules.ai.application.egress_authorization import (
    EgressApprovalPolicyPort,
    EgressAuthorizationService,
)
from plm_assistant.modules.ai.application.egress_preview import (
    EgressPreviewPolicyRegistry,
    EgressPreviewService,
)
from plm_assistant.modules.ai.application.egress_task_plan import (
    AIExecutionPreviewPlanBuilder,
)
from plm_assistant.modules.ai.application.execution_content_plan_owner import (
    AIExecutionContentPlanOwner,
)
from plm_assistant.modules.ai.application.execution_envelope import (
    AIExecutionContextPolicyRegistry,
    AIExecutionEnvelopeBuilder,
    AIExecutionTokenEstimatorRegistry,
    Utf8ByteUpperBoundTokenEstimator,
)
from plm_assistant.modules.ai.application.execution_prompt_content import (
    AIExecutionPromptPlanningOwner,
    StrictAIExecutionPromptRenderer,
)
from plm_assistant.modules.ai.application.input_resolution import AIInputVersionResolver
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_repository import (
    SqlAlchemyEgressAuthorizationRepository,
)
from plm_assistant.modules.ai.infrastructure.egress_preview_repository import (
    SqlAlchemyEgressPreviewRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_content_plan_repository import (
    SqlAlchemyAIExecutionContentPlanRepository,
)
from plm_assistant.modules.ai.infrastructure.execution_prompt_planning_repository import (
    SqlAlchemyAIExecutionPromptPlanningRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.egress_access import SqlAlchemyEgressAccess
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.document.application.ai_content import DocumentAIContentService
from plm_assistant.modules.document.infrastructure.ai_content_repository import (
    SqlAlchemyDocumentAIContentRepository,
)
from plm_assistant.modules.document.infrastructure.parse_result_storage import (
    LocalParseResultStorage,
)
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class WindowsAIEgressStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI Egress approval unavailable")


def create_windows_ai_egress_router(
    *, runtime: DatabaseRuntime, sessions: SessionService, origins: LoginOriginPolicy,
    license_guard: object, audit: AuditService, documents: DocumentReadService,
    preview_policies: EgressPreviewPolicyRegistry,
    approval_policy: EgressApprovalPolicyPort,
    task_policies: AITaskSubmissionPolicyRegistry | None = None,
    data_root: Path | None = None,
) -> APIRouter:
    """Build the router only when every trust, Owner and deployment policy is explicit."""
    try:
        if (type(runtime) is not DatabaseRuntime
                or type(sessions) is not SessionService
                or type(origins) is not LoginOriginPolicy
                or type(audit) is not AuditService
                or type(documents) is not DocumentReadService
                or type(preview_policies) is not EgressPreviewPolicyRegistry
                or any(value is None for value in (license_guard, approval_policy))):
            raise WindowsAIEgressStartupError()
        access = SqlAlchemyEgressAccess()
        authorization = ProjectAuthorizationService(
            unit_of_work=runtime.unit_of_work,
            repository=SqlAlchemyProjectAuthorizationRepository(),
        )
        receipts = SqlAlchemyIdempotencyReceipts()
        task_plan_builder = None
        content_plan_owner = None
        if task_policies is not None or data_root is not None:
            if (type(task_policies) is not AITaskSubmissionPolicyRegistry
                    or not isinstance(data_root, Path) or not data_root.is_absolute()):
                raise WindowsAIEgressStartupError()
            document_content_owner = AIDocumentContentOwner(DocumentAIContentService(
                repository=SqlAlchemyDocumentAIContentRepository(),
                storage=LocalParseResultStorage(data_root),
                projects=authorization, license_guard=license_guard,
            ))
            task_plan_builder = AIExecutionPreviewPlanBuilder(
                task_policies=task_policies,
                prompt_owner=AIExecutionPromptPlanningOwner(
                    SqlAlchemyAIExecutionPromptPlanningRepository(),
                ),
                source_owners={"DOC-02": document_content_owner},
                envelope_builder=AIExecutionEnvelopeBuilder(
                    renderer=StrictAIExecutionPromptRenderer(),
                    context_policies=AIExecutionContextPolicyRegistry(
                        frozenset({"no-retrieval.v1"}),
                    ),
                    token_estimators=AIExecutionTokenEstimatorRegistry((
                        Utf8ByteUpperBoundTokenEstimator(),
                    )),
                ),
            )
            content_plan_owner = AIExecutionContentPlanOwner(
                SqlAlchemyAIExecutionContentPlanRepository(),
            )
        previews = EgressPreviewService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            input_resolver=AIInputVersionResolver({
                "DOC-02": DocumentVersionAIInputOwner(documents),
            }),
            policies=preview_policies,
            repository=SqlAlchemyEgressPreviewRepository(), receipts=receipts,
            audit=audit, task_plan_builder=task_plan_builder,
            content_plan_owner=content_plan_owner,
        )
        authorizations = EgressAuthorizationService(
            unit_of_work=runtime.unit_of_work, access=access,
            license_guard=license_guard, authorization=authorization,
            approval_policy=approval_policy,
            repository=SqlAlchemyEgressAuthorizationRepository(), receipts=receipts,
            audit=audit,
        )
        return create_ai_egress_router(
            sessions=sessions, previews=previews, authorizations=authorizations,
            origins=origins,
        )
    except WindowsAIEgressStartupError:
        raise
    except Exception:
        raise WindowsAIEgressStartupError() from None
