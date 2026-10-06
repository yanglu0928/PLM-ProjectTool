from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.survey.api.read import create_survey_read_router
from plm_assistant.modules.survey.api.read_cursor import (
    SurveyCursorCodec, SurveyVersionCursorCodec,
)
from plm_assistant.modules.survey.application.read_surveys import (
    SurveyOptionView, SurveyPage, SurveyQuestionView, SurveyReadError,
    SurveySourceView, SurveyTargetDepartmentView, SurveyVersionPage,
    SurveyVersionView, SurveyView,
)


NOW = datetime(2026, 10, 6, tzinfo=timezone.utc)
PROJECT, SURVEY, VERSION, ACTOR, QUESTION, DEPARTMENT = (
    uuid.uuid4() for _ in range(6)
)
VIEW = SurveyView(SURVEY, PROJECT, "Current-state survey", "ACTIVE", None,
                  ACTOR, NOW, None, NOW, '"v0"')
SOURCE = SurveySourceView("MANUAL", None, None, None, None, None, None,
                          None, None, "Facilitated workshop", 0)
QUESTION_VIEW = SurveyQuestionView(
    QUESTION, 1, "Process", "Describe current process", "Establish baseline",
    "TEXT", {"max_length": 2000}, True, None, "Confirmed process", True,
    (SurveyOptionView("N/A", "Not applicable", None, 0),), (SOURCE,))
VERSION_VIEW = SurveyVersionView(
    VERSION, SURVEY, PROJECT, 1, "DRAFT", "a" * 64, 1, 1, 1, 1,
    None, None, None, ACTOR, NOW, (QUESTION_VIEW,),
    (SurveyTargetDepartmentView(DEPARTMENT, 0),))


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def _check(self, query):
        if self.fail:
            raise SurveyReadError(self.fail)

    def list_surveys(self, query, *, page_size, after_updated_at=None,
                     after_survey_id=None):
        self._check(query)
        self.survey_after = (after_updated_at, after_survey_id)
        more = after_updated_at is None
        return SurveyPage((VIEW,), NOW if more else None,
                          SURVEY if more else None, more)

    def get_survey(self, query, survey_id):
        self._check(query)
        return VIEW

    def list_versions(self, query, *, survey_id, page_size,
                      after_version_no=None):
        self._check(query)
        self.version_after = after_version_no
        more = after_version_no is None
        return SurveyVersionPage((VERSION_VIEW,), 1 if more else None, more)

    def get_version(self, query, *, survey_id, survey_version_id):
        self._check(query)
        return VERSION_VIEW


class SurveyReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.reads.fail = None
        router = create_survey_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, survey_cursors=SurveyCursorCodec(b"a" * 32),
            version_cursors=SurveyVersionCursorCodec(b"v" * 32))
        self.client = TestClient(create_app(survey_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.root = f"/api/v1/projects/{PROJECT}/surveys"

    def test_default_closed_and_two_cursor_families(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for path in (self.root, f"{self.root}/{SURVEY}",
                         f"{self.root}/{SURVEY}/versions",
                         f"{self.root}/{SURVEY}/versions/{VERSION}"):
                self.assertEqual(404, bare.get(path).status_code)
        for path, attr, expected in (
            (self.root, "survey_after", (NOW, SURVEY)),
            (f"{self.root}/{SURVEY}/versions", "version_after", 1),
        ):
            first = self.client.get(path + "?page_size=1", headers=self.headers)
            self.assertEqual(200, first.status_code)
            cursor = first.json()["data"]["next_cursor"]
            second = self.client.get(path + f"?page_size=1&cursor={cursor}",
                                     headers=self.headers)
            self.assertEqual(200, second.status_code)
            self.assertEqual(expected, getattr(self.reads, attr))

    def test_safe_fixed_projections(self):
        survey = self.client.get(f"{self.root}/{SURVEY}", headers=self.headers)
        version = self.client.get(f"{self.root}/{SURVEY}/versions/{VERSION}",
                                  headers=self.headers)
        self.assertEqual('"v0"', survey.headers["etag"])
        self.assertEqual(str(QUESTION), version.json()["data"]["questions"][0]["question_id"])
        self.assertEqual(str(DEPARTMENT), version.json()["data"]["target_departments"][0]["department_id"])
        self.assertNotIn("path", version.text.lower())

    def test_strict_query_session_host_and_cursor_scope(self):
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1", headers=self.headers).status_code)
        self.assertEqual(422, self.client.get(
            self.root + "?page_size=0", headers=self.headers).status_code)
        self.assertEqual(401, self.client.get(self.root).status_code)
        first = self.client.get(self.root + "?page_size=1", headers=self.headers)
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            f"/api/v1/projects/{uuid.uuid4()}/surveys?page_size=1&cursor={cursor}",
            headers=self.headers).status_code)

    def test_safe_error_mapping(self):
        for code, status in (("AUTH_ACCESS_DENIED", 404),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("PROJECT_ARCHIVED", 409),
                             ("SURVEY_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.reads.fail = code
                response = self.client.get(self.root, headers=self.headers)
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
