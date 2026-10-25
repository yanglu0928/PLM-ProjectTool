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
from plm_assistant.modules.review.application.persist_round import (
    StartedReviewRoundRef,
)
from plm_assistant.modules.review.application.persist_transition import (
    AppliedReviewTransitionRef,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT, SURVEY, VERSION, REVIEW, ROUND, ACTOR, DECISION, EVENT = (
    uuid.uuid4() for _ in range(8)
)


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Creates:
    def __init__(self) -> None:
        self.fail = None
        self.last = None

    def create_idempotent(self, command, *, idempotency_key):
        self.last = command, idempotency_key
        if self.fail:
            raise ReviewCreateError(self.fail)
        return CreatedReviewRef(
            REVIEW, PROJECT, "SRV-02", SURVEY, "SURVEY_ALL_V1", ACTOR, NOW,
        )


class Starts:
    def __init__(self) -> None:
        self.last = None

    def start_idempotent(self, command, *, idempotency_key):
        self.last = command, idempotency_key
        return StartedReviewRoundRef(
            ROUND, REVIEW, PROJECT, 1, VERSION, ACTOR, NOW,
        )


class Transitions:
    def __init__(self) -> None:
        self.last = None

    def decide_idempotent(self, command, *, idempotency_key):
        self.last = "DECIDE", command, idempotency_key
        return AppliedReviewTransitionRef(
            PROJECT, REVIEW, ROUND, VERSION, ACTOR, NOW, "DECIDE",
            ReviewRoundState.APPROVED, 2, 1, DECISION, EVENT,
        )

    def withdraw_idempotent(self, command, *, idempotency_key):
        self.last = "WITHDRAW", command, idempotency_key
        return AppliedReviewTransitionRef(
            PROJECT, REVIEW, ROUND, VERSION, ACTOR, NOW, "WITHDRAW",
            ReviewRoundState.WITHDRAWN, 2, 1, None, EVENT,
        )


class SurveyReviewCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.creates, self.starts = Creates(), Starts()
        self.transitions = Transitions()
        router = create_review_command_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates, starts=self.starts,
            transitions=self.transitions,
        )
        self.client = TestClient(
            create_app(review_command_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "s" * 16,
        }
        self.root = f"/api/v1/projects/{PROJECT}/reviews"
        self.rounds = f"{self.root}/{REVIEW}/rounds"

    def test_default_closed_and_srv02_create_projection(self):
        body = {"subject_ref": {
            "resource_type": "SRV-02", "resource_id": str(SURVEY),
            "version_id": str(VERSION),
        }}
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.root, json=body).status_code)
        response = self.client.post(self.root, headers=self.headers, json=body)
        self.assertEqual(201, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual({
            "resource_type": "SRV-02", "resource_id": str(SURVEY),
            "version_id": str(VERSION),
        }, response.json()["data"]["subject_ref"])
        self.assertEqual("SURVEY_ALL_V1", response.json()["data"]["policy_code"])
        command, key = self.creates.last
        self.assertEqual((PROJECT, SURVEY, VERSION, "SRV-02"), (
            command.project_id, command.subject_id,
            command.subject_version_id, command.subject_type,
        ))
        self.assertEqual("s" * 16, key)

    def test_survey_policy_start_and_terminal_projection(self):
        body = {
            "subject_version_ref": str(VERSION),
            "reviewer_user_ids": [str(ACTOR)],
            "policy_code": "SURVEY_ALL_V1",
        }
        self.assertEqual(428, self.client.post(
            self.rounds, headers=self.headers, json=body,
        ).status_code)
        started = self.client.post(
            self.rounds, headers={**self.headers, "if-match": '"v0"'},
            json=body,
        )
        self.assertEqual(201, started.status_code)
        self.assertEqual("SURVEY_ALL_V1", started.json()["data"]["policy_code"])
        self.assertEqual(str(VERSION), started.json()["data"]["subject_version_ref"])
        command, _ = self.starts.last
        self.assertEqual(0, command.expected_version)

        approved = self.client.post(
            f"{self.rounds}/{ROUND}:decide", headers=self.headers,
            json={"decision": "APPROVE", "comment": None},
        )
        self.assertEqual(200, approved.status_code)
        self.assertEqual("APPROVED", approved.json()["data"]["state"])
        self.assertEqual(str(VERSION), approved.json()["data"]["subject_version_ref"])

    def test_strict_body_origin_and_frozen_error_projection(self):
        body = {"subject_ref": {
            "resource_type": "SRV-02", "resource_id": str(SURVEY),
            "version_id": str(VERSION),
        }}
        self.assertEqual(403, self.client.post(
            self.root,
            headers={**self.headers, "origin": "https://untrusted.example"},
            json=body,
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root, headers=self.headers,
            json={**body, "owner_module": "survey"},
        ).status_code)
        self.creates.fail = "REVIEW_SUBJECT_LOCKED"
        response = self.client.post(self.root, headers=self.headers, json=body)
        self.assertEqual(409, response.status_code)
        self.assertEqual("REVIEW_SUBJECT_LOCKED", response.json()["error"]["code"])
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
