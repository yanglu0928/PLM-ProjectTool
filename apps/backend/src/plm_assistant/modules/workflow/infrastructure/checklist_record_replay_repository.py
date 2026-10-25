"""Read one immutable Checklist result after validating the current full chain."""

from __future__ import annotations

import uuid
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.workflow.application.checklist_record_integrity import (
    checklist_record_fingerprint,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation, ChecklistRecordReadError,
    CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState

from .checklist_record_orm import ChecklistRecordRefRow, ChecklistRecordRow
from .current_checklist_repository import (
    SqlAlchemyCurrentChecklistRecordRepository,
)


class SqlAlchemyChecklistRecordReplayRepository:
    def __init__(
        self, *, current: SqlAlchemyCurrentChecklistRecordRepository | None = None,
    ) -> None:
        self._current = current or SqlAlchemyCurrentChecklistRecordRepository()

    def get_record(
        self, transaction: object, *, project_id: uuid.UUID,
        item_key: str, record_id: uuid.UUID,
    ) -> CurrentChecklistRecord | None:
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise ChecklistRecordReadError()
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(item_key) is not str
                or type(record_id) is not uuid.UUID or record_id.int == 0):
            raise ChecklistRecordReadError()
        root_table = ChecklistRecordRow.__table__
        identity = session.execute(select(
            root_table.c.workflow_id,
        ).where(
            root_table.c.record_id == record_id,
            root_table.c.project_id == project_id,
            root_table.c.item_key == item_key,
        )).scalar_one_or_none()
        if identity is None:
            return None
        current = self._current.get(
            transaction, project_id, identity, item_key,
        )
        if type(current) is not CurrentChecklistRecord:
            raise ChecklistRecordReadError()
        if current.record.record_id == record_id:
            return current
        root = session.execute(select(root_table).where(
            root_table.c.record_id == record_id,
            root_table.c.workflow_id == identity,
            root_table.c.project_id == project_id,
            root_table.c.item_key == item_key,
        )).mappings().one_or_none()
        if (root is None
                or root["after_item_version"] >= current.record.after_item_version):
            raise ChecklistRecordReadError()
        ref_table = ChecklistRecordRefRow.__table__
        refs = session.execute(select(ref_table).where(
            ref_table.c.record_id == record_id,
            ref_table.c.workflow_id == identity,
            ref_table.c.project_id == project_id,
            ref_table.c.item_key == item_key,
        ).order_by(
            ref_table.c.ref_kind, ref_table.c.ref_id,
        )).mappings().all()
        try:
            basis = tuple(ChecklistBasisObservation(
                ref["ref_kind"], ref["ref_id"], ref["ref_scope"],
                ref["ref_project_id"], ref["observed_state"],
                ref["observed_lock_version"],
                bytes(ref["content_fingerprint"]),
                ref["verified_at"].astimezone(timezone.utc),
                ref["proof_schema_version"],
            ) for ref in refs)
            snapshot = ChecklistRecordSnapshot(
                record_id=root["record_id"], workflow_id=identity,
                project_id=project_id, actor_id=root["actor_id"],
                trace_id=root["trace_id"],
                definition_version=root["definition_version"],
                stage_key=root["stage_key"], item_key=item_key,
                before_state=ChecklistState(root["before_state"]),
                result=ChecklistState(root["result"]),
                before_item_version=root["before_item_version"],
                after_item_version=root["after_item_version"],
                before_workflow_version=root["before_workflow_version"],
                after_workflow_version=root["after_workflow_version"],
                occurred_at=root["occurred_at"].astimezone(timezone.utc),
                supersedes_record_id=root["supersedes_record_id"],
                evidence_refs=tuple(
                    value.ref_id for value in basis
                    if value.ref_kind == "EVIDENCE"
                ),
                review_round_refs=tuple(
                    value.ref_id for value in basis
                    if value.ref_kind == "REVIEW_ROUND"
                ),
                exception_refs=tuple(
                    value.ref_id for value in basis
                    if value.ref_kind == "APPROVED_EXCEPTION"
                ),
                reason=root["reason"], impact=root["impact"],
            )
            fingerprint = bytes(root["content_fingerprint"])
            if fingerprint != checklist_record_fingerprint(
                    snapshot, basis, root["observed_stage_state"]):
                raise ChecklistRecordReadError()
            return CurrentChecklistRecord(
                snapshot, basis, fingerprint,
                root["observed_stage_state"],
                current.current_workflow_version,
            )
        except ChecklistRecordReadError:
            raise
        except (TypeError, ValueError):
            raise ChecklistRecordReadError() from None
