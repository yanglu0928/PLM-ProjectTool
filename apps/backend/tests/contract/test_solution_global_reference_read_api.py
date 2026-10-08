"""GLOBAL Reference GET is opt-in, admin-scoped, and safely projected."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.global_reference_read import create_global_reference_read_router
from plm_assistant.modules.solution.application.read_global_reference import (
    GlobalReferenceCurrentView, GlobalReferenceReadError,
)
from plm_assistant.modules.solution.application.read_reference import ReferenceDocumentRefView


IDENTITY, VERSION, DOCUMENT, DOC_VERSION, EVIDENCE, CONFIRMATION, ACTOR = (
    uuid.uuid4() for _ in range(7))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
VIEW = GlobalReferenceCurrentView(
    IDENTITY, VERSION, "Synthetic Global", "REFERENCE_ONLY", None, 1, "DRAFT",
    "PLM", "DEIDENTIFIED", {"industry": "synthetic"},
    (ReferenceDocumentRefView(DOCUMENT, DOC_VERSION),), (EVIDENCE,),
    b"s" * 32, b"c" * 32, CONFIRMATION, ACTOR, NOW, ACTOR, NOW, '"v0"',
)


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")


class Reads:
    view = VIEW
    error = None

    def get_current(self, query, identity):
        if self.error:
            raise GlobalReferenceReadError(self.error)
        return self.view


class GlobalReferenceReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/global/reference-solutions/{IDENTITY}"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_global_reference_read_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads)
        self.client = TestClient(create_app(global_reference_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_opt_in_projection_and_no_confirmation_claim(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual("no-store", response.headers["cache-control"])
        data = response.json()["data"]
        self.assertEqual("GLOBAL", data["scope"])
        self.assertIsNone(data["project_id"])
        self.assertEqual(str(DOC_VERSION), data["document_version_ids"][0])
        self.assertEqual(str(DOCUMENT), data["document_refs"][0]["document_id"])
        self.assertEqual([str(EVIDENCE)], data["evidence_ids"])
        self.assertEqual('"v0"', data["etag"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertNotIn(str(CONFIRMATION), response.text)
        self.assertNotIn("deidentification_confirmation_id", data)
        self.assertNotIn("is_currently_confirmed", data)

    def test_session_origin_query_identity_and_owner_fail_closed(self):
        variants = (
            (self.path, {}, 401, None),
            (self.path, {**self.headers, "origin": "https://evil.test"}, 403, None),
            (self.path + "?project_id=" + str(uuid.uuid4()), self.headers, 400, None),
            (self.path.replace(str(IDENTITY), "invalid"), self.headers, 404, None),
            (self.path, self.headers, 404, "RESOURCE_NOT_FOUND"),
            (self.path, self.headers, 503, "SOLUTION_UNAVAILABLE"),
            (self.path, self.headers, 503, "mismatched"),
        )
        for path, headers, expected, error in variants:
            with self.subTest(expected=expected, error=error):
                self.reads.error = error if error != "mismatched" else None
                self.reads.view = (replace(VIEW, reference_solution_id=uuid.uuid4())
                                   if error == "mismatched" else VIEW)
                response = self.client.get(path, headers=headers)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())
        self.reads.error = None


if __name__ == "__main__":
    unittest.main()
