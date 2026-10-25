from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.evidence.api.view_evidence import create_evidence_viewer_router
from plm_assistant.modules.evidence.application.view_evidence import (
    EvidenceViewerDescriptor, EvidenceViewerError,
)


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Viewer:
    def __init__(self):
        self.project = uuid.uuid4()
        self.evidence_id = uuid.uuid4()
        self.document = uuid.uuid4()
        self.version = uuid.uuid4()
        self.failure = None
        self.global_mode = False

    def view(self, query, evidence_id):
        if self.failure is not None:
            raise EvidenceViewerError(self.failure)
        if evidence_id != self.evidence_id:
            raise EvidenceViewerError("RESOURCE_NOT_FOUND")
        return EvidenceViewerDescriptor(
            evidence_id, query.scope, query.project_id, self.document,
            self.version, 3, "application/pdf", 123,
            {"locator_type": "PAGE", "page_no": 2}, "PARSED_NODE",
            "第 2 页", "短摘录",
        )


class EvidenceViewerApiTests(unittest.TestCase):
    def setUp(self):
        self.viewer = Viewer()
        router = create_evidence_viewer_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            viewer=self.viewer,
        )
        self.client = TestClient(create_app(evidence_viewer_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.path = (f"/api/v1/projects/{self.viewer.project}/evidence/"
                     f"{self.viewer.evidence_id}/viewer")

    def test_fixed_version_projection_and_default_closed(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.get(self.path).status_code, 404)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual(data["document_version_id"], str(self.viewer.version))
        self.assertEqual(data["locator"], {"locator_type": "PAGE", "page_no": 2})
        self.assertEqual(data["precision"], "PARSED_NODE")
        self.assertEqual(data["short_preview"], "短摘录")
        self.assertEqual(data["content_url"],
                         f"/api/v1/projects/{self.viewer.project}/documents/"
                         f"{self.viewer.document}/versions/{self.viewer.version}/content")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertNotIn("storage_locator", response.text)
        self.assertNotIn("source_parse_record_id", response.text)

    def test_global_and_error_mapping(self):
        global_path = f"/api/v1/global/evidence/{self.viewer.evidence_id}/viewer"
        response = self.client.get(global_path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["content_url"],
                         f"/api/v1/global/documents/{self.viewer.document}/versions/"
                         f"{self.viewer.version}/content")
        for code, status in (("RESOURCE_NOT_FOUND", 404),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("EVIDENCE_RESOLUTION_UNAVAILABLE", 503),
                             ("EVIDENCE_FINGERPRINT_MISMATCH", 409)):
            self.viewer.failure = code
            with self.subTest(code=code):
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("Traceback", response.text)

    def test_session_and_query_rejection(self):
        self.assertEqual(self.client.get(self.path).status_code, 401)
        self.assertEqual(self.client.get(self.path + "?x=1", headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get(self.path.replace(str(self.viewer.evidence_id),
                                                       str(uuid.uuid4())),
                                         headers=self.headers).status_code, 404)


if __name__ == "__main__":
    unittest.main()
