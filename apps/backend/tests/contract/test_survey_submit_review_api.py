from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.review.application.project_persistence import (
    SubmittedProjectReviewRef,
)
from plm_assistant.modules.survey.api.submit_review import (
    create_survey_review_submission_router,
)
from plm_assistant.modules.survey.application.submit_review import (
    SurveyReviewSubmissionError,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT, SURVEY, VERSION = (uuid.uuid4() for _ in range(3))
REVIEW, ROUND, ACTOR, REVIEWER = (uuid.uuid4() for _ in range(4))


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Submissions:
    fail = None
    last = None

    def submit(self, command):
        self.last = command
        if self.fail:
            raise SurveyReviewSubmissionError(self.fail)
        return SubmittedProjectReviewRef(
            REVIEW, ROUND, PROJECT, "SRV-02", SURVEY, VERSION,
            "SURVEY_ALL_V1", (REVIEWER,), ACTOR, NOW,
        )


class SurveySubmitReviewApiTests(unittest.TestCase):
    def setUp(self):
        self.submissions = Submissions()
        self.submissions.fail = None
        router = create_survey_review_submission_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            submissions=self.submissions,
        )
        self.client = TestClient(create_app(
            survey_review_submission_router=router,
        ), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (
            f"/api/v1/projects/{PROJECT}/surveys/{SURVEY}/versions/"
            f"{VERSION}:submit-review"
        )
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
        }
        self.body = {
            "reviewer_ids": [str(REVIEWER)],
            "policy_ref": "SURVEY_ALL_V1",
            "due_at": None, "submission_note": None,
        }

    def test_default_closed_and_created_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.path).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(201, response.status_code)
        self.assertEqual('"v1"', response.headers["etag"])
        self.assertEqual(str(REVIEW), response.json()["data"]["review_id"])
        self.assertEqual(str(ROUND), response.json()["data"]["review_round_id"])
        self.assertEqual(str(SURVEY), response.json()["data"]["survey_id"])
        self.assertEqual("IN_REVIEW", response.json()["data"]["state"])
        self.assertEqual((REVIEWER,), self.submissions.last.reviewer_ids)

    def test_strict_contract_and_security(self):
        bad = {**self.headers, "origin": "https://evil.test"}
        self.assertEqual(403, self.client.post(
            self.path, headers=bad, json=self.body,
        ).status_code)
        for body, status in (
            ({**self.body, "extra": True}, 400),
            ({**self.body, "due_at": "2026-10-07T00:00:00Z"}, 422),
            ({**self.body, "submission_note": "not persisted"}, 422),
            ({**self.body, "policy_ref": "OTHER"}, 422),
            ({**self.body, "reviewer_ids": [str(REVIEWER).upper()]}, 422),
        ):
            with self.subTest(body=body):
                self.assertEqual(status, self.client.post(
                    self.path, headers=self.headers, json=body,
                ).status_code)
        self.assertEqual(400, self.client.post(
            self.path + "?bad=1", headers=self.headers, json=self.body,
        ).status_code)

    def test_safe_error_mapping(self):
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("BUSINESS_REVIEW_NOT_ELIGIBLE", 422),
            ("REVIEW_REVIEWER_INELIGIBLE", 422),
            ("REVIEW_SUBJECT_LOCKED", 409),
            ("CONFLICT_IDEMPOTENCY", 409),
            ("PROJECT_ARCHIVED", 409),
            ("SYSTEM_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.submissions.fail = code
                response = self.client.post(
                    self.path, headers=self.headers, json=self.body,
                )
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
