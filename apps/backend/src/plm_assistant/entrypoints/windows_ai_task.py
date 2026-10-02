"""Closed-by-default Windows composition for project AI Task submission HTTP."""

from __future__ import annotations

from fastapi import APIRouter

from plm_assistant.entrypoints.ai_document_input_owner import DocumentVersionAIInputOwner
from plm_assistant.modules.ai.api.create_task import create_ai_task_create_router
from plm_assistant.modules.ai.application.create_task import AITaskCreateService
from plm_assistant.modules.ai.application.egress_authorization_owner import (
    AITaskEgressPurposeRegistry, EgressAuthorizationOwner,
)
from plm_assistant.modules.ai.application.input_resolution import AIInputVersionResolver
from plm_assistant.modules.ai.application.task_submission_policy import (
    AITaskPromptOwner, AITaskSubmissionPolicyRegistry,
)
from plm_assistant.modules.ai.infrastructure.egress_authorization_owner_repository import (
    SqlAlchemyEgressAuthorizationOwnerRepository,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import (
    SqlAlchemyAITaskCreateRepository,
)
from plm_assistant.modules.ai.infrastructure.task_prompt_repository import (
    SqlAlchemyAITaskPromptCurrentRepository,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionService
from plm_assistant.modules.auth.infrastructure.egress_access import SqlAlchemyEgressAccess
from plm_assistant.modules.audit.application.public import AuditService
from plm_assistant.modules.document.application.read_documents import DocumentReadService
from plm_assistant.modules.platform.infrastructure.database import DatabaseRuntime
from plm_assistant.modules.platform.infrastructure.idempotency_receipts import (
    SqlAlchemyIdempotencyReceipts,
)
from plm_assistant.modules.project.application.authorization import ProjectAuthorizationService
from plm_assistant.modules.project.infrastructure.authorization_repository import (
    SqlAlchemyProjectAuthorizationRepository,
)


class WindowsAITaskStartupError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("Windows AI Task submission unavailable")


def create_windows_ai_task_router(
    *, runtime: DatabaseRuntime, sessions: SessionService, origins: LoginOriginPolicy,
    license_guard: object, audit: AuditService, documents: DocumentReadService,
    task_policies: AITaskSubmissionPolicyRegistry,
    egress_purposes: AITaskEgressPurposeRegistry,
) -> APIRouter:
    """Build Task submission only when all trust and policy sources are explicit."""
    try:
        if (type(runtime) is not DatabaseRuntime
                or type(sessions) is not SessionService
                or type(origins) is not LoginOriginPolicy
                or type(audit) is not AuditService
                or type(documents) is not DocumentReadService
                or type(task_policies) is not AITaskSubmissionPolicyRegistry
                or type(egress_purposes) is not AITaskEgressPurposeRegistry
                or license_guard is None):
            raise WindowsAITaskStartupError()
        service = AITaskCreateService(
            unit_of_work=runtime.unit_of_work,
            access=SqlAlchemyEgressAccess(),
            license_guard=license_guard,
            authorization=ProjectAuthorizationService(
                unit_of_work=runtime.unit_of_work,
                repository=SqlAlchemyProjectAuthorizationRepository(),
            ),
            input_resolver=AIInputVersionResolver({
                "DOC-02": DocumentVersionAIInputOwner(documents),
            }),
            egress_owner=EgressAuthorizationOwner(
                repository=SqlAlchemyEgressAuthorizationOwnerRepository(),
                purposes=egress_purposes,
            ),
            task_policies=task_policies,
            prompt_owner=AITaskPromptOwner(SqlAlchemyAITaskPromptCurrentRepository()),
            repository=SqlAlchemyAITaskCreateRepository(),
            receipts=SqlAlchemyIdempotencyReceipts(),
            audit=audit,
        )
        return create_ai_task_create_router(
            sessions=sessions, tasks=service, origins=origins,
        )
    except WindowsAITaskStartupError:
        raise
    except Exception:
        raise WindowsAITaskStartupError() from None
