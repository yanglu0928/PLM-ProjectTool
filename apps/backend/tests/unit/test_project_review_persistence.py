from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from plm_assistant.modules.review.application.create_review import (
    AuthorizedReviewCreation, CreatedReviewRef,
)
from plm_assistant.modules.review.application.persist_round import StartedReviewRoundRef
from plm_assistant.modules.review.application.project_persistence import (
    ProjectReviewPersistenceService,
)
from plm_assistant.modules.review.application.read_snapshot import ReviewIdentitySnapshot
from plm_assistant.modules.review.application.subject_start import PreparedReviewSubject


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
ACTOR, PROJECT, SUBJECT, VERSION = (uuid.uuid4() for _ in range(4))
REVIEW, ROUND, REVIEWER = (uuid.uuid4() for _ in range(3))


class Subjects:
    def authorize_create(self, tx, **kwargs):
        return AuthorizedReviewCreation(
            kwargs["user_id"], kwargs["project_id"], kwargs["subject_type"],
            kwargs["subject_id"], kwargs["subject_version_id"],
            "HANDOVER_ALL_V1",
        )

    def prepare_start_in_transaction(self, tx, request):
        return PreparedReviewSubject(
            request, b"f" * 32, 1, NOW, request.reviewer_ids, (),
        )

    def assert_active_lock_in_transaction(self, tx, request):
        return None

    def finalize_start_in_transaction(self, tx, request):
        return None


class Creations:
    def create(self, tx, *, proof):
        self.tx, self.proof = tx, proof
        return CreatedReviewRef(
            REVIEW, PROJECT, "HND-02", SUBJECT,
            "HANDOVER_ALL_V1", ACTOR, NOW,
        )


class Rounds:
    def lock_start_context(self, tx, *, project_id, review_id):
        return ReviewIdentitySnapshot(
            REVIEW, "PROJECT", PROJECT, "HND-02", SUBJECT,
            "HANDOVER_ALL_V1", "DRAFT", None, 0,
        ), ROUND

    def insert_round(self, tx, *, prepared, trace_id, started_at):
        self.tx, self.prepared = tx, prepared
        return StartedReviewRoundRef(
            ROUND, REVIEW, PROJECT, 1, VERSION, ACTOR, NOW,
        )

    @staticmethod
    def is_retryable_deadlock(error):
        return False


class Audit:
    def __init__(self):
        self.drafts = []

    def append(self, tx, draft):
        self.drafts.append(draft)
        return uuid.uuid4()


class ProjectReviewPersistenceTests(unittest.TestCase):
    def test_create_and_start_share_caller_transaction(self):
        creations, rounds, audit, subjects = Creations(), Rounds(), Audit(), Subjects()
        service = ProjectReviewPersistenceService(
            creation_repository=creations, round_repository=rounds,
            audit=audit, subjects=subjects, clock=lambda: NOW,
        )
        tx = object()
        result = service.submit_in_transaction(
            tx, actor_id=ACTOR, project_id=PROJECT, subject_type="HND-02",
            subject_id=SUBJECT, subject_version_id=VERSION,
            reviewer_ids=(REVIEWER,), policy_code="HANDOVER_ALL_V1",
            trace_id=uuid.uuid4(),
        )
        self.assertIs(tx, creations.tx)
        self.assertIs(tx, rounds.tx)
        self.assertEqual(("REVIEW_CREATED", "REVIEW_STARTED"),
                         tuple(item.action for item in audit.drafts))
        self.assertEqual(REVIEW, result.review_id)
        self.assertEqual(ROUND, result.round_id)
        self.assertEqual((REVIEWER,), result.reviewer_ids)


if __name__ == "__main__":
    unittest.main()
