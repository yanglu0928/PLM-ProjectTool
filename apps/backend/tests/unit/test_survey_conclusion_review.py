from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts,
)
from plm_assistant.modules.review.application.create_review import CreatedReviewRef
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission, SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied, ReviewSubjectProofContext,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
    ReviewWithdrawalSnapshot,
)
from plm_assistant.modules.survey.application.conclusion_review_subject import (
    SurveyConclusionReviewLock, SurveyConclusionReviewSubjectOwner,
)
from plm_assistant.modules.survey.application.submit_conclusion_review import (
    SubmitSurveyConclusionReview,
    SurveyConclusionReviewSubmissionError,
    SurveyConclusionReviewSubmissionService,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    ConclusionValidationSnapshot,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
ACTOR, REVIEWER, PROJECT, SURVEY, CONCLUSION, SERIES = (
    uuid.uuid4() for _ in range(6))
REVIEW, ROUND = uuid.uuid4(), uuid.uuid4()
TOKEN = b"s" * 32


def validation_snapshot(state="DRAFT"):
    return ConclusionValidationSnapshot(
        CONCLUSION, SERIES, PROJECT, SURVEY, (uuid.uuid4(),), (), 1,
        state, b"f" * 32, 1, 0, 1, 0, None, (), (), (), (), (), (),
        True, True, 0,
    )


class ConclusionReviewSubjectTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = validation_snapshot()
        self.lock = SurveyConclusionReviewLock(
            self.snapshot, "ACTIVE", CONCLUSION, None, None, None,
        )
        self.identity = ReviewIdentitySnapshot(
            REVIEW, "PROJECT", PROJECT, "SRV-05", SERIES,
            "SURVEY_CONCLUSION_ALL_V1", "DRAFT", None, 0,
        )
        self.context = ReviewSubjectProofContext(TOKEN, uuid.uuid4())
        self.request = ReviewSubjectStartRequest(
            ACTOR, self.identity, ROUND, CONCLUSION, (REVIEWER,), self.context,
        )
        self.repository, self.reviewers, self.current, self.audit = (
            Mock() for _ in range(4))
        self.repository.lock_subject.return_value = self.lock
        self.repository.active_series_exists.return_value = True
        self.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(REVIEWER, PROJECT, "CUSTOMER_MANAGER"),
        )
        self.current.current_facts.return_value = SimpleNamespace(issues=())
        self.owner = SurveyConclusionReviewSubjectOwner(
            repository=self.repository, reviewers=self.reviewers,
            current=self.current, audit=self.audit, clock=lambda: NOW,
        )
        self.tx = object()

    def test_latest_draft_authorization_and_transient_context(self):
        proof = self.owner.authorize_create(
            self.tx, user_id=ACTOR, project_id=PROJECT,
            subject_type="SRV-05", subject_id=SERIES,
            subject_version_id=CONCLUSION,
        )
        self.assertEqual("SURVEY_CONCLUSION_ALL_V1", proof.policy_code)
        created = CreatedReviewRef(
            REVIEW, PROJECT, "SRV-05", SERIES,
            "SURVEY_CONCLUSION_ALL_V1", ACTOR, NOW,
        )
        self.assertTrue(self.owner.authorize_replay(
            self.tx, user_id=ACTOR, review=created,
        ))
        self.assertNotIn("s" * 32, repr(self.request))
        self.repository.lock_subject.return_value = replace(
            self.lock, latest_version_id=uuid.uuid4(),
        )
        self.assertIsNone(self.owner.authorize_create(
            self.tx, user_id=ACTOR, project_id=PROJECT,
            subject_type="SRV-05", subject_id=SERIES,
            subject_version_id=CONCLUSION,
        ))

    def test_prepare_revalidates_and_binds_exact_version(self):
        prepared = self.owner.prepare_start_in_transaction(
            self.tx, self.request,
        )
        self.assertEqual(b"f" * 32, prepared.content_fingerprint)
        current_command = self.current.current_facts.call_args.args[1]
        self.assertEqual(TOKEN, current_command.session_token)
        self.assertEqual(self.context.trace_id, current_command.trace_id)
        self.owner.finalize_start_in_transaction(self.tx, self.request)
        self.repository.bind_start.assert_called_once_with(
            self.tx, before=self.lock, review_id=REVIEW, round_id=ROUND,
        )

    def test_missing_context_or_current_issue_fails_closed(self):
        missing = replace(self.request, proof_context=None)
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, missing)
        self.current.current_facts.return_value = SimpleNamespace(
            issues=("EVIDENCE_UNAVAILABLE",),
        )
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)

    def test_approval_revalidates_and_terminally_consumes(self):
        active = replace(
            self.lock, snapshot=validation_snapshot("IN_REVIEW"),
            review_ref=REVIEW, review_round_ref=ROUND,
        )
        self.repository.lock_subject.return_value = active
        progress = ReviewRoundProgress(ROUND, NOW, (REVIEWER,))
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=ROUND,
            lock_version=1,
        )
        fixed = FixedReviewRoundSnapshot(
            review, 1, CONCLUSION, ACTOR, progress, (uuid.uuid4(),), 0,
            uuid.uuid4(), b"f" * 32, 1, NOW, (), uuid.uuid4(), NOW, None,
        )
        decision = ReviewDecisionSnapshot(
            uuid.uuid4(), ROUND, REVIEWER,
            ReviewDecisionKind.APPROVE, NOW,
        )
        transition_trace = uuid.uuid4()
        transition = ReviewSubjectTransition(
            REVIEWER, transition_trace, fixed,
            progress.record_decision(decision), NOW,
            ReviewSubjectProofContext(TOKEN, transition_trace),
        )
        self.owner.require_transition_access_in_transaction(self.tx, transition)
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="APPROVED",
        )
        event = self.audit.append.call_args.args[1]
        self.assertEqual("SURVEY_CONCLUSION_APPROVED", event.action)
        self.assertEqual(SERIES, event.target_object_id)
        self.assertEqual(CONCLUSION, event.target_version_id)

    def test_withdrawal_returns_without_source_revalidation(self):
        active = replace(
            self.lock, snapshot=validation_snapshot("IN_REVIEW"),
            review_ref=REVIEW, review_round_ref=ROUND,
        )
        self.repository.lock_subject.return_value = active
        progress = ReviewRoundProgress(ROUND, NOW, (REVIEWER,))
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=ROUND,
            lock_version=1,
        )
        fixed = FixedReviewRoundSnapshot(
            review, 1, CONCLUSION, ACTOR, progress, (uuid.uuid4(),), 0,
            uuid.uuid4(), b"f" * 32, 1, NOW, (), uuid.uuid4(), NOW, None,
        )
        transition = ReviewSubjectTransition(
            ACTOR, uuid.uuid4(), fixed,
            progress.withdraw(ReviewWithdrawalSnapshot(
                ACTOR, NOW, "Source changed",
            )), NOW,
        )
        self.current.reset_mock()
        self.owner.require_transition_access_in_transaction(self.tx, transition)
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.current.current_facts.assert_not_called()
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="RETURNED",
        )


class Tx(AbstractContextManager):
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def commit(self):
        type(self).commits += 1


class Access:
    def authenticated_user(self, transaction, **kwargs):
        return ACTOR


class Guard:
    def require_valid(self, **kwargs):
        return object()


class Authorization:
    def require_in_transaction(self, transaction, **kwargs):
        return AuthorizedProjectAction(
            ACTOR, PROJECT, "SURVEY_CONCLUSION_SUBMIT_REVIEW",
            "PROJECT_MANAGER",
        )


class Reviewers:
    def lock_users_in_transaction(self, transaction, *, reviewer_ids):
        return object()


class Receipts:
    replay = None
    completed = []

    def reserve(self, transaction, **kwargs):
        self.scope = kwargs["scope"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.completed.append(kwargs["result"])


def submission():
    return SubmittedProjectReviewRef(
        REVIEW, ROUND, PROJECT, "SRV-05", SERIES, CONCLUSION,
        "SURVEY_CONCLUSION_ALL_V1", (REVIEWER,), ACTOR, NOW,
    )


class Reviews:
    def submit_in_transaction(self, transaction, **kwargs):
        self.kwargs = kwargs
        return submission()

    @staticmethod
    def is_retryable_deadlock(error):
        return False


class Replays:
    value = None

    def get_project_submission(self, transaction, **kwargs):
        return self.value

    @staticmethod
    def is_retryable_deadlock(error):
        return False


class Subjects:
    def require_start_replay_access_in_transaction(self, transaction, **kwargs):
        return None


class ConclusionReviewSubmissionTests(unittest.TestCase):
    def setUp(self):
        Tx.commits, Receipts.replay, Receipts.completed = 0, None, []
        self.replays, self.reviews, self.receipts = Replays(), Reviews(), Receipts()
        self.service = SurveyConclusionReviewSubmissionService(
            unit_of_work=Tx, access=Access(), license_guard=Guard(),
            authorization=Authorization(), reviewers=Reviewers(),
            receipts=self.receipts, replay_repository=self.replays,
            reviews=self.reviews, subjects=Subjects(), clock=lambda: NOW,
        )
        self.command = SubmitSurveyConclusionReview(
            TOKEN, b"c" * 32, uuid.uuid4(), PROJECT, SERIES, CONCLUSION,
            (REVIEWER,), "SURVEY_CONCLUSION_ALL_V1", str(uuid.uuid4()),
        )

    def test_submit_passes_transient_proof_context_and_receipts(self):
        result = self.service.submit(self.command)
        context = self.reviews.kwargs["proof_context"]
        self.assertEqual(TOKEN, context.session_token)
        self.assertEqual(self.command.trace_id, context.trace_id)
        self.assertEqual("SRV-05", self.reviews.kwargs["subject_type"])
        self.assertEqual("V1_SURVEY_CONCLUSION_SUBMIT_REVIEW",
                         self.receipts.scope.operation)
        self.assertEqual(IdempotencyResult(
            "V1_SURVEY_CONCLUSION_REVIEW_SUBMISSION", ROUND, 201,
        ), Receipts.completed[0])
        self.assertEqual(ROUND, result.round_id)
        self.assertEqual(1, Tx.commits)

    def test_replay_and_invalid_input(self):
        Receipts.replay = IdempotencyResult(
            "V1_SURVEY_CONCLUSION_REVIEW_SUBMISSION", ROUND, 201,
        )
        identity = ReviewIdentitySnapshot(
            REVIEW, "PROJECT", PROJECT, "SRV-05", SERIES,
            "SURVEY_CONCLUSION_ALL_V1", "IN_REVIEW", ROUND, 1,
        )
        self.replays.value = PersistedProjectReviewSubmission(
            identity, submission(),
        )
        self.assertEqual(ROUND, self.service.submit(self.command).round_id)
        self.assertEqual(0, Tx.commits)
        with self.assertRaises(
                SurveyConclusionReviewSubmissionError) as raised:
            self.service.submit(replace(self.command, policy_ref="OTHER"))
        self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn(self.command.idempotency_key, repr(self.command))


if __name__ == "__main__":
    unittest.main()
