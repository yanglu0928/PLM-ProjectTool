from __future__ import annotations

import unittest
import uuid
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.capability.application.submit_review import (
    CapabilityReviewSubmissionError, CapabilityReviewSubmissionService,
    SubmitCapabilityVersionReview,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyResult
from plm_assistant.modules.review.application.global_persistence import (
    PersistedGlobalReviewSubmission, SubmittedGlobalReviewRef,
)
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot
from plm_assistant.modules.review.application.subject_start import ReviewSubjectAccessDenied


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
ACTOR, BASELINE, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
REVIEW, ROUND = uuid.uuid4(), uuid.uuid4()
REVIEWER_A, REVIEWER_B = uuid.uuid4(), uuid.uuid4()


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

    def authorized_admin(self, transaction, **kwargs):
        return self.actor


class Guard:
    denied = False

    def require_valid(self, **kwargs):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class Receipts:
    replay = None
    completions = []

    def reserve(self, transaction, **kwargs):
        self.reserve_tx = transaction
        self.scope = kwargs["scope"]
        self.fingerprint = kwargs["request_fingerprint"]
        return self.replay

    def complete(self, transaction, **kwargs):
        self.complete_tx = transaction
        self.completions.append(kwargs["result"])


class Reviews:
    def submit_in_transaction(self, tx, **kwargs):
        self.tx, self.kwargs = tx, kwargs
        return SubmittedGlobalReviewRef(
            REVIEW, ROUND, "CAP-01", BASELINE, VERSION,
            "DEPLOYMENT_ALL_V1", kwargs["reviewer_ids"], ACTOR, NOW,
        )


def persisted():
    result = SubmittedGlobalReviewRef(
        REVIEW, ROUND, "CAP-01", BASELINE, VERSION,
        "DEPLOYMENT_ALL_V1",
        tuple(sorted((REVIEWER_A, REVIEWER_B), key=str)), ACTOR, NOW,
    )
    identity = ReviewIdentitySnapshot(
        REVIEW, "GLOBAL", None, "CAP-01", BASELINE,
        "DEPLOYMENT_ALL_V1", "IN_REVIEW", ROUND, 1,
    )
    return PersistedGlobalReviewSubmission(identity, result)


class Replays:
    value = persisted()

    def get_global_submission(self, transaction, **kwargs):
        self.round_id = kwargs["round_id"]
        return self.value


class Subjects:
    denied = False
    calls = 0

    def require_start_replay_access_in_transaction(self, transaction, **kwargs):
        type(self).calls += 1
        if self.denied:
            raise ReviewSubjectAccessDenied()


class CapabilityReviewSubmissionTests(unittest.TestCase):
    def setUp(self):
        Tx.commits = 0
        Subjects.calls = 0
        self.access, self.guard = Access(), Guard()
        self.access.actor, self.guard.denied = ACTOR, False
        self.receipts, self.replays = Receipts(), Replays()
        self.receipts.replay, self.receipts.completions = None, []
        self.replays.value = persisted()
        self.subjects, self.reviews = Subjects(), Reviews()
        self.subjects.denied = False
        self.service = CapabilityReviewSubmissionService(
            unit_of_work=Tx, access=self.access, license_guard=self.guard,
            receipts=self.receipts, replay_repository=self.replays,
            reviews=self.reviews, subjects=self.subjects, clock=lambda: NOW,
        )
        self.command = SubmitCapabilityVersionReview(
            b"s" * 32, b"c" * 32, uuid.uuid4(), BASELINE, VERSION,
            (REVIEWER_B, REVIEWER_A), "DEPLOYMENT_ALL_V1", str(uuid.uuid4()),
        )

    def test_submit_is_atomic_canonical_and_receipted(self):
        result = self.service.submit(self.command)
        expected = tuple(sorted((REVIEWER_A, REVIEWER_B), key=str))
        self.assertEqual(expected, result.reviewer_ids)
        self.assertIs(self.reviews.tx, self.receipts.reserve_tx)
        self.assertIs(self.reviews.tx, self.receipts.complete_tx)
        self.assertEqual("V1_CAP_VERSION_SUBMIT_REVIEW", self.receipts.scope.operation)
        self.assertEqual(IdempotencyResult(
            "V1_CAP_VERSION_REVIEW_SUBMISSION", ROUND, 201,
        ), self.receipts.completions[0])
        self.assertEqual(1, Tx.commits)

    def test_replay_rechecks_current_owner_access_without_second_write(self):
        self.receipts.replay = IdempotencyResult(
            "V1_CAP_VERSION_REVIEW_SUBMISSION", ROUND, 201,
        )
        result = self.service.submit(self.command)
        self.assertEqual(ROUND, result.round_id)
        self.assertEqual(1, Subjects.calls)
        self.assertEqual(0, Tx.commits)
        self.assertEqual([], self.receipts.completions)

    def test_failures_are_classified_and_tokens_redacted(self):
        invalid = (
            replace(self.command, reviewer_ids=()),
            replace(self.command, reviewer_ids=(REVIEWER_A, REVIEWER_A)),
            replace(self.command, policy_ref="OTHER"),
            replace(self.command, session_token=b"short"),
        )
        for command in invalid:
            with self.subTest(command=command), self.assertRaises(
                    CapabilityReviewSubmissionError) as raised:
                self.service.submit(command)
            self.assertEqual("VALIDATION_FAILED", raised.exception.code)
        self.guard.denied = True
        with self.assertRaises(CapabilityReviewSubmissionError) as raised:
            self.service.submit(self.command)
        self.assertEqual("LICENSE_OPERATION_DENIED", raised.exception.code)
        self.assertNotIn("s" * 32, repr(self.command))
        self.assertNotIn(self.command.idempotency_key, repr(self.command))


if __name__ == "__main__":
    unittest.main()
