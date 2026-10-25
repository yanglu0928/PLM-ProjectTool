"""Additive GLOBAL CAP-01 Review GET/DECIDE never opens by default."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.review.api.global_capability import (
    create_global_capability_review_router,
)
from plm_assistant.modules.review.application.global_capability_decide import (
    GlobalCapabilityReviewDecisionError,
)
from plm_assistant.modules.review.application.global_capability_read import (
    AuthorizedGlobalCapabilityReview, GlobalCapabilityReviewReadError,
)
from plm_assistant.modules.review.application.global_persistence import (
    AppliedGlobalReviewTransitionRef,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewRoundProgress, ReviewRoundState,
)


NOW = datetime(2026, 10, 24, tzinfo=timezone.utc)
REVIEW, ROUND, BASELINE, VERSION, ACTOR = (uuid.uuid4() for _ in range(5))


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


def detail() -> AuthorizedGlobalCapabilityReview:
    identity = ReviewIdentitySnapshot(
        REVIEW, "GLOBAL", None, "CAP-01", BASELINE,
        "DEPLOYMENT_ALL_V1", "IN_REVIEW", ROUND, 1,
    )
    fixed = FixedReviewRoundSnapshot(
        identity, 1, VERSION, ACTOR,
        ReviewRoundProgress(ROUND, NOW, (ACTOR,)),
        (uuid.uuid4(),), 0, uuid.uuid4(), b"x" * 32, 1,
        NOW, (), uuid.uuid4(), NOW, None,
    )
    return AuthorizedGlobalCapabilityReview(identity, fixed)


class Reads:
    fail = None
    last = None
    def get(self, query):
        self.last = query
        if self.fail:
            raise GlobalCapabilityReviewReadError(self.fail)
        return detail()


class Decisions:
    fail = None
    last = None
    def decide(self, command):
        self.last = command
        if self.fail:
            raise GlobalCapabilityReviewDecisionError(self.fail)
        return AppliedGlobalReviewTransitionRef(
            REVIEW, ROUND, VERSION, ACTOR, NOW, "DECIDE",
            ReviewRoundState.APPROVED, 2, 1, uuid.uuid4(), uuid.uuid4(),
        )


class GlobalCapabilityReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.decisions = Reads(), Decisions()
        self.reads.fail = self.decisions.fail = None
        router = create_global_capability_review_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, decisions=self.decisions,
        )
        self.client = TestClient(
            create_app(global_capability_review_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.get_path = f"/api/v1/global/reviews/{REVIEW}"
        self.decide_path = f"{self.get_path}/rounds/{ROUND}:decide"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
        }

    def test_default_closed_and_exact_global_metadata_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.get_path, headers=self.headers).status_code)
            self.assertEqual(404, bare.post(self.decide_path, headers=self.headers,
                json={"decision": "APPROVE", "comment": None}).status_code)
        response = self.client.get(self.get_path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v1"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.json()["trace_id"], response.headers["x-trace-id"])
        data = response.json()["data"]
        self.assertEqual({
            "review_id", "subject_type", "baseline_id", "baseline_version_id",
            "policy_ref", "review_round_id", "round_no", "reviewer_ids",
            "decisions", "state", "review_etag", "round_etag",
            "submitted_by", "submitted_at",
        }, set(data))
        self.assertEqual("CAP-01", data["subject_type"])
        self.assertEqual("IN_REVIEW", data["state"])
        self.assertEqual([str(ACTOR)], data["reviewer_ids"])

    def test_decide_uses_private_session_csrf_key_and_exact_result(self):
        response = self.client.post(self.decide_path, headers=self.headers,
            json={"decision": "APPROVE", "comment": None})
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v2"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        data = response.json()["data"]
        self.assertEqual({
            "review_id", "review_round_id", "baseline_version_id", "actor_id",
            "decision", "decision_id", "state", "review_etag", "round_etag",
            "occurred_at", "event_id",
        }, set(data))
        self.assertEqual("APPROVED", data["state"])
        self.assertEqual(ReviewDecisionKind.APPROVE, self.decisions.last.decision)
        self.assertEqual(self.headers["idempotency-key"],
                         self.decisions.last.idempotency_key)

    def test_get_and_decide_reject_query_origin_body_and_comment_errors(self):
        self.assertEqual(400, self.client.get(
            self.get_path + "?extra=1", headers=self.headers).status_code)
        self.assertEqual(403, self.client.post(self.decide_path,
            headers={**self.headers, "origin": "https://evil.test"},
            json={"decision": "APPROVE", "comment": None}).status_code)
        for body, status in (
            ({"decision": "APPROVE"}, 400),
            ({"decision": "APPROVE", "comment": None, "extra": True}, 400),
            ({"decision": "WRONG", "comment": None}, 422),
            ({"decision": "RETURN", "comment": " "}, 422),
            ({"decision": "APPROVE", "comment": 7}, 422),
        ):
            with self.subTest(body=body):
                self.assertEqual(status, self.client.post(
                    self.decide_path, headers=self.headers, json=body,
                ).status_code)
        self.assertEqual(400, self.client.post(
            self.decide_path + "?x=1", headers=self.headers,
            json={"decision": "APPROVE", "comment": None},
        ).status_code)

    def test_public_error_mapping_is_safe(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("GLOBAL_REVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.reads.fail = code
                result = self.client.get(self.get_path, headers=self.headers)
                self.assertEqual(status, result.status_code)
                self.assertNotIn("Traceback", result.text)
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404), ("LICENSE_OPERATION_DENIED", 403),
            ("REVIEW_COMMENT_REQUIRED", 422), ("REVIEW_DECISION_EXISTS", 409),
            ("CONFLICT_IDEMPOTENCY", 409), ("GLOBAL_REVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.decisions.fail = code
                result = self.client.post(self.decide_path, headers=self.headers,
                    json={"decision": "APPROVE", "comment": None})
                self.assertEqual(status, result.status_code)
                self.assertNotIn("Traceback", result.text)


if __name__ == "__main__":
    unittest.main()
