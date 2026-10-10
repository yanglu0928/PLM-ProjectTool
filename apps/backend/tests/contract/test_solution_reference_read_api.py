"""PROJECT Reference GET response, Session, scope and error contract."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_read import create_project_reference_read_router
from plm_assistant.modules.solution.application.read_reference import (
    ReferenceCurrentView, ReferenceDocumentRefView, ReferenceReadError,
)


PROJECT, REFERENCE, VERSION, ACTOR, DOCUMENT, EVIDENCE, DOC_ROOT = (
    uuid.uuid4() for _ in range(7))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
VIEW = ReferenceCurrentView(
    REFERENCE, VERSION, PROJECT, "Project Reference", "REFERENCE_ONLY", None,
    1, "DRAFT", "PLM", "PROJECT_INTERNAL", {"industry": "synthetic"},
    (DOCUMENT,), (EVIDENCE,), b"s" * 32, b"c" * 32, ACTOR, NOW, ACTOR, NOW,
    '"v0"',
    document_refs=(ReferenceDocumentRefView(DOC_ROOT, DOCUMENT),),
)


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    def __init__(self):
        self.calls = []
        self.view = VIEW
        self.error = None

    def get_current(self, query, identity):
        self.calls.append((query, identity))
        if self.error:
            raise ReferenceReadError(self.error)
        return self.view


class ReferenceReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/projects/{PROJECT}/reference-solutions/{REFERENCE}"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_project_reference_read_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads)
        self.client = TestClient(
            create_app(project_reference_read_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_opt_in_and_fixed_projection(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "reference_solution_id": str(REFERENCE),
            "reference_version_id": str(VERSION), "scope": "PROJECT",
            "project_id": str(PROJECT), "name": "Project Reference",
            "eligibility_state": "REFERENCE_ONLY", "eligibility_reason": None,
            "version_no": 1, "version_state": "DRAFT",
            "source_project_class": "PLM",
            "deidentification_class": "PROJECT_INTERNAL",
            "applicability": {"industry": "synthetic"},
            "document_version_ids": [str(DOCUMENT)],
            "document_refs": [{"document_id": str(DOC_ROOT),
                               "document_version_id": str(DOCUMENT)}],
            "evidence_ids": [str(EVIDENCE)],
            "source_fingerprint": (b"s" * 32).hex(),
            "content_fingerprint": (b"c" * 32).hex(),
            "created_by": str(ACTOR), "created_at": "2026-10-09T00:00:00Z",
            "version_created_by": str(ACTOR),
            "version_created_at": "2026-10-09T00:00:00Z",
            "etag": '"v0"',
        }, response.json()["data"])
        self.assertEqual(REFERENCE, self.reads.calls[-1][1])
        self.assertEqual(PROJECT, self.reads.calls[-1][0].project_id)

    def test_auth_scope_query_and_failure_envelope(self):
        variants = (
            (self.path, {}, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403),
            (self.path + "?scope=GLOBAL", self.headers, 400),
            (f"/api/v1/projects/{uuid.uuid4()}/reference-solutions/{REFERENCE}",
             self.headers, 503),
            (self.path.replace(str(REFERENCE), "not-uuid"), self.headers, 404),
        )
        for path, headers, expected in variants:
            with self.subTest(path=path, expected=expected):
                self.reads.view = VIEW
                if expected == 503:
                    self.reads.view = replace(VIEW, project_id=uuid.uuid4())
                response = self.client.get(path, headers=headers)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())
                self.assertNotIn("Traceback", response.text)
        self.assertEqual(404, self.client.get(
            f"/api/v1/global/reference-solutions/{REFERENCE}",
            headers=self.headers).status_code)

    def test_read_owner_error_mapping(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("AUTH_ACCESS_DENIED", 401),
                               ("SOLUTION_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.reads.error = code
                response = self.client.get(self.path, headers=self.headers)
                self.assertEqual(expected, response.status_code)


if __name__ == "__main__":
    unittest.main()
