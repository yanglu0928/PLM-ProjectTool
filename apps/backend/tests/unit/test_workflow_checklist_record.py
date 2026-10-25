from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import unittest

from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordError, ChecklistRecordSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState as State


class ChecklistRecordTests(unittest.TestCase):
    def setUp(self):
        self.first = ChecklistRecordSnapshot(uuid4(), uuid4(), uuid4(), uuid4(), uuid4(),
            1, "HANDOVER", "HANDOVER_BASELINE", State.PENDING, State.FAIL, 0, 1, 19, 20,
            datetime.now(timezone.utc))

    def for_result(self, result):
        return replace(self.first, result=result,
            evidence_refs=(uuid4(),) if result != State.FAIL else (),
            review_round_refs=(uuid4(),) if result != State.FAIL else (),
            exception_refs=(uuid4(),) if result == State.WAIVED else (),
            reason="explicit bounded exception" if result == State.WAIVED else None,
            impact="identified impact" if result == State.WAIVED else None)

    def test_twelve_fixed_items_and_three_first_results(self):
        for stage in six_stage_definition().stages:
            for item in stage.checklist_items:
                for result in (State.PASS, State.FAIL, State.WAIVED):
                    with self.subTest(stage=stage.stage_key, item=item.item_key, result=result):
                        replace(self.for_result(result), stage_key=stage.stage_key, item_key=item.item_key)

    def test_all_nine_corrections_keep_old_record_and_distinct_versions(self):
        for before in (State.PASS, State.FAIL, State.WAIVED):
            old = self.for_result(before)
            for result in (State.PASS, State.FAIL, State.WAIVED):
                corrected = replace(self.for_result(result), record_id=uuid4(), before_state=before,
                    before_item_version=1, after_item_version=2, supersedes_record_id=old.record_id,
                    before_workflow_version=20, after_workflow_version=21)
                self.assertEqual(corrected.supersedes_record_id, old.record_id)
                self.assertEqual(old.result, before)
                self.assertEqual(corrected.before_workflow_version, 20)
                self.assertEqual(corrected.before_item_version, 1)

    def test_fail_can_express_missing_basis_without_invented_reasons(self):
        self.assertEqual(self.first.evidence_refs, ())
        self.assertIsNone(self.first.reason)
        replace(self.first, reason="source unavailable", impact="needs follow-up")
        with self.assertRaises(ChecklistRecordError):
            replace(self.first, exception_refs=(uuid4(),))

    def test_first_and_correction_chain_guards(self):
        for values in (dict(supersedes_record_id=uuid4()), dict(before_state=State.PASS),
                       dict(before_item_version=1, after_item_version=2),
                       dict(before_item_version=1, after_item_version=2, before_state=State.FAIL),
                       dict(before_item_version=1, after_item_version=2, before_state=State.FAIL,
                            supersedes_record_id=self.first.record_id)):
            with self.subTest(values=values), self.assertRaises(ChecklistRecordError):
                replace(self.first, **values)
        for value in (None, UUID(int=0), "latest"):
            with self.assertRaises(ChecklistRecordError):
                replace(self.first, before_state=State.FAIL, before_item_version=1,
                        after_item_version=2, supersedes_record_id=value)

    def test_positive_results_require_basis_and_waiver_requires_details(self):
        for result in (State.PASS, State.WAIVED):
            positive = self.for_result(result)
            for field in ("evidence_refs", "review_round_refs"):
                with self.assertRaises(ChecklistRecordError):
                    replace(positive, **{field: ()})
        waiver = self.for_result(State.WAIVED)
        for field, value in (("exception_refs", ()), ("reason", None), ("impact", None),
                             ("reason", "\u3000"), ("impact", " "), ("reason", "x"*2001)):
            with self.assertRaises(ChecklistRecordError):
                replace(waiver, **{field: value})

    def test_reference_identity_immutability_and_set_boundaries(self):
        with self.assertRaises(FrozenInstanceError):
            self.first.result = State.PASS
        for field in ("record_id", "workflow_id", "project_id", "actor_id", "trace_id"):
            for value in (UUID(int=0), "uuid", None):
                with self.subTest(field=field), self.assertRaises(ChecklistRecordError):
                    replace(self.first, **{field: value})
        ref = uuid4()
        for field in ("evidence_refs", "review_round_refs", "exception_refs"):
            for value in ([ref], (ref, ref), ("latest",), (UUID(int=0),)):
                with self.subTest(field=field), self.assertRaises(ChecklistRecordError):
                    replace(self.first, **{field: value})

    def test_scalar_type_version_result_stage_and_utc_rejection(self):
        for field, value in (("definition_version", True), ("definition_version", 2),
                             ("stage_key", "SURVEY"), ("item_key", "LATEST"),
                             ("item_key", []), ("stage_key", None), ("before_state", "PENDING"),
                             ("result", "FAIL"), ("result", State.PENDING),
                             ("occurred_at", datetime.now()),
                             ("occurred_at", datetime.now(timezone(timedelta(hours=8)))),
                             ("reason", " "), ("impact", "x\x00")):
            with self.subTest(field=field, value=value), self.assertRaises(ChecklistRecordError):
                replace(self.first, **{field: value})
        for field in ("before_item_version", "before_workflow_version",
                      "after_item_version", "after_workflow_version"):
            for value in (True, -1, "1", 1.0, 2**63):
                with self.subTest(field=field, value=value), self.assertRaises(ChecklistRecordError):
                    replace(self.first, **{field: value})

    def test_lock_version_overflow_and_stale_pair_rejected(self):
        replace(self.first, before_workflow_version=2**63-2, after_workflow_version=2**63-1)
        for values in (dict(before_workflow_version=2**63-1, after_workflow_version=2**63),
                       dict(before_item_version=0, after_item_version=2),
                       dict(before_workflow_version=19, after_workflow_version=19)):
            with self.assertRaises(ChecklistRecordError):
                replace(self.first, **values)
