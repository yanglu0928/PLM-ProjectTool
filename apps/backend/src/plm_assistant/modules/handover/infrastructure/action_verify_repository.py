"""Handover-owned SUBMITTED to VERIFIED persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, insert, select, update

from plm_assistant.modules.handover.application.source_validation import HandoverDocumentRef
from plm_assistant.modules.handover.application.verify_action import (
    HandoverActionVerificationLock, HandoverActionVerifyError,
    HandoverActionVerifyView, VerifyHandoverAction,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7

from .analysis_create_repository import _session
from .orm import (
    HandoverActionEvidenceRefRow, HandoverActionItemRow,
    HandoverActionResponseRefRow, HandoverActionStateEventRow,
)


_VERIFIERS = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class SqlAlchemyHandoverActionVerifyRepository:
    def lock(self, transaction: object, *, command: VerifyHandoverAction,
             actor_id: uuid.UUID,
             actor_role: str) -> HandoverActionVerificationLock:
        session = _session(transaction)
        row = session.execute(select(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == command.action_item_id,
            HandoverActionItemRow.project_id == command.project_id,
        ).with_for_update(of=HandoverActionItemRow)).scalar_one_or_none()
        if row is None or actor_role not in _VERIFIERS:
            raise HandoverActionVerifyError("RESOURCE_NOT_FOUND")
        if row.lock_version != command.expected_version:
            raise HandoverActionVerifyError("CONFLICT_VERSION")
        if row.action_state != "SUBMITTED":
            raise HandoverActionVerifyError("HANDOVER_ACTION_STATE_INVALID")
        documents = session.execute(select(
            HandoverActionResponseRefRow.document_id,
            HandoverActionResponseRefRow.document_version_id,
        ).where(
            HandoverActionResponseRefRow.action_item_id == row.action_item_id,
            HandoverActionResponseRefRow.project_id == row.project_id,
        ).order_by(HandoverActionResponseRefRow.ordinal)).all()
        evidence = session.execute(select(
            HandoverActionEvidenceRefRow.evidence_id,
        ).where(
            HandoverActionEvidenceRefRow.action_item_id == row.action_item_id,
            HandoverActionEvidenceRefRow.project_id == row.project_id,
            HandoverActionEvidenceRefRow.purpose == "SUBMISSION",
        ).order_by(HandoverActionEvidenceRefRow.ordinal)).scalars().all()
        next_ordinal = session.execute(select(
            func.count(HandoverActionEvidenceRefRow.action_evidence_ref_id),
        ).where(
            HandoverActionEvidenceRefRow.action_item_id == row.action_item_id,
        )).scalar_one()
        if not documents or not evidence:
            raise HandoverActionVerifyError(
                "HANDOVER_ACTION_EVIDENCE_REQUIRED",
            )
        return HandoverActionVerificationLock(
            row.action_item_id, row.project_id, row.lock_version,
            tuple(HandoverDocumentRef(item.document_id, item.document_version_id)
                  for item in documents),
            tuple(evidence), next_ordinal,
        )

    def verify(self, transaction: object, *, command: VerifyHandoverAction,
               action: HandoverActionVerificationLock, actor_id: uuid.UUID,
               occurred_at: datetime) -> HandoverActionVerifyView:
        session = _session(transaction)
        for offset, evidence_id in enumerate(command.evidence_refs):
            session.execute(insert(HandoverActionEvidenceRefRow).values(
                action_evidence_ref_id=uuid.UUID(new_uuid7()),
                action_item_id=action.action_item_id,
                project_id=action.project_id, evidence_id=evidence_id,
                purpose="VERIFICATION",
                ordinal=action.next_evidence_ordinal + offset,
            ))
        event_id, version = uuid.UUID(new_uuid7()), action.lock_version + 1
        session.execute(insert(HandoverActionStateEventRow).values(
            action_state_event_id=event_id,
            action_item_id=action.action_item_id, project_id=action.project_id,
            sequence_no=version, from_state="SUBMITTED", to_state="VERIFIED",
            actor_id=actor_id, reason=command.reason, occurred_at=occurred_at,
            trace_id=command.trace_id,
        ))
        changed = session.execute(update(HandoverActionItemRow).where(
            HandoverActionItemRow.action_item_id == action.action_item_id,
            HandoverActionItemRow.project_id == action.project_id,
            HandoverActionItemRow.lock_version == action.lock_version,
            HandoverActionItemRow.action_state == "SUBMITTED",
        ).values(
            action_state="VERIFIED", verified_by=actor_id,
            verified_at=occurred_at, updated_by=actor_id,
            updated_at=occurred_at, lock_version=version,
        ))
        if changed.rowcount != 1:
            raise HandoverActionVerifyError("CONFLICT_VERSION")
        return HandoverActionVerifyView(
            action.action_item_id, action.project_id, event_id, "VERIFIED",
            actor_id, occurred_at, command.evidence_refs, f'"v{version}"',
        )

    def replay(self, transaction: object, *, action_item_id: uuid.UUID,
               project_id: uuid.UUID, event_id: uuid.UUID,
               actor_id: uuid.UUID,
               actor_role: str) -> HandoverActionVerifyView | None:
        session = _session(transaction)
        row = session.execute(select(
            HandoverActionStateEventRow.sequence_no,
            HandoverActionStateEventRow.occurred_at,
        ).join(
            HandoverActionItemRow,
            (HandoverActionItemRow.action_item_id
             == HandoverActionStateEventRow.action_item_id)
            & (HandoverActionItemRow.project_id
               == HandoverActionStateEventRow.project_id),
        ).where(
            HandoverActionItemRow.action_item_id == action_item_id,
            HandoverActionItemRow.project_id == project_id,
            HandoverActionStateEventRow.action_state_event_id == event_id,
            HandoverActionStateEventRow.from_state == "SUBMITTED",
            HandoverActionStateEventRow.to_state == "VERIFIED",
            HandoverActionStateEventRow.actor_id == actor_id,
        ).with_for_update(
            of=HandoverActionItemRow, read=True,
        )).one_or_none()
        if row is None or actor_role not in _VERIFIERS:
            raise HandoverActionVerifyError("RESOURCE_NOT_FOUND")
        evidence = session.execute(select(
            HandoverActionEvidenceRefRow.evidence_id,
        ).where(
            HandoverActionEvidenceRefRow.action_item_id == action_item_id,
            HandoverActionEvidenceRefRow.project_id == project_id,
            HandoverActionEvidenceRefRow.purpose == "VERIFICATION",
        ).order_by(HandoverActionEvidenceRefRow.ordinal)).scalars().all()
        if not evidence:
            return None
        return HandoverActionVerifyView(
            action_item_id, project_id, event_id, "VERIFIED", actor_id,
            row.occurred_at, tuple(evidence), f'"v{row.sequence_no}"',
        )
