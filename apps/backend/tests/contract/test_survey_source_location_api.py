from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.survey.api.source_location import (
    create_survey_source_location_router,
)
from plm_assistant.modules.survey.application.source_location import (
    SurveyPublicLocation, SurveySourceLocationError, SurveySourceLocationView,
    SurveySourceRecordRef,
)


PROJECT, SURVEY, VERSION, QUESTION = (uuid.uuid4() for _ in range(4))
ANALYSIS, ANALYSIS_VERSION, ITEM, EVIDENCE = (uuid.uuid4() for _ in range(4))


class Sessions:
    def validate(self, token, **kwargs):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Locations:
    fail = None

    def locate(self, query, **kwargs):
        self.query, self.kwargs = query, kwargs
        if self.fail:
            raise SurveySourceLocationError(self.fail)
        return SurveySourceLocationView(
            "HANDOVER_ITEM", 0, "LOCATABLE", True,
            SurveySourceRecordRef(
                "HANDOVER_ITEM", ANALYSIS, ANALYSIS_VERSION, ITEM,
            ),
            (SurveyPublicLocation(
                "BUSINESS_RECORD", "PROJECT", PROJECT,
                ANALYSIS, ANALYSIS_VERSION, ITEM,
            ), SurveyPublicLocation(
                "EVIDENCE", "PROJECT", PROJECT, EVIDENCE,
            )), None,
        )


class SurveySourceLocationApiTests(unittest.TestCase):
    def setUp(self):
        self.locations = Locations()
        self.locations.fail = None
        router = create_survey_source_location_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            locations=self.locations,
        )
        self.client = TestClient(create_app(survey_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.path = (
            f"/api/v1/projects/{PROJECT}/surveys/{SURVEY}/versions/{VERSION}"
            f"/questions/{QUESTION}/sources/0/location"
        )

    def test_default_closed_and_strict_public_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        data = response.json()["data"]
        self.assertEqual({
            "record_kind": "HANDOVER_ITEM",
            "handover_analysis_id": str(ANALYSIS),
            "handover_analysis_version_id": str(ANALYSIS_VERSION),
            "analysis_item_id": str(ITEM),
        }, data["record_ref"])
        self.assertEqual("BUSINESS_RECORD", data["locations"][0]["location_kind"])
        self.assertEqual(str(EVIDENCE), data["locations"][1]["evidence_id"])
        for forbidden in ("row_id", "path", "locator", "download_url", "content"):
            self.assertNotIn(forbidden, response.text.lower())
        self.assertEqual(VERSION, self.locations.kwargs["survey_version_id"])

    def test_manual_unavailable_projection(self):
        def manual(query, **kwargs):
            return SurveySourceLocationView(
                "MANUAL", 0, "UNAVAILABLE", False, None, (),
                "MANUAL_SOURCE_NOT_FIXED",
            )
        self.locations.locate = manual
        data = self.client.get(self.path, headers=self.headers).json()["data"]
        self.assertIsNone(data["record_ref"])
        self.assertEqual([], data["locations"])
        self.assertEqual("MANUAL_SOURCE_NOT_FIXED", data["unavailable_reason"])

    def test_query_body_path_session_and_host_are_strict(self):
        self.assertEqual(400, self.client.get(
            self.path + "?expand=content", headers=self.headers).status_code)
        self.assertEqual(400, self.client.request(
            "GET", self.path, headers=self.headers, content=b"{}").status_code)
        self.assertEqual(422, self.client.get(
            self.path.replace("/sources/0/", "/sources/00/"),
            headers=self.headers).status_code)
        self.assertEqual(422, self.client.get(
            self.path.replace(str(QUESTION), str(QUESTION).upper()),
            headers=self.headers).status_code)
        self.assertEqual(401, self.client.get(self.path).status_code)
        with TestClient(create_app(survey_read_router=
                create_survey_source_location_router(
                    sessions=Sessions(), origins=LoginOriginPolicy(
                        ["https://plm.example.test"]), locations=self.locations)),
                base_url="https://other.example.test") as untrusted:
            self.assertEqual(403, untrusted.get(
                self.path, headers=self.headers).status_code)

    def test_safe_error_mapping_and_invalid_service_projection(self):
        for code, status in (("AUTH_ACCESS_DENIED", 404),
                             ("RESOURCE_NOT_FOUND", 404),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("VALIDATION_FAILED", 422),
                             ("SOURCE_LOCATION_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.locations.fail = code
                self.assertEqual(status, self.client.get(
                    self.path, headers=self.headers).status_code)
        self.locations.fail = None
        self.locations.locate = lambda query, **kwargs: SurveySourceLocationView(
            "HANDOVER_ITEM", 0, "LOCATABLE", True, None, (), None,
        )
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(503, response.status_code)
        self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
