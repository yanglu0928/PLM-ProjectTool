from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.review.api.read import create_review_read_router
from plm_assistant.modules.review.application.read_service import (
    AuthorizedReviewRead, ReviewReadError,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)


NOW = datetime(2026, 10, 19, tzinfo=timezone.utc)
PROJECT, REVIEW, SUBJECT, VERSION, ROUND, STARTER, REVIEWER = (
    uuid.uuid4() for _ in range(7)
)


def _result() -> AuthorizedReviewRead:
    identity = ReviewIdentitySnapshot(
        REVIEW, "PROJECT", PROJECT, "SOL-06", SUBJECT,
        "STRUCTURED_SPEC_ALL_V1", "IN_REVIEW", ROUND, 2)
    decision = ReviewDecisionSnapshot(
        uuid.uuid4(), ROUND, REVIEWER, ReviewDecisionKind.APPROVE, NOW,
        "Checked against the agreed scope")
    progress = ReviewRoundProgress(ROUND, NOW, (REVIEWER, STARTER), (decision,))
    fixed = FixedReviewRoundSnapshot(
        identity, 1, VERSION, STARTER, progress,
        (uuid.uuid4(), uuid.uuid4()), 1, uuid.uuid4(), b"s" * 32,
        1, NOW, (), uuid.uuid4(), NOW, None)
    return AuthorizedReviewRead(identity, fixed)


class Reads:
    fail = None
    last = None

    def get(self, query):
        self.last = query
        if self.fail:
            raise ReviewReadError(self.fail)
        return _result()


class ReviewReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.reads.fail = None
        router = create_review_read_router(
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads)
        self.client = TestClient(
            create_app(review_read_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{PROJECT}/reviews/{REVIEW}"
        self.headers = {"cookie": "plm_session=" + (b"a" * 32).hex()}

    def test_default_closed_and_strict_active_round_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v2"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        data = response.json()["data"]
        self.assertEqual({
            "review_id", "project_id", "subject_ref", "policy_code",
            "state", "active_round", "etag",
        }, set(data))
        self.assertEqual({"resource_type", "resource_id"}, set(data["subject_ref"]))
        active = data["active_round"]
        self.assertEqual({
            "review_round_id", "round_no", "subject_version_ref", "state",
            "round_etag", "started_by", "started_at", "assignments",
        }, set(active))
        self.assertEqual("DECIDED", active["assignments"][0]["state"])
        self.assertEqual("PENDING", active["assignments"][1]["state"])
        self.assertEqual("APPROVE", active["assignments"][0]["decision"]["decision"])
        self.assertIsNone(active["assignments"][1]["decision"])
        self.assertTrue(self.reads.last.include_active_round)
        self.assertIsNone(self.reads.last.round_id)

    def test_read_security_query_and_canonical_identifiers(self):
        self.assertEqual(403, self.client.get(
            self.path, headers={**self.headers, "host": "evil.test"}).status_code)
        self.assertEqual(401, self.client.get(self.path).status_code)
        self.assertEqual(400, self.client.get(
            self.path + "?round=latest", headers=self.headers).status_code)
        self.assertEqual(422, self.client.get(
            self.path.replace(str(REVIEW), str(REVIEW).upper()),
            headers=self.headers).status_code)

    def test_safe_error_mapping(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 401),
            ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("VALIDATION_FAILED", 422),
            ("REVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.fail = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
