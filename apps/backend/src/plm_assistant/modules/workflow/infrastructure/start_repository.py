"""Atomic first-stage activation inside a caller-authorized Workflow transaction."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.workflow.application.read_workflow import WorkflowView
from plm_assistant.modules.workflow.application.start_errors import WorkflowStartRepositoryError
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.infrastructure.orm import ProjectWorkflowRow, StageRow
from plm_assistant.modules.workflow.infrastructure.read_repository import SqlAlchemyWorkflowReadRepository


class SqlAlchemyWorkflowStartRepository:
    """Does not authorize, audit, commit, initialize or evaluate any Gate."""

    def __init__(self, *, reader: SqlAlchemyWorkflowReadRepository | None = None) -> None:
        self._reader = reader or SqlAlchemyWorkflowReadRepository()

    def start(self, transaction: object, *, project_id: uuid.UUID,
              expected_version: int) -> WorkflowView:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(expected_version) is not int or not 0 <= expected_version < 2**63):
            raise WorkflowStartRepositoryError("VALIDATION_FAILED")
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise WorkflowStartRepositoryError("WORKFLOW_UNAVAILABLE")

        root = session.execute(select(ProjectWorkflowRow).where(
            ProjectWorkflowRow.project_id == project_id,
        ).with_for_update()).scalar_one_or_none()
        if root is None:
            raise WorkflowStartRepositoryError("RESOURCE_NOT_FOUND")
        if root.lock_version != expected_version:
            raise WorkflowStartRepositoryError("CONFLICT_VERSION")
        if root.workflow_state != "NOT_STARTED" or root.current_stage_key is not None:
            raise WorkflowStartRepositoryError("CONFLICT_STATE")
        definition = six_stage_definition(1)
        first_key = definition.stages[0].stage_key
        if (root.workflow_version != definition.version
                or bytes(root.definition_fingerprint) != definition_fingerprint(definition)):
            raise WorkflowStartRepositoryError("WORKFLOW_UNAVAILABLE")
        before = self._reader.get(transaction, project_id)
        if (type(before) is not WorkflowView or before.workflow_id != root.workflow_id
                or before.project_id != project_id or before.state != "NOT_STARTED"
                or before.lock_version != expected_version):
            raise WorkflowStartRepositoryError("WORKFLOW_UNAVAILABLE")

        stage_id = session.execute(update(StageRow).where(
            StageRow.workflow_id == root.workflow_id,
            StageRow.project_id == project_id,
            StageRow.stage_key == first_key,
            StageRow.stage_state == "NOT_STARTED",
        ).values(stage_state="ACTIVE").returning(StageRow.stage_id)).scalar_one_or_none()
        if stage_id is None:
            raise WorkflowStartRepositoryError("WORKFLOW_UNAVAILABLE")
        changed = session.execute(update(ProjectWorkflowRow).where(
            ProjectWorkflowRow.workflow_id == root.workflow_id,
            ProjectWorkflowRow.project_id == project_id,
            ProjectWorkflowRow.workflow_state == "NOT_STARTED",
            ProjectWorkflowRow.current_stage_key.is_(None),
            ProjectWorkflowRow.lock_version == expected_version,
        ).values(workflow_state="ACTIVE", current_stage_key=first_key,
                 lock_version=expected_version + 1, updated_at=func.statement_timestamp()
        ).returning(ProjectWorkflowRow.workflow_id)).scalar_one_or_none()
        if changed != root.workflow_id:
            raise WorkflowStartRepositoryError("CONFLICT_VERSION")
        session.expire_all()
        after = self._reader.get(transaction, project_id)
        if (type(after) is not WorkflowView or after.workflow_id != root.workflow_id
                or after.state != "ACTIVE" or after.current_stage != first_key
                or after.lock_version != expected_version + 1):
            raise WorkflowStartRepositoryError("WORKFLOW_UNAVAILABLE")
        return after
