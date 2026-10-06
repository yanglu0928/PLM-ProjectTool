from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4
import unittest

from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts, ReviewReviewerEligibilityError,
)
from plm_assistant.modules.review.application.create_review import CreatedReviewRef
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
from plm_assistant.modules.survey.application.create_version import (
    SurveyQuestionDraft, SurveySourceDraft,
)
from plm_assistant.modules.survey.application.review_subject import (
    SurveyReviewLock, SurveyReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionSnapshot,
)


class SurveyReviewSubjectTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.reviewer = uuid4(), uuid4()
        self.project, self.survey, self.version = uuid4(), uuid4(), uuid4()
        self.review, self.round = uuid4(), uuid4()
        question = SurveyQuestionDraft(
            uuid4(), "Scope", "Confirm scope", "Fix scope", "TEXT", {},
            True, None, "Confirmed scope", False, (),
            (SurveySourceDraft(
                "MANUAL", manual_source_note="Facilitator source",
            ),),
        )
        self.snapshot = SurveyVersionSnapshot(
            self.survey, self.version, self.project, 1, "DRAFT", b"s" * 32,
            1, 0, 1, 1, (question,), (uuid4(),), True,
        )
        self.lock = SurveyReviewLock(
            self.snapshot, "ACTIVE", 0, None, self.version, None, None,
        )
        self.identity = ReviewIdentitySnapshot(
            self.review, "PROJECT", self.project, "SRV-02", self.survey,
            "SURVEY_ALL_V1", "DRAFT", None, 0,
        )
        self.request = ReviewSubjectStartRequest(
            self.actor, self.identity, self.round, self.version,
            (self.reviewer,),
        )
        self.repository, self.reviewers, self.current, self.audit = (
            Mock() for _ in range(4)
        )
        self.repository.lock_subject.return_value = self.lock
        self.repository.active_survey_exists.return_value = True
        self.repository.assert_terminal_consumed = Mock()
        self.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(
                self.reviewer, self.project, "CUSTOMER_MANAGER",
            ),
        )
        self.current.current_issues.return_value = ()
        self.owner = SurveyReviewSubjectOwner(
            repository=self.repository, reviewers=self.reviewers,
            current=self.current, audit=self.audit, clock=lambda: self.now,
        )
        self.tx = object()

    def test_create_owner_binds_latest_draft_and_policy(self):
        proof = self.owner.authorize_create(
            self.tx, user_id=self.actor, project_id=self.project,
            subject_type="SRV-02", subject_id=self.survey,
            subject_version_id=self.version,
        )
        self.assertEqual(proof.policy_code, "SURVEY_ALL_V1")
        created = CreatedReviewRef(
            self.review, self.project, "SRV-02", self.survey,
            "SURVEY_ALL_V1", self.actor, self.now,
        )
        self.assertTrue(self.owner.authorize_replay(
            self.tx, user_id=self.actor, review=created,
        ))
        self.repository.lock_subject.return_value = replace(
            self.lock, latest_version_id=uuid4(),
        )
        self.assertIsNone(self.owner.authorize_create(
            self.tx, user_id=self.actor, project_id=self.project,
            subject_type="SRV-02", subject_id=self.survey,
            subject_version_id=self.version,
        ))

    def test_prepare_revalidates_and_finalizes_exact_binding(self):
        prepared = self.owner.prepare_start_in_transaction(
            self.tx, self.request,
        )
        self.assertEqual(prepared.content_fingerprint,
                         self.snapshot.content_fingerprint)
        self.assertEqual(prepared.qualified_reviewer_ids, (self.reviewer,))
        self.assertEqual(prepared.basis, ())
        self.current.current_issues.assert_called_once_with(
            self.tx, self.snapshot,
        )
        self.owner.finalize_start_in_transaction(self.tx, self.request)
        self.repository.bind_start.assert_called_once_with(
            self.tx, before=self.lock, review_id=self.review,
            round_id=self.round, actor_id=self.actor,
        )

    def test_reviewer_or_current_issue_fails_closed(self):
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
        self.current.current_issues.return_value = ("SOURCE_UNAVAILABLE",)
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)

    def test_terminal_approval_revalidates_and_consumes(self):
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            survey_lock_version=1, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        progress = ReviewRoundProgress(self.round, self.now, (self.reviewer,))
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
        self.owner.require_transition_access_in_transaction(self.tx, transition)
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="APPROVED",
        )
        self.owner.assert_terminal_consumed_in_transaction(self.tx, transition)
        self.repository.assert_terminal_consumed.assert_called_once_with(
            self.tx, transition=transition, version_state="APPROVED",
        )
        event = self.audit.append.call_args.args[1]
        self.assertEqual(event.action, "SURVEY_VERSION_APPROVED")
        self.assertEqual(event.after_state, "APPROVED")

    def test_withdrawal_does_not_require_stale_sources(self):
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            survey_lock_version=1, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        other = uuid4()
        progress = ReviewRoundProgress(
            self.round, self.now, (self.reviewer, other),
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
        self.current.current_issues.return_value = ("SOURCE_UNAVAILABLE",)
        self.owner.require_transition_access_in_transaction(self.tx, transition)
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="RETURNED",
        )
        self.current.current_issues.assert_not_called()


if __name__ == "__main__":
    unittest.main()
