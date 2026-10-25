"""Atomic immutable Checklist record append; no authorization, audit or commit."""

from __future__ import annotations

import uuid

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.workflow.application.append_checklist_record import (
    AppendChecklistRecord, ChecklistRecordAppendError,
    ChecklistRecordWriteLock,
)
from plm_assistant.modules.workflow.application.checklist_record_integrity import (
    checklist_record_fingerprint,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordSnapshot,
)
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.domain.transition import ChecklistState

from .checklist_record_orm import ChecklistRecordRefRow, ChecklistRecordRow
from .current_checklist_repository import SqlAlchemyCurrentChecklistRecordRepository
from .orm import (
    ChecklistItemRow, ProjectWorkflowRow, StageChecklistRow, StageRow,
)


class SqlAlchemyChecklistRecordAppendRepository:
    """Hold Workflow locks while a caller proves business facts then appends."""

    def __init__(self, *,
                 reader: SqlAlchemyCurrentChecklistRecordRepository | None = None
                 ) -> None:
        self._reader = reader or SqlAlchemyCurrentChecklistRecordRepository()

    def lock_current(
        self, transaction: object, *, project_id: uuid.UUID, item_key: str,
        expected_workflow_version: int,
    ) -> ChecklistRecordWriteLock:
        definition = six_stage_definition(1)
        owners = {
            item.item_key: stage.stage_key
            for stage in definition.stages for item in stage.checklist_items
        }
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(item_key) is not str or item_key not in owners
                or type(expected_workflow_version) is not int
                or not 0 <= expected_workflow_version < 2**63 - 1):
            raise ChecklistRecordAppendError("VALIDATION_FAILED")
        session = self._session(transaction)
        root = session.execute(select(ProjectWorkflowRow).where(
            ProjectWorkflowRow.project_id == project_id,
        ).with_for_update()).scalar_one_or_none()
        if root is None:
            raise ChecklistRecordAppendError("RESOURCE_NOT_FOUND")
        if root.lock_version != expected_workflow_version:
            raise ChecklistRecordAppendError("CONFLICT_VERSION")
        if (root.workflow_state != "ACTIVE"
                or root.current_stage_key != owners[item_key]
                or root.workflow_version != definition.version
                or bytes(root.definition_fingerprint)
                   != definition_fingerprint(definition)):
            raise ChecklistRecordAppendError("CONFLICT_STATE")
        stage = session.execute(select(StageRow).where(
            StageRow.workflow_id == root.workflow_id,
            StageRow.project_id == project_id,
            StageRow.stage_key == owners[item_key],
        ).with_for_update()).scalar_one_or_none()
        if stage is None:
            raise ChecklistRecordAppendError()
        stage_checklist_id = session.execute(select(
            StageChecklistRow.stage_checklist_id,
        ).where(
            StageChecklistRow.stage_id == stage.stage_id,
            StageChecklistRow.workflow_id == root.workflow_id,
            StageChecklistRow.project_id == project_id,
        )).scalar_one_or_none()
        if stage_checklist_id is None:
            raise ChecklistRecordAppendError()
        item = session.execute(select(ChecklistItemRow).where(
            ChecklistItemRow.stage_checklist_id == stage_checklist_id,
            ChecklistItemRow.workflow_id == root.workflow_id,
            ChecklistItemRow.project_id == project_id,
            ChecklistItemRow.item_key == item_key,
        ).with_for_update()).scalar_one_or_none()
        if item is None:
            raise ChecklistRecordAppendError()
        if stage.stage_state not in {"ACTIVE", "BLOCKED"}:
            raise ChecklistRecordAppendError("CONFLICT_STATE")
        try:
            state = ChecklistState(item.item_state)
        except ValueError:
            raise ChecklistRecordAppendError() from None
        previous = session.execute(select(ChecklistRecordRow).where(
            ChecklistRecordRow.workflow_id == root.workflow_id,
            ChecklistRecordRow.project_id == project_id,
            ChecklistRecordRow.item_key == item_key,
            ChecklistRecordRow.after_item_version == item.lock_version,
        ).with_for_update(read=True)).scalar_one_or_none()
        if item.lock_version == 0:
            any_record = session.execute(select(
                ChecklistRecordRow.record_id,
            ).where(
                ChecklistRecordRow.workflow_id == root.workflow_id,
                ChecklistRecordRow.project_id == project_id,
                ChecklistRecordRow.item_key == item_key,
            ).limit(1)).scalar_one_or_none()
            if state is not ChecklistState.PENDING or previous is not None \
                    or any_record is not None:
                raise ChecklistRecordAppendError()
            previous_id = None
        else:
            if previous is None or previous.result != state.value:
                raise ChecklistRecordAppendError()
            previous_id = previous.record_id
        try:
            return ChecklistRecordWriteLock(
                root.workflow_id, project_id, root.workflow_version,
                stage.stage_key, stage.stage_state, item_key, state,
                item.lock_version, root.lock_version, previous_id,
            )
        except ChecklistRecordAppendError:
            raise
        except Exception:
            raise ChecklistRecordAppendError() from None

    def append(
        self, transaction: object, *, lock: ChecklistRecordWriteLock,
        command: AppendChecklistRecord,
    ) -> CurrentChecklistRecord:
        if (type(lock) is not ChecklistRecordWriteLock
                or type(command) is not AppendChecklistRecord):
            raise ChecklistRecordAppendError("VALIDATION_FAILED")
        lock.__post_init__()
        command.__post_init__()
        session = self._session(transaction)
        if any(value.ref_scope == "PROJECT"
               and value.ref_project_id != lock.project_id
               for value in command.basis):
            raise ChecklistRecordAppendError("VALIDATION_FAILED")
        evidence = tuple(
            value.ref_id for value in command.basis
            if value.ref_kind == "EVIDENCE"
        )
        reviews = tuple(
            value.ref_id for value in command.basis
            if value.ref_kind == "REVIEW_ROUND"
        )
        exceptions = tuple(
            value.ref_id for value in command.basis
            if value.ref_kind == "APPROVED_EXCEPTION"
        )
        record_id = uuid.UUID(new_uuid7())
        try:
            snapshot = ChecklistRecordSnapshot(
                record_id, lock.workflow_id, lock.project_id,
                command.actor_id, command.trace_id,
                lock.definition_version, lock.stage_key, lock.item_key,
                lock.before_state, command.result,
                lock.before_item_version, lock.before_item_version + 1,
                lock.before_workflow_version, lock.before_workflow_version + 1,
                command.occurred_at, lock.supersedes_record_id,
                evidence, reviews, exceptions, command.reason, command.impact,
            )
            fingerprint = checklist_record_fingerprint(
                snapshot, command.basis, lock.stage_state,
            )
        except ValueError:
            raise ChecklistRecordAppendError("VALIDATION_FAILED") from None
        session.execute(insert(ChecklistRecordRow).values(
            record_id=record_id, workflow_id=lock.workflow_id,
            project_id=lock.project_id,
            definition_version=lock.definition_version,
            stage_key=lock.stage_key, item_key=lock.item_key,
            observed_stage_state=lock.stage_state,
            before_state=lock.before_state.value,
            result=command.result.value,
            before_item_version=lock.before_item_version,
            after_item_version=lock.before_item_version + 1,
            before_workflow_version=lock.before_workflow_version,
            after_workflow_version=lock.before_workflow_version + 1,
            supersedes_record_id=lock.supersedes_record_id,
            actor_id=command.actor_id, trace_id=command.trace_id,
            occurred_at=command.occurred_at,
            reason=command.reason, impact=command.impact,
            content_fingerprint=fingerprint,
        ))
        if command.basis:
            session.execute(insert(ChecklistRecordRefRow), [dict(
                record_ref_id=uuid.UUID(new_uuid7()),
                record_id=record_id, workflow_id=lock.workflow_id,
                project_id=lock.project_id, item_key=lock.item_key,
                ref_kind=value.ref_kind, ref_id=value.ref_id,
                ref_scope=value.ref_scope,
                ref_project_id=value.ref_project_id,
                observed_state=value.observed_state,
                observed_lock_version=value.observed_lock_version,
                content_fingerprint=value.content_fingerprint,
                verified_at=value.verified_at,
                proof_schema_version=value.proof_schema_version,
            ) for value in command.basis])
        item_changed = session.execute(update(ChecklistItemRow).where(
            ChecklistItemRow.workflow_id == lock.workflow_id,
            ChecklistItemRow.project_id == lock.project_id,
            ChecklistItemRow.item_key == lock.item_key,
            ChecklistItemRow.item_state == lock.before_state.value,
            ChecklistItemRow.lock_version == lock.before_item_version,
        ).values(
            item_state=command.result.value,
            lock_version=lock.before_item_version + 1,
        ).returning(ChecklistItemRow.checklist_item_id)).scalar_one_or_none()
        if item_changed is None:
            raise ChecklistRecordAppendError("CONFLICT_VERSION")
        workflow_changed = session.execute(update(ProjectWorkflowRow).where(
            ProjectWorkflowRow.workflow_id == lock.workflow_id,
            ProjectWorkflowRow.project_id == lock.project_id,
            ProjectWorkflowRow.workflow_state == "ACTIVE",
            ProjectWorkflowRow.current_stage_key == lock.stage_key,
            ProjectWorkflowRow.lock_version == lock.before_workflow_version,
        ).values(
            lock_version=lock.before_workflow_version + 1,
            updated_at=func.statement_timestamp(),
        ).returning(ProjectWorkflowRow.workflow_id)).scalar_one_or_none()
        if workflow_changed != lock.workflow_id:
            raise ChecklistRecordAppendError("CONFLICT_VERSION")
        session.expire_all()
        current = self._reader.get(
            transaction, lock.project_id, lock.workflow_id, lock.item_key,
        )
        if (type(current) is not CurrentChecklistRecord
                or current.record.record_id != record_id
                or current.content_fingerprint != fingerprint
                or current.current_workflow_version
                   != lock.before_workflow_version + 1):
            raise ChecklistRecordAppendError()
        return current

    @staticmethod
    def _session(transaction: object) -> Session:
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise ChecklistRecordAppendError("WORKFLOW_UNAVAILABLE")
        return session
