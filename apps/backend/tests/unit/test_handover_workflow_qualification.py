from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4
import unittest

from plm_assistant.modules.handover.application.workflow_qualification import (
    HandoverChecklistQualification, HandoverWorkflowActionFact,
    HandoverWorkflowEvidenceObservation, HandoverWorkflowItemFact,
    HandoverWorkflowQualificationError, HandoverWorkflowQualificationPolicy,
    HandoverWorkflowQualificationSnapshot, HandoverWorkflowReviewObservation,
)


class HandoverWorkflowQualificationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.project, self.analysis, self.version = uuid4(), uuid4(), uuid4()
        self.review_id, self.round_id = uuid4(), uuid4()
        self.source_evidence = uuid4()
        self.submission_evidence, self.verification_evidence = uuid4(), uuid4()
        self.fingerprint = b"h" * 32
        self.review = HandoverWorkflowReviewObservation(
            self.review_id, self.round_id, self.project, self.analysis,
            self.version, 3, self.fingerprint, self.now,
        )
        self.evidence = tuple(
            HandoverWorkflowEvidenceObservation(
                evidence_id, self.project, index, bytes([index]) * 32,
                self.now,
            )
            for index, evidence_id in enumerate((
                self.source_evidence, self.submission_evidence,
                self.verification_evidence,
            ), start=1)
        )
        self.action = HandoverWorkflowActionFact(
            uuid4(), "VERIFIED", (uuid4(),),
            (self.submission_evidence,), (self.verification_evidence,),
        )
        self.item = HandoverWorkflowItemFact(
            uuid4(), "NEED_CONFIRM", False, (self.action,),
        )
        self.snapshot = HandoverWorkflowQualificationSnapshot(
            self.project, self.analysis, self.version, self.version,
            "ACTIVE", "APPROVED", self.fingerprint,
            (self.source_evidence,), self.evidence, self.review, (self.item,),
        )
        self.policy = HandoverWorkflowQualificationPolicy()

    def test_baseline_and_issues_return_fixed_current_basis(self):
        baseline = self.policy.qualify(self.snapshot, "HANDOVER_BASELINE")
        issues = self.policy.qualify(self.snapshot, "HANDOVER_ISSUES")
        self.assertIsInstance(baseline, HandoverChecklistQualification)
        self.assertEqual(tuple(value.evidence_id for value in baseline.evidence), (
            self.source_evidence, self.submission_evidence,
            self.verification_evidence,
        ))
        self.assertEqual(tuple(value.evidence_id for value in issues.evidence), (
            self.source_evidence, self.submission_evidence,
            self.verification_evidence,
        ))
        self.assertEqual(issues.review.review_round_id, self.round_id)
        self.assertNotEqual(baseline.content_fingerprint,
                            issues.content_fingerprint)

    def test_closed_action_requires_resolution_trace_and_is_qualified(self):
        closed = replace(self.action, action_state="CLOSED",
                         resolution_trace_ref=uuid4())
        result = self.policy.qualify(
            replace(self.snapshot, items=(replace(self.item,
                                                  actions=(closed,)),)),
            "HANDOVER_ISSUES",
        )
        self.assertEqual(result.handover_analysis_version_id, self.version)
        with self.assertRaises(HandoverWorkflowQualificationError):
            replace(closed, resolution_trace_ref=None)

    def test_submitted_open_or_only_cancelled_cannot_satisfy_issue(self):
        for state in ("OPEN", "IN_PROGRESS", "SUBMITTED", "CANCELLED"):
            action = (replace(self.action, action_state=state,
                              response_document_version_refs=(),
                              submission_evidence_refs=(),
                              verification_evidence_refs=())
                      if state in ("OPEN", "IN_PROGRESS", "CANCELLED")
                      else replace(self.action, action_state=state,
                                   verification_evidence_refs=()))
            current = replace(self.snapshot, items=(replace(
                self.item, actions=(action,),
            ),))
            with self.subTest(state=state), self.assertRaises(
                    HandoverWorkflowQualificationError):
                self.policy.qualify(current, "HANDOVER_ISSUES")

    def test_qualified_duplicate_does_not_hide_open_action(self):
        open_action = HandoverWorkflowActionFact(uuid4(), "OPEN")
        current = replace(self.snapshot, items=(replace(
            self.item, actions=(self.action, open_action),
        ),))
        with self.assertRaises(HandoverWorkflowQualificationError):
            self.policy.qualify(current, "HANDOVER_ISSUES")

    def test_cancelled_replacement_is_ignored_when_verified_exists(self):
        cancelled = HandoverWorkflowActionFact(uuid4(), "CANCELLED")
        current = replace(self.snapshot, items=(replace(
            self.item, actions=(cancelled, self.action),
        ),))
        self.policy.qualify(current, "HANDOVER_ISSUES")

    def test_blocking_rule_is_conservative_and_deterministic(self):
        for item_type, source_missing, blocking in (
            ("NEED_CONFIRM", False, True), ("CONFLICT", False, True),
            ("RISK", False, True), ("MISSING", True, True),
            ("MISSING", False, False), ("GAP", False, False),
            ("SCOPE", False, False),
        ):
            item = HandoverWorkflowItemFact(
                uuid4(), item_type, source_missing,
                (self.action,) if blocking else (),
            )
            with self.subTest(item_type=item_type,
                              source_missing=source_missing):
                self.assertEqual(item.blocking, blocking)
                self.policy.qualify(
                    replace(self.snapshot, items=(item,)),
                    "HANDOVER_ISSUES",
                )

    def test_evidence_must_be_current_owner_observation(self):
        for current in (
            replace(self.snapshot, evidence=self.evidence[:1]),
            replace(self.snapshot, source_evidence_refs=(uuid4(),)),
            replace(self.snapshot, source_evidence_refs=(), evidence=()),
        ):
            with self.assertRaises(HandoverWorkflowQualificationError):
                self.policy.qualify(current, "HANDOVER_BASELINE")

    def test_qualification_fingerprint_binds_current_evidence_observation(self):
        original = self.policy.qualify(
            self.snapshot, "HANDOVER_BASELINE",
        )
        changed_evidence = tuple(
            replace(value, observed_lock_version=value.observed_lock_version + 1)
            if value.evidence_id == self.source_evidence else value
            for value in self.evidence
        )
        changed = self.policy.qualify(
            replace(self.snapshot, evidence=changed_evidence),
            "HANDOVER_BASELINE",
        )
        self.assertNotEqual(original.content_fingerprint,
                            changed.content_fingerprint)

    def test_output_rejects_cross_project_nested_observations(self):
        qualified = self.policy.qualify(
            self.snapshot, "HANDOVER_BASELINE",
        )
        with self.assertRaises(HandoverWorkflowQualificationError):
            replace(qualified, evidence=(replace(
                qualified.evidence[0], project_id=uuid4(),
            ),) + qualified.evidence[1:])
        with self.assertRaises(HandoverWorkflowQualificationError):
            replace(qualified, review=replace(
                qualified.review, subject_version_id=uuid4(),
            ))

    def test_review_and_formal_version_must_match(self):
        changes = (
            {"current_approved_version_ref": uuid4()},
            {"analysis_state": "ARCHIVED"},
            {"version_state": "SUPERSEDED"},
            {"review": replace(self.review, subject_version_id=uuid4())},
            {"review": replace(self.review, subject_fingerprint=b"x" * 32)},
        )
        for values in changes:
            with self.subTest(values=values), self.assertRaises(
                    HandoverWorkflowQualificationError):
                replace(self.snapshot, **values)

    def test_unknown_item_or_malformed_identity_fails_closed(self):
        for item_key in ("SURVEY_CONCLUSION", "", None):
            with self.subTest(item_key=item_key), self.assertRaises(
                    HandoverWorkflowQualificationError):
                self.policy.qualify(self.snapshot, item_key)
        with self.assertRaises(HandoverWorkflowQualificationError):
            replace(self.review, review_id=UUID(int=0))
        with self.assertRaises(HandoverWorkflowQualificationError):
            replace(self.evidence[0], verified_at=datetime.now())


if __name__ == "__main__":
    unittest.main()
