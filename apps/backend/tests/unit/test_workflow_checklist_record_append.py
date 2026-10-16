from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
import unittest

from plm_assistant.modules.workflow.application.append_checklist_record import (
    AppendChecklistRecord, ChecklistRecordAppendError,
    ChecklistRecordWriteLock,
)
from plm_assistant.modules.workflow.application.checklist_record_integrity import (
    checklist_record_fingerprint,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation,
)
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


class ChecklistRecordAppendValueTests(unittest.TestCase):
    def setUp(self):
        self.project, self.workflow = uuid4(), uuid4()
        self.now = datetime.now(timezone.utc)
        self.lock = ChecklistRecordWriteLock(
            self.workflow, self.project, 1, "HANDOVER", "ACTIVE",
            "HANDOVER_BASELINE", ChecklistState.PENDING, 0, 2, None,
        )
        evidence = ChecklistBasisObservation(
            "EVIDENCE", uuid4(), "PROJECT", self.project, "ELIGIBLE",
            1, b"e" * 32, self.now, 1,
        )
        review = ChecklistBasisObservation(
            "REVIEW_ROUND", uuid4(), "PROJECT", self.project, "APPROVED",
            2, b"r" * 32, self.now, 1,
        )
        self.basis = tuple(sorted(
            (evidence, review), key=lambda value: (
                value.ref_kind, str(value.ref_id),
            ),
        ))
        self.command = AppendChecklistRecord(
            uuid4(), uuid4(), ChecklistState.PASS, self.basis, self.now,
        )

    def test_first_and_correction_lock_shapes(self):
        correction = ChecklistRecordWriteLock(
            self.workflow, self.project, 1, "HANDOVER", "BLOCKED",
            "HANDOVER_BASELINE", ChecklistState.FAIL, 4, 9, uuid4(),
        )
        self.assertEqual(self.lock.before_item_version, 0)
        self.assertEqual(correction.before_state, ChecklistState.FAIL)

    def test_lock_rejects_wrong_stage_or_broken_chain(self):
        for changes in (
            dict(stage_key="SURVEY"),
            dict(before_item_version=1),
            dict(before_state=ChecklistState.FAIL),
            dict(
                before_item_version=1,
                supersedes_record_id=uuid4(),
            ),
        ):
            with self.subTest(changes=changes), self.assertRaises(
                    ChecklistRecordAppendError):
                replace(self.lock, **changes)

    def test_command_requires_canonical_unique_basis(self):
        duplicate = (self.basis[0], self.basis[0])
        reversed_basis = tuple(reversed(self.basis))
        for basis in (duplicate, reversed_basis, list(self.basis)):
            with self.subTest(basis=basis), self.assertRaises(
                    ChecklistRecordAppendError):
                AppendChecklistRecord(
                    uuid4(), uuid4(), ChecklistState.PASS,
                    basis, self.now,
                )

    def test_fingerprint_binds_stage_and_current_observations(self):
        record = ChecklistRecordSnapshot(
            uuid4(), self.workflow, self.project,
            self.command.actor_id, self.command.trace_id,
            1, "HANDOVER", "HANDOVER_BASELINE",
            ChecklistState.PENDING, ChecklistState.PASS,
            0, 1, 2, 3, self.now,
            evidence_refs=tuple(value.ref_id for value in self.basis
                                if value.ref_kind == "EVIDENCE"),
            review_round_refs=tuple(value.ref_id for value in self.basis
                                    if value.ref_kind == "REVIEW_ROUND"),
        )
        first = checklist_record_fingerprint(record, self.basis, "ACTIVE")
        self.assertEqual(len(first), 32)
        self.assertNotEqual(
            first, checklist_record_fingerprint(record, self.basis, "BLOCKED"),
        )
        changed = replace(
            self.basis[0], observed_lock_version=2,
        )
        changed_basis = tuple(sorted(
            (changed, self.basis[1]),
            key=lambda value: (value.ref_kind, str(value.ref_id)),
        ))
        self.assertNotEqual(
            first, checklist_record_fingerprint(
                record, changed_basis, "ACTIVE",
            ),
        )


if __name__ == "__main__":
    unittest.main()
