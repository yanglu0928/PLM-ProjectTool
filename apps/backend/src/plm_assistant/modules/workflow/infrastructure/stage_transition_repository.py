"""Atomic Stage Transition append/read; no authorization, Owner proof or commit."""

from __future__ import annotations

import uuid
from datetime import timezone

from sqlalchemy import func, insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.workflow.application.append_stage_transition import (
    AppendStageTransition, PersistedStageTransition, PersistedTransitionGate,
    StageTransitionAppendError, TransitionGateProof, gate_snapshot,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation, CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.application.stage_transition_integrity import (
    stage_transition_fingerprint,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.domain.history import ForwardTransitionSnapshot
from plm_assistant.modules.workflow.domain.transition import (
    ChecklistState, StageState, WorkflowState, WorkflowTransitionError,
    validate_forward_structure,
)

from .current_checklist_repository import (
    SqlAlchemyCurrentChecklistRecordRepository,
)
from .history_orm import (
    StageTransitionRow, TransitionGateItemRow, TransitionGateRefRow,
)
from .orm import ChecklistItemRow, ProjectWorkflowRow, StageRow


class SqlAlchemyStageTransitionRepository:
    def __init__(self, *,
                 current: SqlAlchemyCurrentChecklistRecordRepository | None = None
                 ) -> None:
        self._current = current or SqlAlchemyCurrentChecklistRecordRepository()

    def append(
        self, transaction: object, *, command: AppendStageTransition,
    ) -> PersistedStageTransition:
        if type(command) is not AppendStageTransition:
            raise StageTransitionAppendError("VALIDATION_FAILED")
        command.__post_init__()
        session = self._session(transaction)
        definition = six_stage_definition(1)
        root = session.execute(select(ProjectWorkflowRow).where(
            ProjectWorkflowRow.project_id == command.project_id,
        ).with_for_update()).scalar_one_or_none()
        if root is None:
            raise StageTransitionAppendError("RESOURCE_NOT_FOUND")
        if root.lock_version != command.expected_workflow_version:
            raise StageTransitionAppendError("CONFLICT_VERSION")
        if (root.workflow_version != definition.version
                or bytes(root.definition_fingerprint)
                   != definition_fingerprint(definition)):
            raise StageTransitionAppendError("WORKFLOW_UNAVAILABLE")
        try:
            validate_forward_structure(
                definition, workflow_state=WorkflowState(root.workflow_state),
                current_stage_key=root.current_stage_key,
                target_stage_key=command.target_stage_key,
                expected_version=command.expected_workflow_version,
                lock_version=root.lock_version, project_archived=False,
            )
        except (ValueError, WorkflowTransitionError):
            raise StageTransitionAppendError(
                "WORKFLOW_TRANSITION_INVALID",
            ) from None
        source_definition = next(
            stage for stage in definition.stages
            if stage.stage_key == root.current_stage_key
        )
        expected_keys = tuple(
            item.item_key for item in source_definition.checklist_items
        )
        if tuple(value.item_key for value in command.gates) != expected_keys:
            raise StageTransitionAppendError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        stages = session.execute(select(StageRow).where(
            StageRow.workflow_id == root.workflow_id,
            StageRow.project_id == command.project_id,
            StageRow.stage_key.in_((
                root.current_stage_key, command.target_stage_key,
            )),
        ).order_by(StageRow.stage_order).with_for_update()).scalars().all()
        if len(stages) != 2:
            raise StageTransitionAppendError()
        by_stage = {value.stage_key: value for value in stages}
        source = by_stage.get(root.current_stage_key)
        target = by_stage.get(command.target_stage_key)
        if (source is None or target is None or source.stage_state != "ACTIVE"
                or target.stage_state != "NOT_STARTED"):
            raise StageTransitionAppendError(
                "WORKFLOW_TRANSITION_INVALID",
            )

        persisted_gates: list[PersistedTransitionGate] = []
        item_rows: dict[str, ChecklistItemRow] = {}
        for proof in command.gates:
            item = session.execute(select(ChecklistItemRow).where(
                ChecklistItemRow.workflow_id == root.workflow_id,
                ChecklistItemRow.project_id == command.project_id,
                ChecklistItemRow.item_key == proof.item_key,
            ).with_for_update()).scalar_one_or_none()
            if item is None:
                raise StageTransitionAppendError()
            item_rows[proof.item_key] = item
            current = self._current.get(
                transaction, command.project_id, root.workflow_id,
                proof.item_key,
            )
            if type(current) is not CurrentChecklistRecord:
                raise StageTransitionAppendError(
                    "WORKFLOW_GATE_NOT_SATISFIED",
                )
            self._validate_gate(
                proof, current, workflow_id=root.workflow_id,
                project_id=command.project_id,
                stage_key=root.current_stage_key,
                current_workflow_version=root.lock_version,
            )
            try:
                snapshot = gate_snapshot(
                    item_key=proof.item_key,
                    result=current.record.result, basis=proof.basis,
                    waiver_actor_id=proof.waiver_actor_id,
                    reason=current.record.reason,
                    impact=current.record.impact,
                )
                persisted_gates.append(PersistedTransitionGate(
                    gate_item_id=uuid.UUID(new_uuid7()),
                    checklist_record_id=current.record.record_id,
                    observed_item_version=current.record.after_item_version,
                    record_fingerprint=current.content_fingerprint,
                    snapshot=snapshot, basis=proof.basis,
                ))
            except (ValueError, StageTransitionAppendError):
                raise StageTransitionAppendError(
                    "WORKFLOW_GATE_NOT_SATISFIED",
                ) from None

        transition_id = uuid.UUID(new_uuid7())
        try:
            snapshot = ForwardTransitionSnapshot(
                workflow_id=root.workflow_id,
                project_id=command.project_id,
                actor_id=command.actor_id, trace_id=command.trace_id,
                definition_version=definition.version,
                from_stage=root.current_stage_key,
                to_stage=command.target_stage_key,
                before_lock_version=root.lock_version,
                after_lock_version=root.lock_version + 1,
                reason=command.reason, occurred_at=command.occurred_at,
                gate_items=tuple(value.snapshot for value in persisted_gates),
            )
            provisional = PersistedStageTransition(
                transition_id, snapshot, tuple(persisted_gates),
                b"\x00" * 32, root.lock_version + 1,
            )
            fingerprint = stage_transition_fingerprint(provisional)
            result = PersistedStageTransition(
                transition_id, snapshot, tuple(persisted_gates),
                fingerprint, root.lock_version + 1,
            )
        except (ValueError, StageTransitionAppendError):
            raise StageTransitionAppendError("VALIDATION_FAILED") from None

        session.execute(insert(StageTransitionRow).values(
            stage_transition_id=transition_id,
            workflow_id=root.workflow_id, project_id=command.project_id,
            definition_version=definition.version,
            definition_fingerprint=definition_fingerprint(definition),
            transition_type="FORWARD", from_stage=root.current_stage_key,
            to_stage=command.target_stage_key,
            before_lock_version=root.lock_version,
            after_lock_version=root.lock_version + 1,
            actor_id=command.actor_id, reason=command.reason,
            occurred_at=command.occurred_at, trace_id=command.trace_id,
            gate_fingerprint=fingerprint,
        ))
        for gate in result.gates:
            item = item_rows[gate.snapshot.item_key]
            session.execute(insert(TransitionGateItemRow).values(
                gate_item_id=gate.gate_item_id,
                stage_transition_id=transition_id,
                workflow_id=root.workflow_id, project_id=command.project_id,
                item_key=gate.snapshot.item_key, required=item.required,
                result=gate.snapshot.result.value,
                evidence_policy_ref=item.evidence_policy_ref,
                review_policy_ref=item.review_policy_ref,
                waiver_actor_id=gate.snapshot.waiver_actor_id,
                waiver_reason=gate.snapshot.waiver_reason,
                waiver_impact=gate.snapshot.waiver_impact,
                checklist_record_id=gate.checklist_record_id,
                observed_item_version=gate.observed_item_version,
                record_fingerprint=gate.record_fingerprint,
            ))
            session.execute(insert(TransitionGateRefRow), [dict(
                gate_ref_id=uuid.UUID(new_uuid7()),
                gate_item_id=gate.gate_item_id,
                workflow_id=root.workflow_id,
                project_id=command.project_id,
                ref_kind=value.ref_kind, ref_id=value.ref_id,
                ref_scope=value.ref_scope,
                ref_project_id=value.ref_project_id,
                observed_state=value.observed_state,
                observed_lock_version=value.observed_lock_version,
                content_fingerprint=value.content_fingerprint,
                verified_at=value.verified_at,
                proof_schema_version=value.proof_schema_version,
            ) for value in gate.basis])

        source_changed = session.execute(update(StageRow).where(
            StageRow.workflow_id == root.workflow_id,
            StageRow.project_id == command.project_id,
            StageRow.stage_key == root.current_stage_key,
            StageRow.stage_state == "ACTIVE",
        ).values(stage_state="COMPLETED").returning(
            StageRow.stage_id,
        )).scalar_one_or_none()
        target_changed = session.execute(update(StageRow).where(
            StageRow.workflow_id == root.workflow_id,
            StageRow.project_id == command.project_id,
            StageRow.stage_key == command.target_stage_key,
            StageRow.stage_state == "NOT_STARTED",
        ).values(stage_state="ACTIVE").returning(
            StageRow.stage_id,
        )).scalar_one_or_none()
        workflow_changed = session.execute(update(ProjectWorkflowRow).where(
            ProjectWorkflowRow.workflow_id == root.workflow_id,
            ProjectWorkflowRow.project_id == command.project_id,
            ProjectWorkflowRow.workflow_state == "ACTIVE",
            ProjectWorkflowRow.current_stage_key == root.current_stage_key,
            ProjectWorkflowRow.lock_version == root.lock_version,
        ).values(
            current_stage_key=command.target_stage_key,
            lock_version=root.lock_version + 1,
            updated_at=func.statement_timestamp(),
        ).returning(ProjectWorkflowRow.workflow_id)).scalar_one_or_none()
        if (source_changed is None or target_changed is None
                or workflow_changed != root.workflow_id):
            raise StageTransitionAppendError("CONFLICT_VERSION")
        session.expire_all()
        restored = self.get_transition(
            transaction, project_id=command.project_id,
            stage_transition_id=transition_id,
        )
        if restored != result:
            raise StageTransitionAppendError()
        return result

    def get_transition(
        self, transaction: object, *, project_id: uuid.UUID,
        stage_transition_id: uuid.UUID,
    ) -> PersistedStageTransition | None:
        if (type(project_id) is not uuid.UUID or project_id.int == 0
                or type(stage_transition_id) is not uuid.UUID
                or stage_transition_id.int == 0):
            raise StageTransitionAppendError("VALIDATION_FAILED")
        session = self._session(transaction)
        root = session.execute(select(StageTransitionRow.__table__).where(
            StageTransitionRow.stage_transition_id == stage_transition_id,
            StageTransitionRow.project_id == project_id,
        )).mappings().one_or_none()
        if root is None:
            return None
        workflow_version = session.execute(select(
            ProjectWorkflowRow.lock_version,
        ).where(
            ProjectWorkflowRow.workflow_id == root["workflow_id"],
            ProjectWorkflowRow.project_id == project_id,
        )).scalar_one_or_none()
        if workflow_version is None:
            raise StageTransitionAppendError()
        definition = six_stage_definition(root["definition_version"])
        stage = next((value for value in definition.stages
                      if value.stage_key == root["from_stage"]), None)
        if stage is None:
            raise StageTransitionAppendError()
        item_order = {
            item.item_key: index for index, item in enumerate(stage.checklist_items)
        }
        rows = session.execute(select(TransitionGateItemRow.__table__).where(
            TransitionGateItemRow.stage_transition_id == stage_transition_id,
            TransitionGateItemRow.workflow_id == root["workflow_id"],
            TransitionGateItemRow.project_id == project_id,
        )).mappings().all()
        if any(value["item_key"] not in item_order for value in rows):
            raise StageTransitionAppendError()
        rows.sort(key=lambda value: item_order[value["item_key"]])
        gates: list[PersistedTransitionGate] = []
        for row in rows:
            refs = session.execute(select(
                TransitionGateRefRow.__table__,
            ).where(
                TransitionGateRefRow.gate_item_id == row["gate_item_id"],
                TransitionGateRefRow.workflow_id == root["workflow_id"],
                TransitionGateRefRow.project_id == project_id,
            ).order_by(
                TransitionGateRefRow.ref_kind,
                TransitionGateRefRow.ref_id,
            )).mappings().all()
            try:
                basis = tuple(ChecklistBasisObservation(
                    value["ref_kind"], value["ref_id"],
                    value["ref_scope"], value["ref_project_id"],
                    value["observed_state"], value["observed_lock_version"],
                    bytes(value["content_fingerprint"]),
                    value["verified_at"].astimezone(timezone.utc),
                    value["proof_schema_version"],
                ) for value in refs)
                snapshot = gate_snapshot(
                    item_key=row["item_key"],
                    result=ChecklistState(row["result"]), basis=basis,
                    waiver_actor_id=row["waiver_actor_id"],
                    reason=row["waiver_reason"], impact=row["waiver_impact"],
                )
                gates.append(PersistedTransitionGate(
                    row["gate_item_id"], row["checklist_record_id"],
                    row["observed_item_version"],
                    bytes(row["record_fingerprint"]), snapshot, basis,
                ))
            except (TypeError, ValueError, StageTransitionAppendError):
                raise StageTransitionAppendError() from None
        try:
            snapshot = ForwardTransitionSnapshot(
                root["workflow_id"], project_id, root["actor_id"],
                root["trace_id"], root["definition_version"],
                root["from_stage"], root["to_stage"],
                root["before_lock_version"], root["after_lock_version"],
                root["reason"], root["occurred_at"].astimezone(timezone.utc),
                tuple(value.snapshot for value in gates),
            )
            value = PersistedStageTransition(
                stage_transition_id, snapshot, tuple(gates),
                bytes(root["gate_fingerprint"]), workflow_version,
            )
            if stage_transition_fingerprint(value) != value.gate_fingerprint:
                raise StageTransitionAppendError()
            return value
        except (TypeError, ValueError, StageTransitionAppendError):
            raise StageTransitionAppendError() from None

    @staticmethod
    def _validate_gate(
        proof: TransitionGateProof, current: CurrentChecklistRecord, *,
        workflow_id: uuid.UUID, project_id: uuid.UUID, stage_key: str,
        current_workflow_version: int,
    ) -> None:
        try:
            proof.__post_init__()
            current.__post_init__()
        except (ValueError, StageTransitionAppendError):
            raise StageTransitionAppendError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            ) from None
        record = current.record
        if (record.workflow_id != workflow_id
                or record.project_id != project_id
                or record.stage_key != stage_key
                or record.item_key != proof.item_key
                # ApprovedException has no trusted Owner yet.  Keep WAIVED
                # structurally representable in history, but fail closed here.
                or record.result is not ChecklistState.PASS
                or current.current_workflow_version != current_workflow_version
                or proof.waiver_actor_id is not None
                or len(current.basis) != len(proof.basis)):
            raise StageTransitionAppendError(
                "WORKFLOW_GATE_NOT_SATISFIED",
            )
        for stored, fresh in zip(current.basis, proof.basis, strict=True):
            expected_state = (
                "ELIGIBLE" if fresh.ref_kind == "EVIDENCE" else "APPROVED"
            )
            if (fresh.ref_kind != stored.ref_kind
                    or fresh.ref_id != stored.ref_id
                    or fresh.ref_scope != stored.ref_scope
                    or fresh.ref_project_id != stored.ref_project_id
                    or fresh.content_fingerprint != stored.content_fingerprint
                    or fresh.proof_schema_version != stored.proof_schema_version
                    or fresh.observed_state != expected_state
                    or fresh.observed_lock_version < stored.observed_lock_version
                    or fresh.verified_at < stored.verified_at):
                raise StageTransitionAppendError(
                    "WORKFLOW_GATE_NOT_SATISFIED",
                )

    @staticmethod
    def _session(transaction: object) -> Session:
        session = getattr(transaction, "session", None)
        if not isinstance(session, Session) or not session.in_transaction():
            raise StageTransitionAppendError("WORKFLOW_UNAVAILABLE")
        return session
