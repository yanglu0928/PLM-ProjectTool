"""Atomic fixed-definition insert, without owning Project authorization."""
import uuid

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from plm_assistant.modules.workflow.application.initialize import InitializedWorkflow
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.definition import WorkflowDefinition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.infrastructure.orm import (
    ProjectWorkflowRow, StageRow, StageChecklistRow, ChecklistItemRow,
)


class SqlAlchemyWorkflowInitializationRepository:
    def initialize(self, transaction: object, *, project_id: uuid.UUID,
                   actor_id: uuid.UUID, definition: WorkflowDefinition) -> InitializedWorkflow:
        if (any(type(value) is not uuid.UUID or value.int == 0 for value in (project_id, actor_id))
                or type(definition) is not WorkflowDefinition
                or definition != six_stage_definition(1)):
            raise ValueError("supported fixed Workflow definition required")
        session = transaction.session
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Workflow transaction required")
        fingerprint = definition_fingerprint(definition)
        workflow_id = session.execute(pg_insert(ProjectWorkflowRow).values(
            project_id=project_id, workflow_version=definition.version,
            definition_fingerprint=fingerprint, created_by=actor_id,
        ).on_conflict_do_nothing(
            constraint="uq_wfl_workflows__project",
        ).returning(ProjectWorkflowRow.workflow_id)).scalar_one_or_none()
        if workflow_id is None:
            existing = session.execute(select(
                ProjectWorkflowRow.workflow_id, ProjectWorkflowRow.workflow_version,
                ProjectWorkflowRow.definition_fingerprint,
            ).where(ProjectWorkflowRow.project_id == project_id)).one_or_none()
            if (existing is None or existing.workflow_version != definition.version
                    or bytes(existing.definition_fingerprint) != fingerprint):
                raise RuntimeError("existing Workflow definition mismatch")
            return InitializedWorkflow(existing.workflow_id, False)
        for stage in definition.stages:
            stage_id = session.execute(insert(StageRow).values(
                workflow_id=workflow_id, project_id=project_id, stage_key=stage.stage_key,
                stage_order=stage.order, gate_policy_ref=stage.gate_policy_ref,
            ).returning(StageRow.stage_id)).scalar_one()
            checklist_id = session.execute(insert(StageChecklistRow).values(
                workflow_id=workflow_id, project_id=project_id, stage_id=stage_id,
            ).returning(StageChecklistRow.stage_checklist_id)).scalar_one()
            session.execute(insert(ChecklistItemRow), [dict(
                workflow_id=workflow_id, project_id=project_id, stage_checklist_id=checklist_id,
                item_key=item.item_key, required=item.required,
                evidence_policy_ref=item.evidence_policy_ref, review_policy_ref=item.review_policy_ref,
            ) for item in stage.checklist_items])
        return InitializedWorkflow(workflow_id, True)
