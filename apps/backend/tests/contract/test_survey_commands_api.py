from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.survey.api.commands import create_survey_command_router
from plm_assistant.modules.survey.application.change_survey import SurveyStateError
from plm_assistant.modules.survey.application.create_survey import (
    SurveyCreateError, SurveyInitialView,
)
from plm_assistant.modules.survey.application.create_version import (
    CreatedSurveyVersion, SurveyVersionCreateError,
)
from plm_assistant.modules.survey.application.read_surveys import SurveyView
from plm_assistant.modules.survey.application.validate_version import (
    SurveyVersionValidationError, SurveyVersionValidationReport,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT = uuid.uuid4()
SURVEY = uuid.uuid4()
VERSION = uuid.uuid4()
QUESTION = uuid.uuid4()
DEPARTMENT = uuid.uuid4()


class Sessions:
    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Surveys:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise SurveyCreateError(self.fail)
        return SurveyInitialView(SURVEY, PROJECT, "Customer workshop", NOW)


def survey_view(state="ACTIVE", etag='"v1"'):
    return SurveyView(
        SURVEY, PROJECT, "Updated workshop", state, None, uuid.uuid4(),
        NOW, uuid.uuid4(), NOW, etag,
    )


class States:
    def __init__(self):
        self.last = None
        self.fail = None

    def _check(self, command):
        self.last = command
        if self.fail:
            raise SurveyStateError(self.fail)

    def patch(self, command):
        self._check(command)
        return survey_view()

    def archive(self, command):
        self._check(command)
        return survey_view("ARCHIVED", '"v2"')


class Versions:
    def __init__(self):
        self.last = None
        self.fail = None

    def create(self, command):
        self.last = command
        if self.fail:
            raise SurveyVersionCreateError(self.fail)
        return CreatedSurveyVersion(
            VERSION, SURVEY, PROJECT, 1, "DRAFT", b"b" * 32, None,
            uuid.uuid4(), NOW, 0, 1,
        )


class Validations:
    def __init__(self):
        self.last = None
        self.fail = None

    def validate(self, command):
        self.last = command
        if self.fail:
            raise SurveyVersionValidationError(self.fail)
        return SurveyVersionValidationReport(
            uuid.uuid4(), command.trace_id, SURVEY, VERSION, PROJECT,
            1, "DRAFT", 1, 0, 1, 1, 0, True, (), NOW,
        )


class SurveyCommandsApiTests(unittest.TestCase):
    def setUp(self):
        self.surveys, self.states = Surveys(), States()
        self.versions, self.validations = Versions(), Validations()
        router = create_survey_command_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            surveys=self.surveys, states=self.states,
            versions=self.versions, validations=self.validations,
        )
        self.client = TestClient(
            create_app(survey_command_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/surveys"
        self.survey_path = f"{self.root}/{SURVEY}"
        self.version_path = f"{self.survey_path}/versions/{VERSION}"
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"a" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()),
            "if-match": '"v0"',
        }
        self.source = {
            "source_kind": "MANUAL",
            "handover_item_row_id": None,
            "handover_analysis_version_id": None,
            "handover_analysis_id": None,
            "capability_item_row_id": None,
            "capability_baseline_version_id": None,
            "capability_baseline_id": None,
            "template_document_version_id": None,
            "template_document_id": None,
            "manual_source_note": "Facilitator workshop record",
        }
        self.question = {
            "question_id": str(QUESTION), "topic": "Process",
            "question_text": "How is approval performed?",
            "objective": "Confirm the approval path", "answer_type": "TEXT",
            "validation_rule": {"max_length": 1000}, "required": True,
            "condition_rule": None, "expected_output": "An approved workflow",
            "evidence_required": False, "options": [], "sources": [self.source],
        }
        self.version_body = {
            "questions": [self.question],
            "target_department_ids": [str(DEPARTMENT)],
        }

    def test_default_closed_and_all_five_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(self.root).status_code)
            self.assertEqual(404, bare.patch(self.survey_path).status_code)
            self.assertEqual(404, bare.post(self.survey_path + ":archive").status_code)
            self.assertEqual(404, bare.post(self.survey_path + "/versions").status_code)
            self.assertEqual(404, bare.post(self.version_path + ":validate").status_code)

        created = self.client.post(
            self.root, headers=self.headers, json={"name": "Customer workshop"},
        )
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual(self.survey_path, created.headers["location"])
        self.assertEqual(PROJECT, self.surveys.last.project_id)

        patched = self.client.patch(
            self.survey_path, headers=self.headers, json={"name": "Updated workshop"},
        )
        self.assertEqual(200, patched.status_code)
        self.assertEqual('"v1"', patched.headers["etag"])
        self.assertEqual("Updated workshop", self.states.last.name)

        archived = self.client.post(
            self.survey_path + ":archive", headers=self.headers, content=b"",
        )
        self.assertEqual(200, archived.status_code)
        self.assertEqual("ARCHIVED", archived.json()["data"]["state"])

        version = self.client.post(
            self.survey_path + "/versions", headers=self.headers,
            json=self.version_body,
        )
        self.assertEqual(201, version.status_code)
        self.assertEqual('"v1"', version.headers["etag"])
        self.assertEqual(self.version_path, version.headers["location"])
        self.assertEqual(
            "Facilitator workshop record",
            self.versions.last.questions[0].sources[0].manual_source_note,
        )
        self.assertEqual(DEPARTMENT, self.versions.last.target_department_ids[0])

        validated = self.client.post(
            self.version_path + ":validate", headers=self.headers, content=b"",
        )
        self.assertEqual(200, validated.status_code)
        self.assertTrue(validated.json()["data"]["valid"])
        self.assertEqual([], validated.json()["data"]["blocking_issues"])

    def test_security_headers_query_and_json_are_fail_closed(self):
        self.assertEqual(403, self.client.post(
            self.root, headers={**self.headers, "origin": "https://evil.test"},
            json={"name": "Customer workshop"},
        ).status_code)
        no_key = {key: value for key, value in self.headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.root, headers=no_key, json={"name": "Customer workshop"},
        ).status_code)
        no_match = {key: value for key, value in self.headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.patch(
            self.survey_path, headers=no_match, json={"name": "New"},
        ).status_code)
        self.assertEqual(400, self.client.post(
            self.root + "?bad=1", headers=self.headers,
            json={"name": "Customer workshop"},
        ).status_code)
        duplicate = b'{"name":"A","name":"B"}'
        self.assertEqual(400, self.client.post(self.root, headers={
            **self.headers, "content-type": "application/json",
        }, content=duplicate).status_code)
        upper_path = f"/api/v1/projects/{str(PROJECT).upper()}/surveys"
        self.assertEqual(422, self.client.post(
            upper_path, headers=self.headers, json={"name": "Customer workshop"},
        ).status_code)
        malformed_source = {
            **self.version_body,
            "questions": [{
                **self.question,
                "sources": [{key: value for key, value in self.source.items()
                             if key != "manual_source_note"}],
            }],
        }
        self.assertEqual(400, self.client.post(
            self.survey_path + "/versions", headers=self.headers,
            json=malformed_source,
        ).status_code)

    def test_error_mapping_is_stable_and_safe(self):
        self.surveys.fail = "AUTH_ACCESS_DENIED"
        response = self.client.post(
            self.root, headers=self.headers, json={"name": "Customer workshop"},
        )
        self.assertEqual(404, response.status_code)
        self.assertEqual("RESOURCE_NOT_FOUND", response.json()["error"]["code"])
        self.surveys.fail = None

        self.versions.fail = "SURVEY_SOURCE_UNAVAILABLE"
        response = self.client.post(
            self.survey_path + "/versions", headers=self.headers,
            json=self.version_body,
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual("VALIDATION_FAILED", response.json()["error"]["code"])
        self.versions.fail = None

        self.states.fail = "CONFLICT_VERSION"
        response = self.client.patch(
            self.survey_path, headers=self.headers, json={"name": "New"},
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("CONFLICT_VERSION", response.json()["error"]["code"])
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
