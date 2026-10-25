from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
import unittest

from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.history import (
    ForwardTransitionSnapshot, GateItemSnapshot, WorkflowHistoryError,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


class WorkflowHistoryTests(unittest.TestCase):
    def setUp(self):
        self.items = tuple(GateItemSnapshot(key, ChecklistState.PASS,
                           (uuid4(),), (uuid4(),)) for key in
                           ("HANDOVER_BASELINE", "HANDOVER_ISSUES"))
        self.snapshot = ForwardTransitionSnapshot(
            uuid4(), uuid4(), uuid4(), uuid4(), 1, "HANDOVER", "SURVEY",
            0, 1, "confirmed fixed source set", datetime.now(timezone.utc), self.items)

    def test_immutable_snapshot_and_nested_items(self):
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.reason = "overwrite"
        with self.assertRaises(FrozenInstanceError):
            self.items[0].result = ChecklistState.FAIL

    def test_exact_five_forward_stage_pairs(self):
        stages = six_stage_definition().stages
        for index, stage in enumerate(stages):
            items = tuple(GateItemSnapshot(item.item_key, ChecklistState.PASS,
                          (uuid4(),), (uuid4(),)) for item in stage.checklist_items)
            for target_index, target in enumerate(stages):
                with self.subTest(stage=stage.stage_key, target=target.stage_key):
                    if target_index == index + 1:
                        replace(self.snapshot, from_stage=stage.stage_key,
                                to_stage=target.stage_key, gate_items=items)
                    else:
                        with self.assertRaises(WorkflowHistoryError):
                            replace(self.snapshot, from_stage=stage.stage_key,
                                    to_stage=target.stage_key, gate_items=items)

    def test_gate_set_missing_extra_duplicate_reordered_and_foreign_rejected(self):
        foreign = GateItemSnapshot("SURVEY_CONCLUSION", ChecklistState.PASS,
                                  (uuid4(),), (uuid4(),))
        for items in ((), self.items[:1], self.items + (foreign,),
                      (self.items[0], self.items[0]), self.items[::-1],
                      (self.items[0], foreign), list(self.items)):
            with self.subTest(items=items), self.assertRaises(WorkflowHistoryError):
                replace(self.snapshot, gate_items=items)

    def test_references_must_be_unique_nonzero_tuples(self):
        ref = uuid4()
        for field in ("evidence_refs", "review_round_refs"):
            for value in ((), [ref], (ref, ref), (UUID(int=0),), ("latest",), (None,)):
                with self.subTest(field=field, value=value), self.assertRaises(WorkflowHistoryError):
                    replace(self.items[0], **{field: value})

    def test_pending_fail_raw_result_and_unknown_keys_rejected(self):
        for value in (ChecklistState.PENDING, ChecklistState.FAIL, "PASS", True, None):
            with self.subTest(value=value), self.assertRaises(WorkflowHistoryError):
                replace(self.items[0], result=value)
        for value in ("LATEST", "", None, []):
            with self.assertRaises(WorkflowHistoryError):
                replace(self.items[0], item_key=value)

    def test_waiver_requires_all_explicit_basis_and_never_changes_to_pass(self):
        waived = replace(self.items[0], result=ChecklistState.WAIVED,
                         exception_refs=(uuid4(),), waiver_actor_id=uuid4(),
                         waiver_reason="approved exception", waiver_impact="bounded risk")
        self.assertIs(waived.result, ChecklistState.WAIVED)
        replace(self.snapshot, gate_items=(waived, self.items[1]))
        for field, value in (("exception_refs", ()), ("waiver_actor_id", None),
                             ("waiver_reason", " "), ("waiver_impact", None),
                             ("waiver_reason", "x" * 2001)):
            with self.subTest(field=field), self.assertRaises(WorkflowHistoryError):
                replace(waived, **{field: value})
        with self.assertRaises(WorkflowHistoryError):
            replace(waived, result=ChecklistState.PASS)

    def test_identity_version_lock_reason_and_utc_boundaries(self):
        for field in ("workflow_id", "project_id", "actor_id", "trace_id"):
            for value in (UUID(int=0), "uuid", None):
                with self.subTest(field=field), self.assertRaises(WorkflowHistoryError):
                    replace(self.snapshot, **{field: value})
        for field, value in (("definition_version", 2), ("definition_version", True),
                             ("before_lock_version", -1), ("before_lock_version", True),
                             ("after_lock_version", 0), ("after_lock_version", True),
                             ("reason", " "), ("reason", "x" * 2001), ("reason", "x\x00"),
                             ("occurred_at", datetime.now()),
                             ("occurred_at", datetime.now(timezone(timedelta(hours=8)))),
                             ("from_stage", None), ("to_stage", "DONE")):
            with self.subTest(field=field, value=value), self.assertRaises(WorkflowHistoryError):
                replace(self.snapshot, **{field: value})
        replace(self.snapshot, before_lock_version=19, after_lock_version=20)

    def test_nested_bypassed_init_rejected(self):
        forged = replace(self.items[0])
        object.__setattr__(forged, "evidence_refs", ())
        with self.assertRaises(WorkflowHistoryError):
            replace(self.snapshot, gate_items=(forged, self.items[1]))
