from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission, SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot
from plm_assistant.modules.review.application.subject_start import ReviewSubjectAccessDenied
from plm_assistant.modules.survey.application.submit_review import (
    SubmitSurveyVersionReview, SurveyReviewSubmissionError,
    SurveyReviewSubmissionService,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
ACTOR, PROJECT, SURVEY, VERSION = (uuid.uuid4() for _ in range(4))
REVIEW, ROUND, REVIEWER_A, REVIEWER_B = (uuid.uuid4() for _ in range(4))


class Tx(AbstractContextManager):
    commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def commit(self):
        type(self).commits += 1


class Access:
    actor = ACTOR

    def authenticated_user(self, transaction, **kwargs):
        return self.actor


class Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Authorization:
    def require_in_transaction(self, tx, **kwargs):
        self.tx, self.kwargs = tx, kwargs
        return AuthorizedProjectAction(
            ACTOR, PROJECT, "SURVEY_VERSION_SUBMIT_REVIEW", "PROJECT_MANAGER",
        )


class Reviewers:
    def lock_users_in_transaction(self, tx, *, reviewer_ids):
        self.tx, self.reviewer_ids = tx, reviewer_ids
        return object()


class Receipts:
    replay = None
    completions = []

    def reserve(self, tx, **kwargs):
        self.tx, self.scope = tx, kwargs["scope"]
        return self.replay

    def complete(self, tx, **kwargs):
        self.complete_tx = tx
        self.completions.append(kwargs["result"])


def submission():
    return SubmittedProjectReviewRef(
        REVIEW, ROUND, PROJECT, "SRV-02", SURVEY, VERSION,
        "SURVEY_ALL_V1", tuple(sorted((REVIEWER_A, REVIEWER_B), key=str)),
        ACTOR, NOW,
    )


class Reviews:
    def submit_in_transaction(self, tx, **kwargs):
        self.tx, self.kwargs = tx, kwargs
        return submission()

    @staticmethod
    def is_retryable_deadlock(error):
        return False


class Replays:
    value = None

    def get_project_submission(self, tx, **kwargs):
        self.tx, self.kwargs = tx, kwargs
        return self.value

    @staticmethod
    def is_retryable_deadlock(error):
        return False


class Subjects:
    denied = False
    calls = 0

    def require_start_replay_access_in_transaction(self, tx, **kwargs):
        type(self).calls += 1
        if self.denied:
            raise ReviewSubjectAccessDenied()


class SurveyReviewSubmissionTests(unittest.TestCase):
    def setUp(self):
        Tx.commits, Subjects.calls = 0, 0
        self.guard, self.receipts = Guard(), Receipts()
        self.guard.denied, self.receipts.replay = False, None
        self.receipts.completions = []
        self.replays, self.reviews, self.subjects = Replays(), Reviews(), Subjects()
        self.replays.value, self.subjects.denied = None, False
        self.service = SurveyReviewSubmissionService(
            unit_of_work=Tx, access=Access(), license_guard=self.guard,
            authorization=Authorization(), reviewers=Reviewers(),
            receipts=self.receipts, replay_repository=self.replays,
            reviews=self.reviews, subjects=self.subjects, clock=lambda: NOW,
        )
        self.command = SubmitSurveyVersionReview(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, SURVEY, VERSION,
            (REVIEWER_B, REVIEWER_A), "SURVEY_ALL_V1", str(uuid.uuid4()),
        )

    def test_submit_is_atomic_canonical_and_receipted(self):
        result = self.service.submit(self.command)
        expected = tuple(sorted((REVIEWER_A, REVIEWER_B), key=str))
        self.assertEqual(expected, result.reviewer_ids)
        self.assertIs(self.reviews.tx, self.receipts.tx)
        self.assertIs(self.reviews.tx, self.receipts.complete_tx)
        self.assertEqual(
            "V1_SURVEY_VERSION_SUBMIT_REVIEW", self.receipts.scope.operation,
        )
        self.assertEqual(IdempotencyResult(
            "V1_SURVEY_VERSION_REVIEW_SUBMISSION", ROUND, 201,
        ), self.receipts.completions[0])
        self.assertEqual("SRV-02", self.reviews.kwargs["subject_type"])
        self.assertEqual(1, Tx.commits)

    def test_replay_recovers_first_round_and_rechecks_owner_access(self):
        self.receipts.replay = IdempotencyResult(
            "V1_SURVEY_VERSION_REVIEW_SUBMISSION", ROUND, 201,
        )
        identity = ReviewIdentitySnapshot(
            REVIEW, "PROJECT", PROJECT, "SRV-02", SURVEY,
            "SURVEY_ALL_V1", "IN_REVIEW", ROUND, 1,
        )
        self.replays.value = PersistedProjectReviewSubmission(identity, submission())
        result = self.service.submit(self.command)
        self.assertEqual(ROUND, result.round_id)
        self.assertEqual(1, Subjects.calls)
        self.assertEqual(0, Tx.commits)
        self.assertEqual([], self.receipts.completions)

    def test_invalid_and_license_failures_are_classified_and_redacted(self):
        for command in (
            replace(self.command, reviewer_ids=()),
            replace(self.command, reviewer_ids=(REVIEWER_A, REVIEWER_A)),
            replace(self.command, policy_ref="OTHER"),
            replace(self.command, session_token=b"short"),
        ):
            with self.subTest(command=command), self.assertRaises(
                    SurveyReviewSubmissionError) as raised:
                self.service.submit(command)
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        self.guard.denied = True
        with self.assertRaises(SurveyReviewSubmissionError) as raised:
            self.service.submit(self.command)
        self.assertEqual("LICENSE_OPERATION_DENIED", raised.exception.code)
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn(self.command.idempotency_key, repr(self.command))


if __name__ == "__main__":
    unittest.main()
