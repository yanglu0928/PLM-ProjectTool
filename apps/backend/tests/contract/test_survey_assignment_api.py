from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.survey.api.assignments import (
    create_survey_assignment_command_router,
    create_survey_assignment_read_router,
)
from plm_assistant.modules.survey.api.read_cursor import SurveyAssignmentCursorCodec
from plm_assistant.modules.survey.application.assignment_views import (
    SurveyAssignmentDetailView,
    SurveyAssignmentPage,
    SurveyAssignmentView,
    SurveyResponseReadView,
)
from plm_assistant.modules.survey.application.create_assignment import (
    SurveyAssignmentCreateError,
)
from plm_assistant.modules.survey.application.read_assignments import (
    SurveyAssignmentReadError,
)
from plm_assistant.modules.survey.application.record_response import (
    SurveyResponseRecordError,
)
from plm_assistant.modules.survey.application.response_views import (
    SurveyResponseWriteView,
)
from plm_assistant.modules.survey.application.review_assignment import (
    SurveyAssignmentReviewError,
)
from plm_assistant.modules.survey.application.submission_views import (
    SurveyAssignmentReviewReceipt,
    SurveyAssignmentSubmitReceipt,
)
from plm_assistant.modules.survey.application.submit_assignment import (
    SurveyAssignmentSubmitError,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT, SURVEY, VERSION, ROUND, ASSIGNMENT, DEPARTMENT, QUESTION, RESPONSE, ANSWER, ACTOR = (
    uuid.uuid4() for _ in range(10)
)


def assignment(state="ASSIGNED", etag='"v0"', count=0):
    return SurveyAssignmentView(
        ASSIGNMENT, ROUND, SURVEY, VERSION, PROJECT, DEPARTMENT, ACTOR,
        state, ACTOR if state in {"SUBMITTED", "VALIDATED"} else None,
        NOW if state in {"SUBMITTED", "VALIDATED"} else None,
        ACTOR if state == "VALIDATED" else None,
        NOW if state == "VALIDATED" else None,
        ACTOR if state == "RETURNED" else None,
        NOW if state == "RETURNED" else None,
        "Clarify" if state == "RETURNED" else None,
        ACTOR, NOW, ACTOR, NOW, etag, count,
    )


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def list_assignments(self, query, *, page_size, after_created_at=None,
                         after_assignment_id=None):
        if self.fail:
            raise SurveyAssignmentReadError(self.fail)
        self.after = after_created_at, after_assignment_id
        more = after_created_at is None
        return SurveyAssignmentPage(
            (assignment(),), NOW if more else None,
            ASSIGNMENT if more else None, more,
        )

    def get_assignment_detail(self, query, identity):
        if self.fail:
            raise SurveyAssignmentReadError(self.fail)
        response = SurveyResponseReadView(
            RESPONSE, QUESTION, "SELF_SERVICE", None, None,
            ACTOR, NOW, "yes", True, (),
        )
        return SurveyAssignmentDetailView(assignment("IN_PROGRESS", '"v1"', 1),
                                          (response,))


class Creates:
    fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise SurveyAssignmentCreateError(self.fail)
        return assignment()


class Responses:
    fail = None

    def record(self, command):
        self.last = command
        if self.fail:
            raise SurveyResponseRecordError(self.fail)
        return SurveyResponseWriteView(
            RESPONSE, ANSWER, ASSIGNMENT, ROUND, VERSION, PROJECT, QUESTION,
            "SELF_SERVICE", None, None, ACTOR, NOW, "IN_PROGRESS", '"v1"', 0,
        )


class Submissions:
    fail = None

    def submit(self, command):
        self.last = command
        if self.fail:
            raise SurveyAssignmentSubmitError(self.fail)
        return SurveyAssignmentSubmitReceipt(
            ASSIGNMENT, ROUND, PROJECT, "SUBMITTED", '"v2"')


class Reviews:
    fail = None

    def _run(self, command, state):
        self.last = command
        if self.fail:
            raise SurveyAssignmentReviewError(self.fail)
        return SurveyAssignmentReviewReceipt(
            ASSIGNMENT, ROUND, PROJECT, state, '"v3"',
            command.return_comment,
        )

    def validate(self, command):
        return self._run(command, "VALIDATED")

    def return_assignment(self, command):
        return self._run(command, "RETURNED")


class SurveyAssignmentApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates = Reads(), Creates()
        self.responses, self.submissions, self.reviews = (
            Responses(), Submissions(), Reviews())
        for service in (self.reads, self.creates, self.responses,
                        self.submissions, self.reviews):
            service.fail = None
        origins = LoginOriginPolicy(["https://plm.example.test"])
        read_router = create_survey_assignment_read_router(
            sessions=Sessions(), origins=origins, reads=self.reads,
            cursors=SurveyAssignmentCursorCodec(b"a" * 32),
        )
        command_router = create_survey_assignment_command_router(
            sessions=Sessions(), origins=origins, creates=self.creates,
            responses=self.responses, submissions=self.submissions,
            reviews=self.reviews,
        )
        self.client = TestClient(create_app(
            survey_read_router=read_router,
            survey_command_router=command_router,
        ), base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/survey-rounds/{ROUND}/assignments"
        self.path = f"{self.root}/{ASSIGNMENT}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
        }

    def test_default_closed_and_all_seven_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.root).status_code)
            self.assertEqual(404, bare.post(self.root).status_code)

        first = self.client.get(self.root + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}", headers=self.headers)
        self.assertEqual(200, second.status_code)
        self.assertEqual((NOW, ASSIGNMENT), self.reads.after)

        detail = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual('"v1"', detail.headers["etag"])
        self.assertEqual(str(RESPONSE), detail.json()["data"]["responses"][0][
            "survey_response_id"])

        created = self.client.post(self.root, headers=self.headers, json={
            "department_id": str(DEPARTMENT), "assignee_user_id": str(ACTOR),
        })
        self.assertEqual(201, created.status_code)
        self.assertEqual(self.path, created.headers["location"])

        recorded = self.client.post(self.path + "/responses", headers=self.headers,
            json={"question_id": str(QUESTION), "response_source": "SELF_SERVICE",
                  "raw_answer": "yes", "answer_value": True, "evidence_ids": [],
                  "project_record_evidence_id": None,
                  "correction_of_response_id": None})
        self.assertEqual(201, recorded.status_code)
        self.assertEqual('"v1"', recorded.headers["etag"])
        self.assertEqual(True, self.responses.last.answer_value)

        self.assertEqual(200, self.client.post(
            self.path + ":submit", headers=self.headers, content=b"").status_code)
        self.headers["if-match"] = '"v2"'
        self.assertEqual(200, self.client.post(
            self.path + ":validate", headers=self.headers, content=b"").status_code)
        returned = self.client.post(
            self.path + ":return", headers=self.headers,
            json={"comment": "Clarify"})
        self.assertEqual(200, returned.status_code)
        self.assertEqual("Clarify", returned.json()["data"]["return_comment"])

    def test_strict_requests_cursor_binding_and_safe_errors(self):
        self.assertEqual(400, self.client.post(self.root, headers=self.headers,
            json={"department_id": str(DEPARTMENT), "assignee_user_id": None,
                  "extra": 1}).status_code)
        self.assertEqual(428, self.client.post(
            self.path + ":submit",
            headers={key: value for key, value in self.headers.items()
                     if key != "if-match"}, content=b"").status_code)

        first = self.client.get(self.root + "?page_size=1", headers=self.headers)
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            self.root + f"?page_size=2&cursor={cursor}",
            headers=self.headers).status_code)

        self.responses.fail = "SURVEY_ASSIGNMENT_STATE_INVALID"
        failed = self.client.post(self.path + "/responses", headers=self.headers,
            json={"question_id": str(QUESTION), "response_source": "SELF_SERVICE",
                  "raw_answer": "yes", "answer_value": True, "evidence_ids": [],
                  "project_record_evidence_id": None,
                  "correction_of_response_id": None})
        self.assertEqual(409, failed.status_code)
        self.assertEqual("CONFLICT_STATE", failed.json()["error"]["code"])
        self.assertNotIn("Traceback", failed.text)


if __name__ == "__main__":
    unittest.main()
