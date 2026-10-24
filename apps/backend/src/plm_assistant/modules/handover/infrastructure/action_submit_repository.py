"""Handover-owned IN_PROGRESS to SUBMITTED persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select, update

from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.handover.application.submit_action import (
    HandoverActionSubmitError, HandoverActionSubmitLock,
    HandoverActionSubmitView, SubmitHandoverAction,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import (
    HandoverActionEvidenceRefRow, HandoverActionItemRow,
    HandoverActionResponseRefRow, HandoverActionStateEventRow,
)


class SqlAlchemyHandoverActionSubmitRepository:
    @staticmethod
    def _allowed(row, actor_id, actor_role):
        return actor_role == "IMPLEMENTATION_MEMBER" or row.owner_ref == actor_id

    def lock(self, transaction: object, *, command: SubmitHandoverAction,
             actor_id: uuid.UUID,
             actor_role: str) -> HandoverActionSubmitLock:
        row = _session(transaction).execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == command.action_item_id,
            HandoverActionItemRow.project_id == command.project_id,
        ).with_for_update(of=HandoverActionItemRow)).scalar_one_or_none()
        if row is None or not self._allowed(row, actor_id, actor_role):
            raise HandoverActionSubmitError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise HandoverActionSubmitError("CONFLICT_VERSION")
        if row.action_state != "IN_PROGRESS":
            raise HandoverActionSubmitError("HANDOVER_ACTION_STATE_INVALID")
        return HandoverActionSubmitLock(
            row.action_item_id, row.project_id, row.lock_version,
        )

    def submit(self, transaction: object, *, command: SubmitHandoverAction,
               action: HandoverActionSubmitLock, actor_id: uuid.UUID,
               occurred_at: datetime) -> HandoverActionSubmitView:
        session = _session(transaction)
        for ordinal, ref in enumerate(command.response_documents):
            session.execute(insert(HandoverActionResponseRefRow).values(
                action_response_ref_id=uuid.UUID(new_uuid7()),
                action_item_id=action.action_item_id,
                project_id=action.project_id, document_id=ref.document_id,
                document_version_id=ref.document_version_id, ordinal=ordinal,
            ))
        for ordinal, evidence_id in enumerate(command.evidence_refs):
            session.execute(insert(HandoverActionEvidenceRefRow).values(
                action_evidence_ref_id=uuid.UUID(new_uuid7()),
                action_item_id=action.action_item_id,
                project_id=action.project_id, evidence_id=evidence_id,
                purpose="SUBMISSION", ordinal=ordinal,
            ))
        event_id, version = uuid.UUID(new_uuid7()), action.lock_version + 1
        session.execute(insert(HandoverActionStateEventRow).values(
            action_state_event_id=event_id,
            action_item_id=action.action_item_id, project_id=action.project_id,
            sequence_no=version, from_state="IN_PROGRESS", to_state="SUBMITTED",
            actor_id=actor_id, reason=command.reason, occurred_at=occurred_at,
            trace_id=command.trace_id,
        ))
        changed = session.execute(update(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == action.action_item_id,
            HandoverActionItemRow.project_id == action.project_id,
            HandoverActionItemRow.lock_version == action.lock_version,
            HandoverActionItemRow.action_state == "IN_PROGRESS",
        ).values(
            action_state="SUBMITTED", submitted_at=occurred_at,
            updated_by=actor_id, updated_at=occurred_at, lock_version=version,
        ))
        if changed.rowcount != 1:
            raise HandoverActionSubmitError("CONFLICT_VERSION")
        return HandoverActionSubmitView(
            action.action_item_id, action.project_id, event_id, "SUBMITTED",
            occurred_at, command.response_documents, command.evidence_refs,
            f'"v{version}"',
        )

    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID,
               actor_role: str) -> HandoverActionSubmitView | None:
        session = _session(transaction)
        row = session.execute(select(
            HandoverActionItemRow.owner_ref,
            HandoverActionStateEventRow.sequence_no,
            HandoverActionStateEventRow.occurred_at,
        ).join(
            HandoverActionStateEventRow,
            (HandoverActionStateEventRow.action_item_id
             == HandoverActionItemRow.action_item_id)
            & (HandoverActionStateEventRow.project_id
               == HandoverActionItemRow.project_id),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionStateEventRow.action_state_event_id == event_id,
            HandoverActionStateEventRow.from_state == "IN_PROGRESS",
            HandoverActionStateEventRow.to_state == "SUBMITTED",
            HandoverActionStateEventRow.actor_id == actor_id,
        ).with_for_update(
            of=HandoverActionItemRow, read=True,
        )).one_or_none()
        if row is None or not (
                actor_role == "IMPLEMENTATION_MEMBER"
                or row.owner_ref == actor_id):
            raise HandoverActionSubmitError("RESOURCE_NOT_FOUND")
        documents = session.execute(select(
            HandoverActionResponseRefRow.document_id,
            HandoverActionResponseRefRow.document_version_id,
        ).where(
            HandoverActionResponseRefRow.action_item_id == action_item_id,
            HandoverActionResponseRefRow.project_id == project_id,
        ).order_by(HandoverActionResponseRefRow.ordinal)).all()
        evidence = session.execute(select(
            HandoverActionEvidenceRefRow.evidence_id,
        ).where(
            HandoverActionEvidenceRefRow.action_item_id == action_item_id,
            HandoverActionEvidenceRefRow.project_id == project_id,
            HandoverActionEvidenceRefRow.purpose == "SUBMISSION",
        ).order_by(HandoverActionEvidenceRefRow.ordinal)).scalars().all()
        if not documents or not evidence:
            return None
        return HandoverActionSubmitView(
            action_item_id, project_id, event_id, "SUBMITTED", row.occurred_at,
            tuple(HandoverDocumentRef(item.document_id, item.document_version_id)
                  for item in documents),
            tuple(evidence), f'"v{row.sequence_no}"',
        )
