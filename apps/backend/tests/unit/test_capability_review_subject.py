from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
import unittest

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.capability.application.create_version import (
    CapabilityItemDraft,
)
from plm_assistant.modules.capability.application.review_subject import (
    CapabilityReviewLock,
    CapabilityReviewSubjectOwner,
)
from plm_assistant.modules.capability.application.source_validation import (
    CapabilityDocumentRef,
    ValidatedCapabilitySourceSet,
)
from plm_assistant.modules.capability.application.validate_version import (
    CapabilityVersionSnapshot,
)
from plm_assistant.modules.evidence.application.fixed_source_record import (
    LockedEvidenceSource,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
    ReviewSubjectTransitionError,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
    ReviewDecisionSnapshot,
    ReviewRoundProgress,
    ReviewWithdrawalSnapshot,
)


class CapabilityReviewSubjectTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.reviewer, self.other = uuid4(), uuid4(), uuid4()
        self.baseline, self.version = uuid4(), uuid4()
        self.review, self.round = uuid4(), uuid4()
        self.document, self.document_version, self.evidence_id = (
            uuid4(), uuid4(), uuid4(),
        )
        self.document_ref = CapabilityDocumentRef(
            self.document, self.document_version,
        )
        self.item = CapabilityItemDraft(
            uuid4(), "PLM.TEST", "PLM", "Test", "Review", "Review",
            "Review capability", "GLOBAL only", (), (), "AVAILABLE",
            (self.document_ref,), (self.evidence_id,),
        )
        self.snapshot = CapabilityVersionSnapshot(
            self.baseline, self.version, 1, "DRAFT", "sha256:" + "a" * 64,
            b"f" * 32, (self.item,),
        )
        self.lock = CapabilityReviewLock(
            self.snapshot, "ACTIVE", 1, None, self.version, None, None,
        )
        self.identity = ReviewIdentitySnapshot(
            self.review, "GLOBAL", None, "CAP-01", self.baseline,
            "DEPLOYMENT_ALL_V1", "DRAFT", None, 0,
        )
        self.request = ReviewSubjectStartRequest(
            self.actor, self.identity, self.round, self.version,
            (self.reviewer, self.other),
        )
        self.users, self.repository, self.sources, self.evidence, self.audit = (
            Mock(), Mock(), Mock(), Mock(), Mock(),
        )
        self.users.current_enabled_user.side_effect = lambda tx, user_id: (
            CurrentUserFacts(
                user_id,
                "DEPLOYMENT_ADMIN" if user_id == self.actor else "NONE",
            )
        )
        self.repository.lock_subject.return_value = self.lock
        self.repository.assert_terminal_consumed = Mock()
        self.sources.validate.return_value = ValidatedCapabilitySourceSet(
            self.snapshot.source_collection_ref, (self.document_ref,),
        )
        self.evidence.get_for_trace.return_value = LockedEvidenceSource(
            self.evidence_id, "GLOBAL", None, self.document,
            self.document_version, None, {"page": 1}, b"e" * 32, 2,
        )
        self.owner = CapabilityReviewSubjectOwner(
            users=self.users, repository=self.repository,
            sources=self.sources, evidence=self.evidence,
            audit=self.audit, terminal_enabled=False,
            clock=lambda: self.now,
        )
        self.tx = object()

    def test_prepare_rechecks_admin_reviewers_sources_and_evidence(self):
        prepared = self.owner.prepare_start_in_transaction(
            self.tx, self.request,
        )
        self.assertEqual(prepared.content_fingerprint, b"f" * 32)
        self.assertEqual(prepared.qualified_reviewer_ids,
                         self.request.reviewer_ids)
        self.assertEqual(len(prepared.basis), 1)
        self.assertEqual(prepared.basis[0].ref_id, self.evidence_id)
        checked = {
            call.kwargs["user_id"]
            for call in self.users.current_enabled_user.call_args_list
        }
        self.assertEqual(checked,
                         {self.actor, self.reviewer, self.other})

    def test_finalize_binds_exact_review_and_active_assertion(self):
        self.owner.finalize_start_in_transaction(self.tx, self.request)
        self.repository.bind_start.assert_called_once_with(
            self.tx, before=self.lock, review_id=self.review,
            round_id=self.round, actor_id=self.actor,
        )
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            baseline_lock_version=2, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        self.assertIsNone(self.owner.assert_active_lock_in_transaction(
            self.tx, self.request,
        ))

    def test_non_admin_disabled_reviewer_and_wrong_scope_fail_closed(self):
        self.users.current_enabled_user.side_effect = lambda tx, user_id: (
            CurrentUserFacts(user_id, "NONE")
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        self.users.current_enabled_user.side_effect = lambda tx, user_id: (
            None if user_id == self.other else CurrentUserFacts(
                user_id, "DEPLOYMENT_ADMIN" if user_id == self.actor else "NONE",
            )
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        project = replace(
            self.identity, scope="PROJECT", project_id=uuid4(),
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(
                self.tx, replace(self.request, review=project),
            )

    def test_nonlatest_source_drift_and_evidence_loss_rejected(self):
        self.repository.lock_subject.return_value = replace(
            self.lock, latest_version_id=uuid4(),
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        self.repository.lock_subject.return_value = self.lock
        self.sources.validate.return_value = ValidatedCapabilitySourceSet(
            "sha256:" + "b" * 64, (self.document_ref,),
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        self.sources.validate.return_value = ValidatedCapabilitySourceSet(
            self.snapshot.source_collection_ref, (self.document_ref,),
        )
        self.evidence.get_for_trace.return_value = None
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)

    def test_nonterminal_transition_access_but_terminal_consumption_closed(self):
        progress = ReviewRoundProgress(
            self.round, self.now, (self.reviewer, self.other),
        )
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=self.round,
            lock_version=1,
        )
        fixed = FixedReviewRoundSnapshot(
            review, 1, self.version, self.actor, progress,
            (uuid4(), uuid4()), 0, uuid4(), b"f" * 32, 1,
            self.now, (), uuid4(), self.now, None,
        )
        decision = ReviewDecisionSnapshot(
            uuid4(), self.round, self.reviewer,
            ReviewDecisionKind.APPROVE, self.now, None,
        )
        transition = ReviewSubjectTransition(
            self.reviewer, uuid4(), fixed,
            progress.record_decision(decision), self.now,
        )
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            baseline_lock_version=2, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        self.assertIsNone(self.owner.require_transition_access_in_transaction(
            self.tx, transition,
        ))
        self.assertIsNone(self.owner.assert_transition_lock_in_transaction(
            self.tx, transition,
        ))
        with self.assertRaises(ReviewSubjectTransitionError):
            self.owner.consume_terminal_in_transaction(self.tx, transition)

    def test_terminal_outcomes_are_consumed_and_independently_asserted(self):
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=self.round,
            lock_version=1,
        )
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            baseline_lock_version=2, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        owner = CapabilityReviewSubjectOwner(
            users=self.users, repository=self.repository,
            sources=self.sources, evidence=self.evidence, audit=self.audit,
            clock=lambda: self.now,
        )
        for expected, decision in (
                ("APPROVED", ReviewDecisionKind.APPROVE),
                ("RETURNED", ReviewDecisionKind.RETURN)):
            with self.subTest(expected=expected):
                progress = ReviewRoundProgress(
                    self.round, self.now, (self.reviewer,),
                )
                fixed = FixedReviewRoundSnapshot(
                    review, 1, self.version, self.actor, progress,
                    (uuid4(),), 0, uuid4(), b"f" * 32, 1,
                    self.now, (), uuid4(), self.now, None,
                )
                entry = ReviewDecisionSnapshot(
                    uuid4(), self.round, self.reviewer, decision, self.now,
                    "return for revision" if decision is ReviewDecisionKind.RETURN
                    else None,
                )
                transition = ReviewSubjectTransition(
                    self.reviewer, uuid4(), fixed,
                    progress.record_decision(entry), self.now,
                )
                owner.require_transition_access_in_transaction(
                    self.tx, transition,
                )
                owner.consume_terminal_in_transaction(self.tx, transition)
                self.repository.consume_terminal.assert_called_with(
                    self.tx, before=active, transition=transition,
                    version_state=expected,
                )
                owner.assert_terminal_consumed_in_transaction(
                    self.tx, transition,
                )
                self.repository.assert_terminal_consumed.assert_called_with(
                    self.tx, transition=transition, version_state=expected,
                )

        progress = ReviewRoundProgress(
            self.round, self.now, (self.reviewer, self.other),
        )
        fixed = FixedReviewRoundSnapshot(
            review, 1, self.version, self.actor, progress,
            (uuid4(), uuid4()), 0, uuid4(), b"f" * 32, 1,
            self.now, (), uuid4(), self.now, None,
        )
        withdrawn = ReviewSubjectTransition(
            self.actor, uuid4(), fixed,
            progress.withdraw(ReviewWithdrawalSnapshot(
                self.actor, self.now, "scope changed",
            )), self.now,
        )
        owner.require_transition_access_in_transaction(self.tx, withdrawn)
        owner.consume_terminal_in_transaction(self.tx, withdrawn)
        self.repository.consume_terminal.assert_called_with(
            self.tx, before=active, transition=withdrawn,
            version_state="RETURNED",
        )
        audit = self.audit.append.call_args.args[1]
        self.assertEqual(audit.action, "CAP_VERSION_WITHDRAWN")
        self.assertEqual(audit.after_state, "RETURNED")


if __name__ == "__main__":
    unittest.main()
