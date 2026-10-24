from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.review.application.project_persistence import (
    PersistedProjectReviewSubmission,
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
    ReviewSubjectProofContext,
)
from plm_assistant.modules.solution.application.structured_spec_submit_review import (
    StructuredSpecReviewSubmissionError,
    StructuredSpecReviewSubmissionService,
    SubmitStructuredSpecReview,
)


NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
ACTOR, PROJECT, SERIES, SPEC = (uuid.uuid4() for _ in range(4))
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
    def authenticated_user(self, transaction, **kwargs):
        return ACTOR


class Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Authorization:
    denied = False

    def require_in_transaction(self, tx, **kwargs):
        self.tx, self.kwargs = tx, kwargs
        role = "IMPLEMENTATION_MEMBER" if self.denied else "PROJECT_MANAGER"
        return AuthorizedProjectAction(
            ACTOR, PROJECT, "SOL_SPEC_SUBMIT_REVIEW", role,
        )


class Reviewers:
    def lock_users_in_transaction(self, tx, *, reviewer_ids):
        self.tx, self.reviewer_ids = tx, reviewer_ids
        return object()


class Receipts:
    replay = None

    def __init__(self):
        self.completions = []

    def reserve(self, tx, **kwargs):
        self.tx, self.scope = tx, kwargs["scope"]
        return self.replay

    def complete(self, tx, **kwargs):
        self.complete_tx = tx
        self.completions.append(kwargs["result"])


class Identity:
    value = SERIES
    calls = 0

    def series_for_version(self, tx, **kwargs):
        type(self).calls += 1
        self.tx, self.kwargs = tx, kwargs
        return self.value


def submission():
    return SubmittedProjectReviewRef(
        REVIEW, ROUND, PROJECT, "SOL-06", SERIES, SPEC,
        "STRUCTURED_SPEC_ALL_V1",
        tuple(sorted((REVIEWER_A, REVIEWER_B), key=str)), ACTOR, NOW,
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
        self.tx, self.kwargs = tx, kwargs
        if self.denied:
            raise ReviewSubjectAccessDenied()


class StructuredSpecReviewSubmissionTests(unittest.TestCase):
    def setUp(self):
        Tx.commits, Subjects.calls, Identity.calls = 0, 0, 0
        self.guard, self.authorization = Guard(), Authorization()
        self.receipts, self.replays = Receipts(), Replays()
        self.identity, self.reviews, self.subjects = (
            Identity(), Reviews(), Subjects())
        self.guard.denied = self.authorization.denied = False
        self.receipts.replay, self.replays.value = None, None
        self.identity.value, self.subjects.denied = SERIES, False
        self.service = StructuredSpecReviewSubmissionService(
            unit_of_work=Tx, access=Access(), license_guard=self.guard,
            authorization=self.authorization, reviewers=Reviewers(),
            receipts=self.receipts, replay_repository=self.replays,
            identity=self.identity, reviews=self.reviews,
            subjects=self.subjects, clock=lambda: NOW,
        )
        self.command = SubmitStructuredSpecReview(
            b"s" * 32, b"c" * 32, uuid.uuid4(), PROJECT, SPEC,
            (REVIEWER_B, REVIEWER_A), "STRUCTURED_SPEC_ALL_V1",
            str(uuid.uuid4()),
        )

    def test_submit_is_atomic_canonical_receipted_and_proven(self):
        result = self.service.submit(self.command)
        expected = tuple(sorted((REVIEWER_A, REVIEWER_B), key=str))
        self.assertEqual(expected, result.reviewer_ids)
        self.assertIs(self.reviews.tx, self.receipts.tx)
        self.assertIs(self.reviews.tx, self.receipts.complete_tx)
        self.assertIs(self.reviews.tx, self.identity.tx)
        self.assertEqual(
            "V1_SOL_SPEC_SUBMIT_REVIEW", self.receipts.scope.operation,
        )
        self.assertEqual(IdempotencyResult(
            "V1_SOL_SPEC_REVIEW_SUBMISSION", ROUND, 201,
        ), self.receipts.completions[0])
        self.assertEqual("SOL-06", self.reviews.kwargs["subject_type"])
        self.assertEqual(SERIES, self.reviews.kwargs["subject_id"])
        self.assertEqual(
            "SOL_SPEC_SUBMIT_REVIEW", self.authorization.kwargs["operation"],
        )
        proof = self.reviews.kwargs["proof_context"]
        self.assertIsInstance(proof, ReviewSubjectProofContext)
        self.assertEqual(self.command.session_token, proof.session_token)
        self.assertEqual(self.command.trace_id, proof.trace_id)
        self.assertEqual(1, Identity.calls)
        self.assertEqual(1, Tx.commits)

    def test_replay_recovers_round_and_rechecks_current_owner_access(self):
        self.receipts.replay = IdempotencyResult(
            "V1_SOL_SPEC_REVIEW_SUBMISSION", ROUND, 201,
        )
        identity = ReviewIdentitySnapshot(
            REVIEW, "PROJECT", PROJECT, "SOL-06", SERIES,
            "STRUCTURED_SPEC_ALL_V1", "IN_REVIEW", ROUND, 1,
        )
        self.replays.value = PersistedProjectReviewSubmission(
            identity, submission(),
        )
        result = self.service.submit(self.command)
        self.assertEqual(ROUND, result.round_id)
        self.assertEqual(1, Subjects.calls)
        self.assertEqual(0, Identity.calls)
        self.assertEqual(0, Tx.commits)
        self.assertEqual([], self.receipts.completions)

        self.subjects.denied = True
        with self.assertRaises(StructuredSpecReviewSubmissionError) as raised:
            self.service.submit(self.command)
        self.assertEqual(
            "BUSINESS_REVIEW_NOT_ELIGIBLE", raised.exception.code,
        )

    def test_invalid_license_role_and_missing_identity_fail_safe(self):
        for command in (
            replace(self.command, reviewer_ids=()),
            replace(self.command, reviewer_ids=(REVIEWER_A, REVIEWER_A)),
            replace(self.command, policy_ref="OTHER"),
            replace(self.command, session_token=b"short"),
        ):
            with self.subTest(command=command), self.assertRaises(
                    StructuredSpecReviewSubmissionError) as raised:
                self.service.submit(command)
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        self.guard.denied = True
        with self.assertRaises(StructuredSpecReviewSubmissionError) as raised:
            self.service.submit(self.command)
        self.assertEqual("LICENSE_OPERATION_DENIED", raised.exception.code)
        self.guard.denied = False
        self.authorization.denied = True
        with self.assertRaises(StructuredSpecReviewSubmissionError) as raised:
            self.service.submit(self.command)
        self.assertEqual("RESOURCE_NOT_FOUND", raised.exception.code)
        self.authorization.denied = False
        self.identity.value = None
        with self.assertRaises(StructuredSpecReviewSubmissionError) as raised:
            self.service.submit(self.command)
        self.assertEqual("RESOURCE_NOT_FOUND", raised.exception.code)
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn(self.command.idempotency_key, repr(self.command))


if __name__ == "__main__":
    unittest.main()
