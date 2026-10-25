from dataclasses import FrozenInstanceError, asdict, replace
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from uuid import uuid4
from unittest.mock import Mock
from sqlalchemy.orm import Session

from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation, ChecklistRecordReadError, CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.domain.checklist_record import ChecklistRecordSnapshot
from plm_assistant.modules.workflow.domain.transition import ChecklistState
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition
from plm_assistant.modules.workflow.domain.fingerprint import definition_fingerprint
from plm_assistant.modules.workflow.infrastructure.current_checklist_repository import (
    SqlAlchemyCurrentChecklistRecordRepository,
)


class CurrentChecklistRecordTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid4()
        self.evidence = ChecklistBasisObservation("EVIDENCE", uuid4(), "PROJECT", self.project,
            "ELIGIBLE", 1, b"e"*32, datetime.now(timezone.utc), 1)
        self.review = replace(self.evidence, ref_kind="REVIEW_ROUND", ref_id=uuid4(), observed_state="APPROVED")
        self.record = ChecklistRecordSnapshot(uuid4(), uuid4(), self.project, uuid4(), uuid4(),
            1, "HANDOVER", "HANDOVER_BASELINE", ChecklistState.PENDING, ChecklistState.PASS,
            0, 1, 2, 3, datetime.now(timezone.utc), evidence_refs=(self.evidence.ref_id,),
            review_round_refs=(self.review.ref_id,))
        self.view = CurrentChecklistRecord(self.record, (self.evidence, self.review), b"r"*32, "ACTIVE", 5)

    def test_immutable_observation_not_latest_workflow_version_equality(self):
        self.assertEqual(self.view.current_workflow_version, 5)
        with self.assertRaises(FrozenInstanceError):
            self.view.current_workflow_version = 6

    def test_missing_duplicate_wrong_project_and_negative_positive_basis(self):
        for basis in ((self.evidence,), (self.evidence, self.review, self.review),
                      (replace(self.evidence, ref_project_id=uuid4()), self.review),
                      (replace(self.evidence, observed_state="REVOKED"), self.review),
                      (self.evidence, replace(self.review, observed_state="RETURNED"))):
            with self.subTest(basis=basis), self.assertRaises(ChecklistRecordReadError):
                replace(self.view, basis=basis)

    def test_fail_can_preserve_negative_observations_or_have_no_refs(self):
        failure = replace(self.record, result=ChecklistState.FAIL)
        negative = replace(self.evidence, observed_state="INELIGIBLE")
        CurrentChecklistRecord(failure, (negative, self.review), b"r"*32, "BLOCKED", 3)
        empty = replace(failure, evidence_refs=(), review_round_refs=())
        CurrentChecklistRecord(empty, (), b"r"*32, "BLOCKED", 3)

    def test_bad_proof_shape_and_scope(self):
        for changes in (dict(ref_kind="UNKNOWN"), dict(ref_scope="GLOBAL", ref_project_id=self.project),
                        dict(ref_kind="REVIEW_ROUND", ref_scope="GLOBAL", ref_project_id=None),
                        dict(content_fingerprint=b"x"), dict(proof_schema_version=True),
                        dict(observed_lock_version=True), dict(observed_lock_version=-1),
                        dict(verified_at=datetime.now()), dict(observed_state="UNKNOWN")):
            with self.subTest(changes=changes), self.assertRaises(ChecklistRecordReadError):
                replace(self.evidence, **changes)
        replace(self.evidence, ref_scope="GLOBAL", ref_project_id=None)

    def test_view_rejects_mutable_collections_and_stale_workflow(self):
        for changes in (dict(basis=list(self.view.basis)), dict(current_workflow_version=2),
                        dict(current_workflow_version=True), dict(observed_stage_state="COMPLETED"),
                        dict(content_fingerprint=b"x")):
            with self.subTest(changes=changes), self.assertRaises(ChecklistRecordReadError):
                replace(self.view, **changes)

    def test_requires_caller_transaction(self):
        with self.assertRaisesRegex(RuntimeError, "active Checklist caller transaction required"):
            SqlAlchemyCurrentChecklistRecordRepository().get(SimpleNamespace(session=None),
                                                             self.project, uuid4(), "HANDOVER_BASELINE")

    def test_broken_chain_and_projection_fail_closed(self):
        root = asdict(self.record)
        root.update(before_state="PENDING", result="PASS", content_fingerprint=b"r"*32,
                    observed_stage_state="ACTIVE")
        item = dict(lock_version=1, item_state="PASS")
        workflow = dict(workflow_version=1, definition_fingerprint=definition_fingerprint(six_stage_definition()),
                        lock_version=5)

        def read(roots, current=item, w=workflow):
            session = Mock(spec=Session)
            session.in_transaction.return_value = True
            results = [Mock(), Mock(), Mock()]
            results[0].mappings.return_value.one_or_none.return_value = w
            results[1].mappings.return_value.one_or_none.return_value = current
            results[2].mappings.return_value.all.return_value = roots
            session.execute.side_effect = results
            return SqlAlchemyCurrentChecklistRecordRepository().get(SimpleNamespace(session=session),
                self.project, self.record.workflow_id, self.record.item_key)

        for changes in (dict(before_item_version=1), dict(after_item_version=2),
                        dict(supersedes_record_id=uuid4()), dict(before_state="FAIL"),
                        dict(stage_key="SURVEY"), dict(definition_version=2),
                        dict(result="FAIL"), dict(after_workflow_version=6),
                        dict(before_workflow_version=-1)):
            with self.subTest(changes=changes), self.assertRaises(ChecklistRecordReadError):
                read([dict(root, **changes)])
        for roots, current in (([], item), ([root], dict(lock_version=2, item_state="PASS"))):
            with self.assertRaises(ChecklistRecordReadError):
                read(roots, current)
        with self.assertRaises(ChecklistRecordReadError):
            read([root], w=dict(workflow, definition_fingerprint=b"bad"))
