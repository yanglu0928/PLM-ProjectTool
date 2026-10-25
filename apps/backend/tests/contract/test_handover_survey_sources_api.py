from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.handover.api.read_cursor import (
    HandoverItemCursorCodec, HandoverSurveySourceCursorCodec,
)
from plm_assistant.modules.handover.api.survey_sources import (
    create_handover_survey_source_router,
)
from plm_assistant.modules.handover.application.read_analyses import (
    HandoverAnalysisReadError, HandoverSurveySourcePage,
    HandoverSurveySourceView,
)
from plm_assistant.modules.platform.application.errors import ApplicationError


PROJECT, ANALYSIS, VERSION, ROW, ITEM = (uuid.uuid4() for _ in range(5))
SESSION = b"s" * 32
SOURCE = HandoverSurveySourceView(
    ROW, VERSION, ANALYSIS, ITEM, PROJECT, "Confirm implementation scope",
    "CONFIRMED",
)


class Sessions:
    def validate(self, token):
        if token != SESSION:
            raise SessionError("AUTH_SESSION_EXPIRED")


class Reads:
    fail = None

    def list_survey_sources(self, query, *, page_size, after_row_id=None):
        self.query = query
        self.after = after_row_id
        if self.fail:
            raise HandoverAnalysisReadError(self.fail)
        return HandoverSurveySourcePage(
            (SOURCE,), ROW if after_row_id is None else None,
            after_row_id is None,
        )


class HandoverSurveySourceApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        router = create_handover_survey_source_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads,
            cursors=HandoverSurveySourceCursorCodec(b"i" * 32),
        )
        self.client = TestClient(
            create_app(handover_survey_source_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{PROJECT}/survey-handover-sources"
        self.headers = {"cookie": "plm_session=" + SESSION.hex()}

    def test_closed_default_and_minimal_paged_response(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path).status_code)
        first = self.client.get(self.path + "?page_size=1", headers=self.headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual("no-store", first.headers["cache-control"])
        item = first.json()["data"]["items"][0]
        self.assertEqual(str(ROW), item["handover_item_row_id"])
        self.assertEqual({"handover_item_row_id", "handover_analysis_version_id",
                          "handover_analysis_id", "analysis_item_id", "project_id",
                          "title", "state"}, set(item))
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.path + "?page_size=1&cursor=" + cursor, headers=self.headers,
        )
        self.assertEqual(200, second.status_code)
        self.assertEqual(ROW, self.reads.after)
        self.assertFalse(second.json()["data"]["has_more"])

    def test_auth_scope_and_query_fail_closed(self):
        self.assertEqual(401, self.client.get(self.path).status_code)
        self.reads.fail = "AUTH_ACCESS_DENIED"
        self.assertEqual(404, self.client.get(
            self.path, headers=self.headers).status_code)
        self.reads.fail = "LICENSE_OPERATION_DENIED"
        self.assertNotEqual(200, self.client.get(
            self.path, headers=self.headers).status_code)
        self.assertNotEqual(200, self.client.get(
            self.path + "?page_size=1&page_size=2", headers=self.headers,
        ).status_code)

    def test_cursor_rejects_project_session_size_family_and_tamper(self):
        codec = HandoverSurveySourceCursorCodec(b"i" * 32)
        token = codec.encode(project_id=PROJECT, session_token=SESSION,
                             page_size=1, row_id=ROW)
        self.assertEqual(ROW, codec.decode(
            token, project_id=PROJECT, session_token=SESSION, page_size=1,
        ))
        for project, session, size, value in (
            (uuid.uuid4(), SESSION, 1, token),
            (PROJECT, b"x" * 32, 1, token),
            (PROJECT, SESSION, 2, token),
            (PROJECT, SESSION, 1, ("A" if token[0] != "A" else "B") + token[1:]),
        ):
            with self.assertRaises(ApplicationError):
                codec.decode(value, project_id=project,
                             session_token=session, page_size=size)
        other = HandoverItemCursorCodec(b"i" * 32).encode(
            project_id=PROJECT, analysis_id=ANALYSIS, version_id=VERSION,
            session_token=SESSION, page_size=1, position=0,
        )
        with self.assertRaises(ApplicationError):
            codec.decode(other, project_id=PROJECT,
                         session_token=SESSION, page_size=1)


if __name__ == "__main__":
    unittest.main()
