from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.review.api.commands import create_review_command_router
from plm_assistant.modules.review.application.create_review import (
    CreatedReviewRef, ReviewCreateError,
)
from plm_assistant.modules.review.application.persist_round import StartedReviewRoundRef
from plm_assistant.modules.review.application.persist_transition import (
    AppliedReviewTransitionRef,
)
from plm_assistant.modules.review.application.start_round import ReviewStartError
from plm_assistant.modules.review.application.transition_command import (
    ReviewTransitionCommandError,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState


NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
PROJECT, SUBJECT, VERSION, REVIEW, ROUND, ACTOR, DECISION, EVENT = (
    uuid.uuid4() for _ in range(8)
)


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Creates:
    fail = None
    last = None

    def create_idempotent(self, command, *, idempotency_key):
        self.last = (command, idempotency_key)
        if self.fail:
            raise ReviewCreateError(self.fail)
        return CreatedReviewRef(
            REVIEW, PROJECT, "HND-02", SUBJECT, "HANDOVER_ALL_V1", ACTOR, NOW,
        )


class Starts:
    fail = None
    last = None

    def start_idempotent(self, command, *, idempotency_key):
        self.last = (command, idempotency_key)
        if self.fail:
            raise ReviewStartError(self.fail)
        return StartedReviewRoundRef(ROUND, REVIEW, PROJECT, 1, VERSION, ACTOR, NOW)


class Transitions:
    fail = None
    last = None

    def decide_idempotent(self, command, *, idempotency_key):
        self.last = ("DECIDE", command, idempotency_key)
        if self.fail:
            raise ReviewTransitionCommandError(self.fail)
        return AppliedReviewTransitionRef(
            PROJECT, REVIEW, ROUND, VERSION, ACTOR, NOW, "DECIDE",
            ReviewRoundState.APPROVED, 2, 1, DECISION, EVENT,
        )

    def withdraw_idempotent(self, command, *, idempotency_key):
        self.last = ("WITHDRAW", command, idempotency_key)
        if self.fail:
            raise ReviewTransitionCommandError(self.fail)
        return AppliedReviewTransitionRef(
            PROJECT, REVIEW, ROUND, VERSION, ACTOR, NOW, "WITHDRAW",
            ReviewRoundState.WITHDRAWN, 2, 1, None, EVENT,
        )


class ReviewCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.creates, self.starts, self.transitions = Creates(), Starts(), Transitions()
        self.creates.fail = self.starts.fail = self.transitions.fail = None
        router = create_review_command_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates, starts=self.starts, transitions=self.transitions,
        )
        self.client = TestClient(
            create_app(review_command_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "r" * 16,
        }
        self.root = f"/api/v1/projects/{PROJECT}/reviews"
        self.rounds = f"{self.root}/{REVIEW}/rounds"

    def test_default_closed_and_create_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.root).status_code)
        body = {"subject_ref": {
            "resource_type": "HND-02", "resource_id": str(SUBJECT),
            "version_id": str(VERSION),
        }}
        response = self.client.post(self.root, headers=self.headers, json=body)
        self.assertEqual(201, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual(f"{self.root}/{REVIEW}", response.headers["location"])
        self.assertEqual("DRAFT", response.json()["data"]["state"])
        self.assertEqual(str(VERSION), response.json()["data"]["subject_ref"]["version_id"])
        command, key = self.creates.last
        self.assertEqual((PROJECT, SUBJECT, VERSION), (
            command.project_id, command.subject_id, command.subject_version_id,
        ))
        self.assertEqual("r" * 16, key)

    def test_start_projection_and_strong_precondition(self):
        body = {
            "subject_version_ref": str(VERSION),
            "reviewer_user_ids": [str(ACTOR)],
            "policy_code": "HANDOVER_ALL_V1",
        }
        self.assertEqual(428, self.client.post(
            self.rounds, headers=self.headers, json=body,
        ).status_code)
        response = self.client.post(
            self.rounds, headers={**self.headers, "if-match": '"v0"'}, json=body,
        )
        self.assertEqual(201, response.status_code)
        self.assertEqual('"v1"', response.headers["etag"])
        self.assertEqual("IN_REVIEW", response.json()["data"]["state"])
        command, _ = self.starts.last
        self.assertEqual(0, command.expected_version)
        self.assertEqual((ACTOR,), command.reviewer_ids)

    def test_decide_and_withdraw_projections(self):
        decide = self.client.post(
            f"{self.rounds}/{ROUND}:decide", headers=self.headers,
            json={"decision": "APPROVE", "comment": None},
        )
        self.assertEqual(200, decide.status_code)
        self.assertEqual("APPROVED", decide.json()["data"]["state"])
        self.assertEqual("DECIDED", decide.json()["data"]["assignment_state"])
        self.assertEqual('"v2"', decide.headers["etag"])

        withdraw = self.client.post(
            f"{self.rounds}/{ROUND}:withdraw",
            headers={**self.headers, "if-match": '"v1"'},
            json={"reason": "withdraw current round"},
        )
        self.assertEqual(200, withdraw.status_code)
        self.assertEqual("WITHDRAWN", withdraw.json()["data"]["state"])
        self.assertTrue(withdraw.json()["data"]["withdrawn"])
        self.assertEqual(1, self.transitions.last[1].expected_version)

    def test_strict_body_security_and_no_unfrozen_if_match_on_decide(self):
        create_body = {"subject_ref": {
            "resource_type": "HND-02", "resource_id": str(SUBJECT),
            "version_id": str(VERSION),
        }}
        self.assertEqual(403, self.client.post(
            self.root, headers={**self.headers, "origin": "https://evil.test"},
            json=create_body,
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root, headers=self.headers,
            json={**create_body, "owner_module": "handover"},
        ).status_code)
        self.assertEqual(422, self.client.post(
            self.root, headers=self.headers,
            json={"subject_ref": {**create_body["subject_ref"],
                                  "resource_id": str(SUBJECT).upper()}},
        ).status_code)
        self.assertEqual(200, self.client.post(
            f"{self.rounds}/{ROUND}:decide", headers=self.headers,
            json={"decision": "APPROVE", "comment": None},
        ).status_code)
        self.assertEqual(422, self.client.post(
            f"{self.rounds}/{ROUND}:decide", headers=self.headers,
            json={"decision": "RETURN", "comment": None},
        ).status_code)

    def test_safe_frozen_error_mapping(self):
        body = {
            "subject_version_ref": str(VERSION),
            "reviewer_user_ids": [str(ACTOR)],
            "policy_code": "HANDOVER_ALL_V1",
        }
        for code, status in (
            ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("REVIEW_SUBJECT_LOCKED", 409),
            ("REVIEW_REVIEWER_INELIGIBLE", 422),
            ("CONFLICT_IDEMPOTENCY", 409),
            ("REVIEW_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.starts.fail = code
                response = self.client.post(
                    self.rounds, headers={**self.headers, "if-match": '"v0"'},
                    json=body,
                )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
