from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import unittest

from plm_assistant.modules.workflow.application.append_stage_transition import (
    AppendStageTransition, PersistedStageTransition, PersistedTransitionGate,
    StageTransitionAppendError, TransitionGateProof,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation,
)
from plm_assistant.modules.workflow.application.stage_transition_integrity import (
    stage_transition_fingerprint,
)
from plm_assistant.modules.workflow.domain.history import (
    ForwardTransitionSnapshot, GateItemSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


class StageTransitionAppendValueTests(unittest.TestCase):
    def setUp(self):
        self.project, self.workflow = uuid4(), uuid4()
        self.actor, self.trace = uuid4(), uuid4()
        self.now = datetime.now(timezone.utc)
        evidence = ChecklistBasisObservation(
            "EVIDENCE", uuid4(), "PROJECT", self.project, "ELIGIBLE",
            2, b"e" * 32, self.now, 1,
        )
        review = ChecklistBasisObservation(
            "REVIEW_ROUND", uuid4(), "PROJECT", self.project, "APPROVED",
            3, b"r" * 32, self.now, 1,
        )
        self.basis = tuple(sorted(
            (evidence, review),
            key=lambda value: (value.ref_kind, str(value.ref_id)),
        ))
        self.proofs = (
            TransitionGateProof("HANDOVER_BASELINE", self.basis),
            TransitionGateProof("HANDOVER_ISSUES", self.basis),
        )
        self.command = AppendStageTransition(
            self.project, "SURVEY", 3, self.actor, self.trace,
            "Handover Gate facts reverified", self.now, self.proofs,
        )

    def test_command_requires_canonical_unique_gate_proofs(self):
        self.assertEqual(self.command.target_stage_key, "SURVEY")
        for changes in (
            {"gates": tuple(reversed(self.proofs))},
            {"gates": (self.proofs[0], self.proofs[0])},
            {"expected_workflow_version": -1},
            {"reason": " "},
            {"occurred_at": self.now - timedelta(microseconds=1)},
        ):
            with self.subTest(changes=changes), self.assertRaises(
                    StageTransitionAppendError):
                replace(self.command, **changes)

    def test_gate_proof_requires_sorted_fresh_evidence_and_review(self):
        cases = (
            tuple(reversed(self.basis)),
            (self.basis[0], self.basis[0]),
            (self.basis[0],),
            (self.basis[1],),
        )
        for basis in cases:
            with self.subTest(basis=basis), self.assertRaises(
                    StageTransitionAppendError):
                TransitionGateProof("HANDOVER_BASELINE", basis)

    def test_fingerprint_binds_transition_record_and_fresh_observations(self):
        gate_snapshots = tuple(GateItemSnapshot(
            proof.item_key, ChecklistState.PASS,
            tuple(value.ref_id for value in proof.basis
                  if value.ref_kind == "EVIDENCE"),
            tuple(value.ref_id for value in proof.basis
                  if value.ref_kind == "REVIEW_ROUND"),
        ) for proof in self.proofs)
        gates = tuple(PersistedTransitionGate(
            uuid4(), uuid4(), 1, bytes([index + 1]) * 32,
            gate_snapshots[index], proof.basis,
        ) for index, proof in enumerate(self.proofs))
        snapshot = ForwardTransitionSnapshot(
            self.workflow, self.project, self.actor, self.trace, 1,
            "HANDOVER", "SURVEY", 3, 4,
            self.command.reason, self.now, gate_snapshots,
        )
        value = PersistedStageTransition(
            uuid4(), snapshot, gates, b"\x00" * 32, 4,
        )
        first = stage_transition_fingerprint(value)
        self.assertEqual(len(first), 32)
        changed_snapshot = replace(snapshot, reason="A different reason")
        changed = replace(value, snapshot=changed_snapshot)
        self.assertNotEqual(first, stage_transition_fingerprint(changed))
        newer = replace(
            self.basis[0], observed_lock_version=4,
        )
        newer_basis = tuple(sorted(
            (newer, self.basis[1]),
            key=lambda item: (item.ref_kind, str(item.ref_id)),
        ))
        changed_gate = replace(gates[0], basis=newer_basis)
        changed_gate_snapshot = replace(
            gate_snapshots[0],
            evidence_refs=tuple(item.ref_id for item in newer_basis
                                if item.ref_kind == "EVIDENCE"),
        )
        changed_gate = replace(changed_gate, snapshot=changed_gate_snapshot)
        changed_gates = (changed_gate, gates[1])
        changed_value = replace(
            value, gates=changed_gates,
            snapshot=replace(snapshot, gate_items=(changed_gate_snapshot,
                                                    gate_snapshots[1])),
        )
        self.assertNotEqual(first, stage_transition_fingerprint(changed_value))

        malformed = object.__new__(PersistedStageTransition)
        with self.assertRaisesRegex(
                ValueError, "invalid Stage Transition fingerprint input"):
            stage_transition_fingerprint(malformed)


if __name__ == "__main__":
    unittest.main()
