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
from plm_assistant.modules.survey.api.conclusions import (
    create_survey_conclusion_command_router,
    create_survey_conclusion_read_router,
)
from plm_assistant.modules.survey.api.read_cursor import SurveyConclusionCursorCodec
from plm_assistant.modules.survey.application.conclusion_views import (
    ConclusionEvidenceView, ConclusionOpenIssueView,
    DepartmentConclusionView, SurveyConclusionPage,
    SurveyConclusionSummaryView, SurveyConclusionView,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    SurveyConclusionCreateError,
)
from plm_assistant.modules.survey.application.read_conclusions import (
    SurveyConclusionReadError,
)
from plm_assistant.modules.survey.application.submit_conclusion_review import (
    SurveyConclusionReviewSubmissionError,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    SurveyConclusionValidationError, SurveyConclusionValidationReport,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)
PROJECT, SURVEY, CONCLUSION, SERIES, ROUND = (
    uuid.uuid4() for _ in range(5))
ACTOR, REVIEWER, DEPARTMENT, RESPONSE, EVIDENCE = (
    uuid.uuid4() for _ in range(5))
DOCUMENT, DOCUMENT_VERSION, ACTION = (uuid.uuid4() for _ in range(3))
REVIEW, REVIEW_ROUND = uuid.uuid4(), uuid.uuid4()


def conclusion_view(state="DRAFT"):
    summary = SurveyConclusionSummaryView(
        CONCLUSION, SERIES, PROJECT, SURVEY, (ROUND,), (), 1, state,
        "66" * 32, 1, 0, 1, 1, None,
        REVIEW if state == "IN_REVIEW" else None,
        REVIEW_ROUND if state == "IN_REVIEW" else None,
        ACTOR, NOW,
    )
    return SurveyConclusionView(
        summary,
        (DepartmentConclusionView(
            uuid.uuid4(), DEPARTMENT, "Scope", "Confirmed scope",
            (RESPONSE,), 0,
        ),),
        (),
        (ConclusionEvidenceView(
            uuid.uuid4(), "SUPPORT", DOCUMENT, DOCUMENT_VERSION, EVIDENCE,
            0, "65" * 32, 0,
        ),),
        (ConclusionOpenIssueView(
            uuid.uuid4(), "handover", "HND-03", ACTION, "CLOSED", 1,
            False, 0,
        ),),
    )


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def list_conclusions(self, query, *, page_size, after_created_at=None,
                         after_conclusion_id=None):
        if self.fail:
            raise SurveyConclusionReadError(self.fail)
        self.after = after_created_at, after_conclusion_id
        more = after_created_at is None
        return SurveyConclusionPage(
            (conclusion_view().summary,), NOW if more else None,
            CONCLUSION if more else None, more,
        )

    def get_conclusion(self, query, identity):
        if self.fail:
            raise SurveyConclusionReadError(self.fail)
        self.last_identity = identity
        return conclusion_view()


class Creates:
    fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise SurveyConclusionCreateError(self.fail)
        return conclusion_view()


class Validations:
    fail = None

    def validate(self, command):
        self.last = command
        if self.fail:
            raise SurveyConclusionValidationError(self.fail)
        return SurveyConclusionValidationReport(
            uuid.uuid4(), command.trace_id, CONCLUSION, SERIES, PROJECT,
            SURVEY, 1, "DRAFT", 1, 0, 1, 1, 1, 1, 0, 0, True, (), NOW,
        )


class Submissions:
    fail = None

    def submit(self, command):
        self.last = command
        if self.fail:
            raise SurveyConclusionReviewSubmissionError(self.fail)
        return SubmittedProjectReviewRef(
            REVIEW, REVIEW_ROUND, PROJECT, "SRV-05", SERIES, CONCLUSION,
            "SURVEY_CONCLUSION_ALL_V1", (REVIEWER,), ACTOR, NOW,
        )


class SurveyConclusionApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates = Reads(), Creates()
        self.validations, self.submissions = Validations(), Submissions()
        self.reads.fail = self.creates.fail = None
        self.validations.fail = self.submissions.fail = None
        origins = LoginOriginPolicy(["https://plm.example.test"])
        read_router = create_survey_conclusion_read_router(
            sessions=Sessions(), origins=origins, reads=self.reads,
            cursors=SurveyConclusionCursorCodec(b"q" * 32),
        )
        command_router = create_survey_conclusion_command_router(
            sessions=Sessions(), origins=origins, creates=self.creates,
            validations=self.validations, submissions=self.submissions,
            reads=self.reads,
        )
        self.client = TestClient(create_app(
            survey_read_router=read_router,
            survey_command_router=command_router,
        ), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/survey-conclusions"
        self.path = f"{self.root}/{CONCLUSION}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
        }
        self.create_body = {
            "survey_id": str(SURVEY), "round_refs": [str(ROUND)],
            "department_conclusions": [{
                "department_id": str(DEPARTMENT), "title": "Scope",
                "statement": "Confirmed scope",
                "response_refs": [str(RESPONSE)],
            }],
            "module_conclusions": [],
            "evidence_refs": [{
                "evidence_id": str(EVIDENCE), "reference_role": "SUPPORT",
            }],
            "open_issue_refs": [{
                "action_item_id": str(ACTION), "is_blocking": False,
            }],
            "ai_task_refs": [], "supersedes_ref": None,
        }
        self.review_body = {
            "reviewer_ids": [str(REVIEWER)],
            "policy_ref": "SURVEY_CONCLUSION_ALL_V1",
            "due_at": None, "submission_note": None,
        }

    def test_default_closed_and_all_five_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.root).status_code)
            self.assertEqual(404, bare.post(self.root).status_code)

        first = self.client.get(
            self.root + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}",
            headers=self.headers,
        )
        self.assertEqual(200, second.status_code)
        self.assertEqual((NOW, CONCLUSION), self.reads.after)

        detail = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual(str(DOCUMENT_VERSION),
                         detail.json()["data"]["evidence_refs"][0]
                         ["document_version_id"])
        self.assertNotIn("conclusion_evidence_ref_id", detail.text)

        created = self.client.post(
            self.root, headers=self.headers, json=self.create_body)
        self.assertEqual(201, created.status_code)
        self.assertEqual(self.path, created.headers["location"])
        self.assertEqual((ROUND,), self.creates.last.round_refs)

        validated = self.client.post(
            self.path + ":validate", headers=self.headers, content=b"")
        self.assertEqual(200, validated.status_code)
        self.assertTrue(validated.json()["data"]["valid"])
        self.assertEqual(1, validated.json()["data"]
                         ["coverage_summary"]["response_count"])

        submitted = self.client.post(
            self.path + ":submit-review", headers=self.headers,
            json=self.review_body,
        )
        self.assertEqual(201, submitted.status_code)
        self.assertEqual('"v1"', submitted.headers["etag"])
        self.assertEqual(SERIES, self.submissions.last.conclusion_series_id)
        self.assertEqual(str(REVIEW), submitted.json()["data"]["review_id"])

    def test_strict_request_cursor_and_safe_errors(self):
        self.assertEqual(400, self.client.post(
            self.root, headers=self.headers,
            json={**self.create_body, "extra": True},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.path + ":validate", headers=self.headers, json={},
        ).status_code)
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&cursor=bad", headers=self.headers,
        ).status_code)
        self.assertEqual(422, self.client.post(
            self.path + ":submit-review", headers=self.headers,
            json={**self.review_body, "submission_note": "not persisted"},
        ).status_code)
        self.creates.fail = "SURVEY_CONCLUSION_SOURCE_INVALID"
        failed = self.client.post(
            self.root, headers=self.headers, json=self.create_body)
        self.assertEqual(422, failed.status_code)
        self.assertEqual("SURVEY_CONCLUSION_SOURCE_INVALID",
                         failed.json()["error"]["code"])
        self.submissions.fail = "BUSINESS_REVIEW_NOT_ELIGIBLE"
        rejected = self.client.post(
            self.path + ":submit-review", headers=self.headers,
            json=self.review_body,
        )
        self.assertEqual(422, rejected.status_code)
        self.assertNotIn("Traceback", rejected.text)


if __name__ == "__main__":
    unittest.main()
