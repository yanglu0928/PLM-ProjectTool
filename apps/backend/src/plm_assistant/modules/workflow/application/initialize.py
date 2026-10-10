"""Internal caller-transaction bootstrap; not a user authorization entry point."""
import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.definition import WorkflowDefinition


@dataclass(frozen=True, slots=True)
class InitializedWorkflow:
    workflow_id: uuid.UUID
    inserted: bool


class WorkflowInitializationRepositoryPort(Protocol):
    def initialize(self, transaction: object, *, project_id: uuid.UUID,
                   actor_id: uuid.UUID, definition: WorkflowDefinition) -> InitializedWorkflow: ...


class WorkflowInitializationService:
    """Caller must authorize Project operation/License in this transaction.

    Only initializes NOT_STARTED facts; never infers stage progress. No commit
    here, so caller's Project creation/receipt/Audit can succeed or roll back
    together. Must not be bound directly to a user request or backfill command.
    """
    def __init__(self, *, repository: WorkflowInitializationRepositoryPort,
                 audit: AuditService) -> None:
        if repository is None or audit is None:
            raise ValueError("Workflow initialization dependencies required")
        self._repository, self._audit = repository, audit

    def initialize_in_transaction(self, transaction: object, *, project_id: uuid.UUID,
                                  actor_id: uuid.UUID, trace_id: uuid.UUID) -> uuid.UUID:
        if transaction is None or any(type(value) is not uuid.UUID or value.int == 0
                                      for value in (project_id, actor_id, trace_id)):
            raise ValueError("validated Workflow initialization identity required")
        result = self._repository.initialize(
            transaction, project_id=project_id, actor_id=actor_id,
            definition=six_stage_definition(1),
        )
        if (type(result) is not InitializedWorkflow
                or type(result.workflow_id) is not uuid.UUID or result.workflow_id.int == 0
                or type(result.inserted) is not bool):
            raise RuntimeError("Workflow initialization result invalid")
        if result.inserted:
            self._audit.append(transaction, AuditEventDraft(
                trace_id=trace_id, event_scope="PROJECT", target_project_id=project_id,
                actor_type="USER", actor_id=actor_id, original_actor_id=None,
                actor_hint_digest=None, action="WORKFLOW_INITIALIZED", outcome="SUCCESS",
                target_owner_module="workflow", target_object_type="WFL-01",
                target_object_id=result.workflow_id, after_state="NOT_STARTED",
            ))
        return result.workflow_id
