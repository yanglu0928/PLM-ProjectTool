"""Caller-transaction values for one immutable forward Stage Transition."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..domain.catalog_v1 import six_stage_definition
from ..domain.history import ForwardTransitionSnapshot, GateItemSnapshot, _reason
from ..domain.transition import ChecklistState
from .current_checklist_record import ChecklistBasisObservation


class StageTransitionAppendError(RuntimeError):
    def __init__(self, code: str = "WORKFLOW_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


@dataclass(frozen=True, slots=True)
class TransitionGateProof:
    """Fresh Owner observations; never authorization by construction alone."""

    item_key: str
    basis: tuple[ChecklistBasisObservation, ...]
    waiver_actor_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (type(self.item_key) is not str or not self.item_key
                or type(self.basis) is not tuple or not self.basis
                or any(type(value) is not ChecklistBasisObservation
                       for value in self.basis)
                or self.waiver_actor_id is not None
                   and not _id(self.waiver_actor_id)):
            raise StageTransitionAppendError("VALIDATION_FAILED")
        positions: list[tuple[str, str]] = []
        for value in self.basis:
            try:
                value.__post_init__()
            except ValueError:
                raise StageTransitionAppendError(
                    "VALIDATION_FAILED",
                ) from None
            positions.append((value.ref_kind, str(value.ref_id)))
        if (positions != sorted(positions)
                or len(positions) != len(set(positions))
                or not any(value.ref_kind == "EVIDENCE" for value in self.basis)
                or not any(value.ref_kind == "REVIEW_ROUND"
                           for value in self.basis)):
            raise StageTransitionAppendError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class AppendStageTransition:
    project_id: uuid.UUID
    target_stage_key: str
    expected_workflow_version: int
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    reason: str
    occurred_at: datetime
    gates: tuple[TransitionGateProof, ...]

    def __post_init__(self) -> None:
        if (not _id(self.project_id) or not _id(self.actor_id)
                or not _id(self.trace_id)
                or type(self.target_stage_key) is not str
                or not self.target_stage_key
                or type(self.expected_workflow_version) is not int
                or not 0 <= self.expected_workflow_version < 2**63 - 1
                or not _reason(self.reason)
                or type(self.occurred_at) is not datetime
                or self.occurred_at.tzinfo is None
                or self.occurred_at.utcoffset() != timedelta(0)
                or type(self.gates) is not tuple or not self.gates
                or any(type(value) is not TransitionGateProof
                       for value in self.gates)
                or any(observation.verified_at > self.occurred_at
                       for gate in self.gates for observation in gate.basis)):
            raise StageTransitionAppendError("VALIDATION_FAILED")
        for value in self.gates:
            value.__post_init__()
        keys = tuple(value.item_key for value in self.gates)
        definition = six_stage_definition(1)
        stages = tuple(stage.stage_key for stage in definition.stages)
        if (self.target_stage_key not in stages[1:]
                or keys != tuple(
                    item.item_key for item in definition.stages[
                        stages.index(self.target_stage_key) - 1
                    ].checklist_items
                )):
            raise StageTransitionAppendError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class PersistedTransitionGate:
    gate_item_id: uuid.UUID
    checklist_record_id: uuid.UUID
    observed_item_version: int
    record_fingerprint: bytes
    snapshot: GateItemSnapshot
    basis: tuple[ChecklistBasisObservation, ...]

    def __post_init__(self) -> None:
        if (not _id(self.gate_item_id) or not _id(self.checklist_record_id)
                or type(self.observed_item_version) is not int
                or not 0 < self.observed_item_version < 2**63
                or type(self.record_fingerprint) is not bytes
                or len(self.record_fingerprint) != 32
                or type(self.snapshot) is not GateItemSnapshot
                or type(self.basis) is not tuple
                or any(type(value) is not ChecklistBasisObservation
                       for value in self.basis)):
            raise StageTransitionAppendError()
        try:
            self.snapshot.__post_init__()
        except ValueError:
            raise StageTransitionAppendError() from None
        for value in self.basis:
            try:
                value.__post_init__()
            except ValueError:
                raise StageTransitionAppendError() from None
        for kind, expected in (
                ("EVIDENCE", self.snapshot.evidence_refs),
                ("REVIEW_ROUND", self.snapshot.review_round_refs),
                ("APPROVED_EXCEPTION", self.snapshot.exception_refs)):
            if tuple(value.ref_id for value in self.basis
                     if value.ref_kind == kind) != expected:
                raise StageTransitionAppendError()


@dataclass(frozen=True, slots=True)
class PersistedStageTransition:
    stage_transition_id: uuid.UUID
    snapshot: ForwardTransitionSnapshot
    gates: tuple[PersistedTransitionGate, ...]
    gate_fingerprint: bytes
    current_workflow_version: int

    def __post_init__(self) -> None:
        if (not _id(self.stage_transition_id)
                or type(self.snapshot) is not ForwardTransitionSnapshot
                or type(self.gates) is not tuple
                or any(type(value) is not PersistedTransitionGate
                       for value in self.gates)
                or type(self.gate_fingerprint) is not bytes
                or len(self.gate_fingerprint) != 32
                or type(self.current_workflow_version) is not int
                or not self.snapshot.after_lock_version
                       <= self.current_workflow_version < 2**63):
            raise StageTransitionAppendError()
        try:
            self.snapshot.__post_init__()
        except ValueError:
            raise StageTransitionAppendError() from None
        for value in self.gates:
            value.__post_init__()
        if tuple(value.snapshot for value in self.gates) != self.snapshot.gate_items:
            raise StageTransitionAppendError()


def gate_snapshot(
    *, item_key: str, result: ChecklistState,
    basis: tuple[ChecklistBasisObservation, ...],
    waiver_actor_id: uuid.UUID | None, reason: str | None, impact: str | None,
) -> GateItemSnapshot:
    return GateItemSnapshot(
        item_key=item_key, result=result,
        evidence_refs=tuple(value.ref_id for value in basis
                            if value.ref_kind == "EVIDENCE"),
        review_round_refs=tuple(value.ref_id for value in basis
                                if value.ref_kind == "REVIEW_ROUND"),
        exception_refs=tuple(value.ref_id for value in basis
                             if value.ref_kind == "APPROVED_EXCEPTION"),
        waiver_actor_id=waiver_actor_id if result is ChecklistState.WAIVED else None,
        waiver_reason=reason if result is ChecklistState.WAIVED else None,
        waiver_impact=impact if result is ChecklistState.WAIVED else None,
    )
