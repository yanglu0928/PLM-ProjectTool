"""Safe PostgreSQL AI Task metadata projection."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import and_, or_, select

from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView,
    AITaskListCandidates,
    AITaskReadError,
    AITaskView,
)
from plm_assistant.modules.ai.infrastructure.task_create_repository import _session
from plm_assistant.modules.ai.infrastructure.task_orm import (
    AIEgressAuthorizationSnapshotRow, AITaskInputRefRow, AITaskRow,
)


class SqlAlchemyAITaskReadRepository:
    def get(self, transaction: object, *, ai_task_id: uuid.UUID,
            project_id: uuid.UUID) -> AITaskView | None:
        if any(type(value) is not uuid.UUID or not value.int
               for value in (ai_task_id, project_id)):
            return None
        session = _session(transaction)
        row = session.execute(select(
            AITaskRow.ai_task_id, AITaskRow.project_id, AITaskRow.task_type,
            AITaskRow.requested_by, AITaskRow.prompt_policy_ref,
            AITaskRow.prompt_policy_version, AITaskRow.prompt_template_ref,
            AITaskRow.prompt_version_no, AITaskRow.output_schema_ref,
            AITaskRow.context_policy_ref, AITaskRow.task_state,
            AITaskRow.suggestion_state, AITaskRow.current_invocation_ref,
            AITaskRow.job_ref, AITaskRow.trace_id, AITaskRow.error_code,
            AITaskRow.retryable, AITaskRow.lock_version, AITaskRow.requested_at,
            AITaskRow.started_at, AITaskRow.completed_at,
        ).where(
            AITaskRow.ai_task_id == ai_task_id,
            AITaskRow.scope == "PROJECT", AITaskRow.project_id == project_id,
        ).execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None
        inputs = session.execute(select(
            AITaskInputRefRow.owner_module, AITaskInputRefRow.object_type,
            AITaskInputRefRow.object_id, AITaskInputRefRow.version_id,
        ).where(
            AITaskInputRefRow.ai_task_id == ai_task_id,
            AITaskInputRefRow.scope == "PROJECT",
            AITaskInputRefRow.project_id == project_id,
        ).order_by(AITaskInputRefRow.ref_ordinal)
          .execution_options(autoflush=False)).all()
        public_inputs: list[AITaskInputView] = []
        for item in inputs:
            if (item.owner_module, item.object_type) != ("document", "DOCUMENT_VERSION"):
                return None
            if type(item.object_id) is not uuid.UUID:
                return None
            public_inputs.append(AITaskInputView("DOC-02", item.object_id, item.version_id))
        authorization_ref = session.execute(select(
            AIEgressAuthorizationSnapshotRow.authorization_ref,
        ).where(
            AIEgressAuthorizationSnapshotRow.ai_task_id == ai_task_id,
            AIEgressAuthorizationSnapshotRow.scope == "PROJECT",
            AIEgressAuthorizationSnapshotRow.project_id == project_id,
        ).execution_options(autoflush=False)).scalar_one_or_none()
        return AITaskView(
            row.ai_task_id, row.project_id, row.task_type, row.requested_by,
            tuple(public_inputs), row.prompt_policy_ref, row.prompt_policy_version,
            row.prompt_template_ref, row.prompt_version_no, row.output_schema_ref,
            row.context_policy_ref, authorization_ref, row.task_state,
            row.suggestion_state, row.current_invocation_ref, row.job_ref,
            row.trace_id, row.error_code, row.retryable, row.lock_version,
            row.requested_at, row.started_at, row.completed_at,
        )

    def list_page(
        self, transaction: object, *, project_id: uuid.UUID,
        requested_by: uuid.UUID | None,
        before: tuple[datetime, uuid.UUID] | None, limit: int,
    ) -> AITaskListCandidates:
        if (type(project_id) is not uuid.UUID or not project_id.int
                or requested_by is not None and (
                    type(requested_by) is not uuid.UUID or not requested_by.int)
                or type(limit) is not int or not 1 <= limit <= 100
                or before is not None and (
                    type(before) is not tuple or len(before) != 2
                    or not isinstance(before[0], datetime)
                    or before[0].tzinfo is None or before[0].utcoffset() is None
                    or type(before[1]) is not uuid.UUID or not before[1].int)):
            raise AITaskReadError()
        session = _session(transaction)
        statement = select(
            AITaskRow.ai_task_id, AITaskRow.project_id, AITaskRow.task_type,
            AITaskRow.requested_by, AITaskRow.prompt_policy_ref,
            AITaskRow.prompt_policy_version, AITaskRow.prompt_template_ref,
            AITaskRow.prompt_version_no, AITaskRow.output_schema_ref,
            AITaskRow.context_policy_ref, AITaskRow.task_state,
            AITaskRow.suggestion_state, AITaskRow.current_invocation_ref,
            AITaskRow.job_ref, AITaskRow.trace_id, AITaskRow.error_code,
            AITaskRow.retryable, AITaskRow.lock_version, AITaskRow.requested_at,
            AITaskRow.started_at, AITaskRow.completed_at,
        ).where(
            AITaskRow.scope == "PROJECT", AITaskRow.project_id == project_id,
        )
        if requested_by is not None:
            statement = statement.where(AITaskRow.requested_by == requested_by)
        if before is not None:
            statement = statement.where(or_(
                AITaskRow.requested_at < before[0],
                and_(AITaskRow.requested_at == before[0],
                     AITaskRow.ai_task_id < before[1]),
            ))
        rows = session.execute(
            statement.order_by(
                AITaskRow.requested_at.desc(), AITaskRow.ai_task_id.desc(),
            ).limit(limit + 1).execution_options(autoflush=False)
        ).all()
        has_more = len(rows) > limit
        rows = rows[:limit]
        if not rows:
            return AITaskListCandidates((), False)
        task_ids = tuple(row.ai_task_id for row in rows)
        input_rows = session.execute(select(
            AITaskInputRefRow.ai_task_id, AITaskInputRefRow.ref_ordinal,
            AITaskInputRefRow.owner_module, AITaskInputRefRow.object_type,
            AITaskInputRefRow.object_id, AITaskInputRefRow.version_id,
        ).where(
            AITaskInputRefRow.ai_task_id.in_(task_ids),
            AITaskInputRefRow.scope == "PROJECT",
            AITaskInputRefRow.project_id == project_id,
        ).order_by(
            AITaskInputRefRow.ai_task_id, AITaskInputRefRow.ref_ordinal,
        ).execution_options(autoflush=False)).all()
        inputs: dict[uuid.UUID, list[AITaskInputView]] = {
            task_id: [] for task_id in task_ids
        }
        for item in input_rows:
            if ((item.owner_module, item.object_type)
                    != ("document", "DOCUMENT_VERSION")
                    or item.ai_task_id not in inputs
                    or type(item.object_id) is not uuid.UUID
                    or type(item.version_id) is not uuid.UUID):
                raise AITaskReadError()
            inputs[item.ai_task_id].append(AITaskInputView(
                "DOC-02", item.object_id, item.version_id,
            ))
        authorization_rows = session.execute(select(
            AIEgressAuthorizationSnapshotRow.ai_task_id,
            AIEgressAuthorizationSnapshotRow.authorization_ref,
        ).where(
            AIEgressAuthorizationSnapshotRow.ai_task_id.in_(task_ids),
            AIEgressAuthorizationSnapshotRow.scope == "PROJECT",
            AIEgressAuthorizationSnapshotRow.project_id == project_id,
        ).execution_options(autoflush=False)).all()
        authorizations: dict[uuid.UUID, uuid.UUID] = {}
        for item in authorization_rows:
            if (item.ai_task_id not in inputs
                    or item.ai_task_id in authorizations):
                raise AITaskReadError()
            authorizations[item.ai_task_id] = item.authorization_ref
        views = tuple(AITaskView(
            row.ai_task_id, row.project_id, row.task_type, row.requested_by,
            tuple(inputs[row.ai_task_id]), row.prompt_policy_ref,
            row.prompt_policy_version, row.prompt_template_ref,
            row.prompt_version_no, row.output_schema_ref,
            row.context_policy_ref, authorizations.get(row.ai_task_id),
            row.task_state, row.suggestion_state, row.current_invocation_ref,
            row.job_ref, row.trace_id, row.error_code, row.retryable,
            row.lock_version, row.requested_at, row.started_at, row.completed_at,
        ) for row in rows)
        return AITaskListCandidates(views, has_more)
