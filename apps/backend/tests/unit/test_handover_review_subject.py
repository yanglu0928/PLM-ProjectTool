from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
import unittest

from plm_assistant.modules.capability.application.read_capability import (
    CapabilityVersionView,
)
from plm_assistant.modules.evidence.application.fixed_source_record import (
    LockedEvidenceSource,
)
from plm_assistant.modules.handover.application.create_version import (
    HandoverAnalysisItemDraft, HandoverItemOptionDraft,
)
from plm_assistant.modules.handover.application.review_subject import (
    HandoverReviewLock, HandoverReviewSubjectOwner,
)
from plm_assistant.modules.handover.application.source_validation import (
    HandoverDocumentRef, ValidatedHandoverSourceSet,
)
from plm_assistant.modules.handover.application.validate_version import (
    HandoverVersionSnapshot, HandoverVersionValidationService,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import (
    CreatedReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
    ReviewWithdrawalSnapshot,
)


class HandoverReviewSubjectTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.reviewer = uuid4(), uuid4()
        self.project, self.analysis, self.version = uuid4(), uuid4(), uuid4()
        self.review, self.round = uuid4(), uuid4()
        self.document, self.document_version = uuid4(), uuid4()
        self.evidence_id, self.item_id = uuid4(), uuid4()
        self.capability, self.capability_version = uuid4(), uuid4()
        item = HandoverAnalysisItemDraft(
            self.item_id, "NEED_CONFIRM", "Confirm scope",
            "Customer scope is unresolved", "Delivery may be delayed",
            "HIGH", "HIGH", "Confirm one option", "Which scope?",
            {"fields": [{"name": "scope", "format": "text",
                         "example": "Option A", "required": True}]},
            False, (self.evidence_id,), (),
            (HandoverItemOptionDraft("A", "Option A"),
             HandoverItemOptionDraft("B", "Option B")),
        )
        document = HandoverDocumentRef(self.document, self.document_version)
        initial = HandoverVersionSnapshot(
            self.analysis, self.version, self.project, 1, "DRAFT",
            "sha256:" + "a" * 64, self.capability,
            self.capability_version, b"x" * 32, (document,), (item,), (),
        )
        fingerprint = canonical_payload_fingerprint(
            HandoverVersionValidationService._snapshot_payload(initial)
        )
        self.snapshot = replace(initial, content_fingerprint=fingerprint)
        self.lock = HandoverReviewLock(
            self.snapshot, "ACTIVE", 0, None, self.version, None, None,
            ((self.item_id, "CANDIDATE"),), frozenset({self.item_id}),
        )
        self.identity = ReviewIdentitySnapshot(
            self.review, "PROJECT", self.project, "HND-02", self.analysis,
            "HANDOVER_ALL_V1", "DRAFT", None, 0,
        )
        self.request = ReviewSubjectStartRequest(
            self.actor, self.identity, self.round, self.version,
            (self.reviewer,),
        )
        (self.repository, self.reviewers, self.sources, self.evidence,
         self.capabilities, self.ai_tasks, self.audit) = (
            Mock() for _ in range(7)
        )
        self.repository.lock_subject.return_value = self.lock
        self.repository.active_analysis_exists.return_value = True
        self.repository.assert_terminal_consumed = Mock()
        self.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(
                self.reviewer, self.project, "CUSTOMER_MANAGER",
            ),
        )
        self.sources.validate.return_value = ValidatedHandoverSourceSet(
            self.snapshot.source_set_ref, self.snapshot.source_documents,
        )
        self.evidence.get_for_trace.return_value = LockedEvidenceSource(
            self.evidence_id, "PROJECT", self.project, self.document,
            self.document_version, None, {"page": 1}, b"e" * 32, 2,
        )
        self.capabilities.get_version.return_value = CapabilityVersionView(
            self.capability_version, self.capability, 1, "APPROVED",
            "sha256:" + "b" * 64, "sha256:" + "c" * 64, 0, 0, 0,
            None, None, None, self.now,
        )
        self.capabilities.list_items.return_value = ()
        self.owner = HandoverReviewSubjectOwner(
            repository=self.repository, reviewers=self.reviewers,
            sources=self.sources, evidence=self.evidence,
            capabilities=self.capabilities, ai_tasks=self.ai_tasks,
            audit=self.audit, clock=lambda: self.now,
        )
        self.tx = object()

    def test_create_owner_binds_latest_draft_and_policy(self):
        proof = self.owner.authorize_create(
            self.tx, user_id=self.actor, project_id=self.project,
            subject_type="HND-02", subject_id=self.analysis,
            subject_version_id=self.version,
        )
        self.assertEqual(proof.policy_code, "HANDOVER_ALL_V1")
        created = CreatedReviewRef(
            self.review, self.project, "HND-02", self.analysis,
            "HANDOVER_ALL_V1", self.actor, self.now,
        )
        self.assertTrue(self.owner.authorize_replay(
            self.tx, user_id=self.actor, review=created,
        ))
        self.repository.lock_subject.return_value = replace(
            self.lock, latest_version_id=uuid4(),
        )
        self.assertIsNone(self.owner.authorize_create(
            self.tx, user_id=self.actor, project_id=self.project,
            subject_type="HND-02", subject_id=self.analysis,
            subject_version_id=self.version,
        ))

    def test_prepare_rechecks_reviewers_sources_evidence_and_action(self):
        prepared = self.owner.prepare_start_in_transaction(
            self.tx, self.request,
        )
        self.assertEqual(prepared.content_fingerprint,
                         self.snapshot.content_fingerprint)
        self.assertEqual(prepared.qualified_reviewer_ids,
                         (self.reviewer,))
        self.assertEqual(len(prepared.basis), 1)
        self.assertEqual(prepared.basis[0].ref_id, self.evidence_id)
        self.owner.finalize_start_in_transaction(self.tx, self.request)
        self.repository.bind_start.assert_called_once_with(
            self.tx, before=self.lock, review_id=self.review,
            round_id=self.round, actor_id=self.actor,
        )

    def test_missing_action_reviewer_or_current_fact_fails_closed(self):
        self.repository.lock_subject.return_value = replace(
            self.lock, active_action_item_ids=frozenset(),
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        self.repository.lock_subject.return_value = self.lock
        self.reviewers.qualify_in_transaction.side_effect = (
            ReviewReviewerEligibilityError()
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        self.reviewers.qualify_in_transaction.side_effect = None
        self.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(
                self.reviewer, self.project, "CUSTOMER_MANAGER",
            ),
        )
        self.evidence.get_for_trace.return_value = None
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)

    def test_terminal_approval_revalidates_and_consumes(self):
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            analysis_lock_version=1, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        progress = ReviewRoundProgress(
            self.round, self.now, (self.reviewer,),
        )
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=self.round,
            lock_version=1,
        )
        fixed = FixedReviewRoundSnapshot(
            review, 1, self.version, self.actor, progress, (uuid4(),), 0,
            uuid4(), self.snapshot.content_fingerprint, 1, self.now, (),
            uuid4(), self.now, None,
        )
        decision = ReviewDecisionSnapshot(
            uuid4(), self.round, self.reviewer,
            ReviewDecisionKind.APPROVE, self.now,
        )
        transition = ReviewSubjectTransition(
            self.reviewer, uuid4(), fixed,
            progress.record_decision(decision), self.now,
        )
        self.owner.require_transition_access_in_transaction(
            self.tx, transition,
        )
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="APPROVED",
        )
        self.owner.assert_terminal_consumed_in_transaction(
            self.tx, transition,
        )
        self.repository.assert_terminal_consumed.assert_called_once_with(
            self.tx, transition=transition, version_state="APPROVED",
        )
        event = self.audit.append.call_args.args[1]
        self.assertEqual(event.action, "HND_VERSION_APPROVED")
        self.assertEqual(event.after_state, "APPROVED")

    def test_withdrawal_does_not_require_stale_sources(self):
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            analysis_lock_version=1, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        progress = ReviewRoundProgress(
            self.round, self.now, (self.reviewer, uuid4()),
        )
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=self.round,
            lock_version=1,
        )
        fixed = FixedReviewRoundSnapshot(
            review, 1, self.version, self.actor, progress,
            (uuid4(), uuid4()), 0, uuid4(),
            self.snapshot.content_fingerprint, 1, self.now, (), uuid4(),
            self.now, None,
        )
        transition = ReviewSubjectTransition(
            self.actor, uuid4(), fixed,
            progress.withdraw(ReviewWithdrawalSnapshot(
                self.actor, self.now, "Source changed",
            )), self.now,
        )
        self.evidence.get_for_trace.return_value = None
        self.owner.require_transition_access_in_transaction(
            self.tx, transition,
        )
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="RETURNED",
        )
        self.evidence.get_for_trace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
