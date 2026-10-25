"""Frozen PlanVersion submit-review remains opt-in and atomic."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.plan.api.submit_plan_version_review import create_plan_version_review_submission_router
from plm_assistant.modules.plan.application.submit_plan_version_review import PlanVersionReviewSubmissionError
from plm_assistant.modules.review.application.project_persistence import SubmittedProjectReviewRef


NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)
PROJECT, PLAN, VERSION, REVIEW, ROUND, ACTOR, REVIEWER = (uuid4() for _ in range(7))
PATH = (f"/api/v1/projects/{PROJECT}/plans/{PLAN}/versions/"
        f"{VERSION}:submit-review")
HEADERS = {
    "origin": "https://plm.example.test",
    "cookie": "plm_session=" + (b"a" * 32).hex(),
    "x-csrf-token": (b"c" * 32).hex(),
    "idempotency-key": str(uuid4()),
}
BODY = {"reviewer_ids": [str(REVIEWER)], "policy_ref": "PLAN_VERSION_ALL_V1",
        "due_at": None, "submission_note": None}


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if (token != b"a" * 32 or csrf_token != b"c" * 32
                or require_csrf is not True):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Submissions:
    fail = None
    malformed = False

    def submit(self, command):
        self.last = command
        if self.fail:
            raise PlanVersionReviewSubmissionError(self.fail)
        return SubmittedProjectReviewRef(
            REVIEW, ROUND, PROJECT, "BAD" if self.malformed else "PLN-02",
            VERSION, VERSION, "PLAN_VERSION_ALL_V1", (REVIEWER,), ACTOR, NOW)


@pytest.fixture
def app():
    submissions = Submissions()
    submissions.fail = None
    submissions.malformed = False
    router = create_plan_version_review_submission_router(
        sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
        submissions=submissions)
    with TestClient(create_app(plan_version_validation_router=router),
                    base_url="https://plm.example.test") as client:
        yield client, submissions


def test_default_closed_and_fixed_201_projection(app):
    client, submissions = app
    with TestClient(create_app(), base_url="https://plm.example.test") as bare:
        assert bare.post(PATH).status_code == 404
    response = client.post(PATH, headers=HEADERS, json=BODY)
    assert response.status_code == 201
    assert response.headers["etag"] == '"v1"'
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    assert set(data) == {
        "review_id", "review_round_id", "subject_type", "project_id", "plan_id",
        "plan_version_id", "policy_ref", "reviewer_ids", "state", "round_no",
        "review_etag", "submitted_by", "submitted_at",
    }
    assert (data["plan_id"], data["plan_version_id"]) == (str(PLAN), str(VERSION))
    assert data["state"] == "IN_REVIEW"
    assert (submissions.last.plan_id, submissions.last.plan_version_id) == (PLAN, VERSION)
    assert response.json()["trace_id"] == response.headers["x-trace-id"]


def test_origin_csrf_body_path_and_output_are_strict(app):
    client, submissions = app
    assert client.post(PATH, headers={**HEADERS, "origin": "https://evil.test"},
                       json=BODY).status_code == 403
    assert client.post(PATH, headers={**HEADERS, "x-csrf-token": "bad"},
                       json=BODY).status_code in (401, 403)
    for body, status in (
            ({**BODY, "extra": True}, 400),
            ({**BODY, "due_at": "2026-10-23T00:00:00Z"}, 422),
            ({**BODY, "submission_note": "not persisted"}, 422),
            ({**BODY, "policy_ref": "OTHER"}, 422),
            ({**BODY, "reviewer_ids": [str(REVIEWER).upper()]}, 422)):
        assert client.post(PATH, headers=HEADERS, json=body).status_code == status
    assert client.post(PATH + "?bad=1", headers=HEADERS, json=BODY).status_code == 400
    submissions.malformed = True
    assert client.post(PATH, headers=HEADERS, json=BODY).status_code == 503


@pytest.mark.parametrize("code,status", [
    ("AUTH_ACCESS_DENIED", 404), ("LICENSE_OPERATION_DENIED", 403),
    ("BUSINESS_REVIEW_NOT_ELIGIBLE", 422), ("REVIEW_REVIEWER_INELIGIBLE", 422),
    ("REVIEW_SUBJECT_LOCKED", 409), ("CONFLICT_IDEMPOTENCY", 409),
    ("CONFLICT_VERSION", 409), ("PROJECT_ARCHIVED", 409),
    ("SYSTEM_UNAVAILABLE", 503),
])
def test_error_mapping_does_not_leak_traceback(app, code, status):
    client, submissions = app
    submissions.fail = code
    response = client.post(PATH, headers=HEADERS, json=BODY)
    assert response.status_code == status
    assert response.headers["cache-control"] == "no-store"
    assert "Traceback" not in response.text
