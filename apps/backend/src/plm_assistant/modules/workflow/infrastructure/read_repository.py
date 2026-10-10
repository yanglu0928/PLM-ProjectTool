"""One SQL statement projects all Workflow rows from one MVCC snapshot."""
import uuid
from itertools import groupby

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.workflow.application.read_workflow import (
    ChecklistView, StageView, WorkflowView,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.infrastructure.orm import (
    ProjectWorkflowRow as W, StageRow as S, StageChecklistRow as C, ChecklistItemRow as I,
)


class SqlAlchemyWorkflowReadRepository:
    def get(self, transaction: object, project_id: uuid.UUID) -> WorkflowView | None:
        session = transaction.session
        if not isinstance(session, Session) or not session.in_transaction():
            raise RuntimeError("active Workflow read transaction required")
        if type(project_id) is not uuid.UUID or project_id.int == 0:
            raise ValueError("validated Project identity required")
        rows = session.execute(select(W, S, I).join(
            S, (S.workflow_id == W.workflow_id) & (S.project_id == W.project_id),
        ).join(C, (C.stage_id == S.stage_id) & (C.workflow_id == S.workflow_id) & (C.project_id == S.project_id)
        ).join(I, (I.stage_checklist_id == C.stage_checklist_id) & (I.workflow_id == C.workflow_id) & (I.project_id == C.project_id)
        ).where(W.project_id == project_id).order_by(S.stage_order, I.item_key)).all()
        if not rows:
            return None
        workflow = rows[0][0]
        if (workflow.workflow_version != 1 or bytes(workflow.definition_fingerprint) != definition_fingerprint(six_stage_definition(1))):
            raise RuntimeError("unsupported Workflow snapshot definition")
        stages = []
        expected = {s.stage_key: tuple(i.item_key for i in s.checklist_items) for s in six_stage_definition(1).stages}
        for _, group in groupby(rows, key=lambda row: row[1].stage_key):
            values = list(group)
            stage = values[0][1]
            items = {row[2].item_key: ChecklistView(row[2].item_key, row[2].required, row[2].item_state) for row in values}
            order = expected.get(stage.stage_key, ())
            if set(items) != set(order) or len(values) != len(order):
                raise RuntimeError("invalid Workflow checklist snapshot")
            stages.append(StageView(stage.stage_key, stage.stage_order, stage.stage_state, tuple(items[key] for key in order)))
        return WorkflowView(workflow.workflow_id, workflow.project_id, workflow.workflow_version,
                            workflow.workflow_state, workflow.current_stage_key, tuple(stages), workflow.lock_version)
