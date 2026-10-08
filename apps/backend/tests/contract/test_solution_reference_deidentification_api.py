"""Opt-in GLOBAL source attestation HTTP boundaries."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_deidentification import create_reference_deidentification_router
from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ReferenceDeidentificationConfirmError, ReferenceDeidentificationConfirmationView,
)
from plm_assistant.modules.solution.application.preview_reference_deidentification import (
    PreviewDocumentRef, ReferenceDeidentificationPreviewError,
    ReferenceDeidentificationPreviewView,
)
from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    ReferenceDeidentificationRevokeError, RevocationView,
)


DOC, VERSION, EVIDENCE, CONFIRMATION, ACTOR = (uuid.uuid4() for _ in range(5))
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Services:
    def __init__(self):
        self.commands = []
        self.error = None

    def preview(self, command):
        self.commands.append(("preview", command))
        if self.error:
            raise ReferenceDeidentificationPreviewError(self.error)
        return ReferenceDeidentificationPreviewView(
            b"f" * 32, (PreviewDocumentRef(DOC, VERSION),), (EVIDENCE,), NOW)

    def confirm(self, command):
        self.commands.append(("confirm", command))
        if self.error:
            raise ReferenceDeidentificationConfirmError(self.error)
        return ReferenceDeidentificationConfirmationView(
            CONFIRMATION, b"f" * 32, ACTOR, NOW, NOW + timedelta(days=1),
            command.sources.trace_id)

    def revoke(self, command):
        self.commands.append(("revoke", command))
        if self.error:
            raise ReferenceDeidentificationRevokeError(self.error)
        return RevocationView(CONFIRMATION, NOW)


class ReferenceDeidentificationApiTests(unittest.TestCase):
    def setUp(self):
        self.service = Services()
        self.path = "/api/v1/global/reference-deidentification-confirmations"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "r" * 16,
        }
        self.body = {
            "document_version_ids": [str(VERSION)],
            "evidence_ids": [str(EVIDENCE)],
            "source_project_class": "PLM",
            "deidentification_class": "HUMAN_REVIEWED",
            "applicability": {"industry": "synthetic"},
        }
        router = create_reference_deidentification_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            previews=self.service, confirmations=self.service, revocations=self.service)
        self.client = TestClient(create_app(reference_deidentification_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_opt_in_and_all_success_shapes(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for path in (self.path + ":preview", self.path,
                         self.path + f"/{CONFIRMATION}:revoke"):
                self.assertEqual(404, bare.post(path, headers=self.headers, json={}).status_code)
        preview = self.client.post(self.path + ":preview", headers=self.headers, json=self.body)
        self.assertEqual(200, preview.status_code)
        self.assertEqual("no-store", preview.headers["cache-control"])
        self.assertEqual(preview.headers["x-trace-id"], preview.json()["trace_id"])
        self.assertEqual({"source_fingerprint", "document_refs", "evidence_ids", "previewed_at"},
                         set(preview.json()["data"]))
        self.assertEqual([{"document_id": str(DOC), "document_version_id": str(VERSION)}],
                         preview.json()["data"]["document_refs"])
        self.assertEqual("preview", self.service.commands[0][0])
        self.assertEqual("GLOBAL", self.service.commands[0][1].sources.scope)
        self.assertIsNone(self.service.commands[0][1].sources.project_id)
        confirmation = self.client.post(self.path, headers=self.headers, json={
            **self.body, "expected_source_fingerprint": (b"f" * 32).hex(),
            "attestation_statement": "I_VERIFIED_DEIDENTIFICATION",
            "expires_at": "2026-10-10T00:00:00Z",
        })
        self.assertEqual(201, confirmation.status_code)
        self.assertEqual(confirmation.headers["x-trace-id"], confirmation.json()["trace_id"])
        self.assertEqual(CONFIRMATION, uuid.UUID(confirmation.json()["data"]["confirmation_id"]))
        self.assertEqual(b"f" * 32, self.service.commands[1][1].expected_source_fingerprint)
        revoked = self.client.post(self.path + f"/{CONFIRMATION}:revoke",
                                   headers=self.headers, json={"reason_code": "ADMIN_REVIEW"})
        self.assertEqual(200, revoked.status_code)
        self.assertEqual("no-store", revoked.headers["cache-control"])
        self.assertEqual(str(CONFIRMATION), revoked.json()["data"]["confirmation_id"])
        self.assertEqual("revoke", self.service.commands[2][0])

    def test_fail_closed_request_security_and_validation(self):
        cases = [
            (self.path + ":preview", {k: v for k, v in self.headers.items() if k != "cookie"}, self.body, 401),
            (self.path + ":preview", {**self.headers, "origin": "https://evil.test"}, self.body, 403),
            (self.path + ":preview", {**self.headers, "x-csrf-token": (b"x" * 32).hex()}, self.body, 403),
            (self.path + ":preview?scope=GLOBAL", self.headers, self.body, 400),
            (self.path + ":preview", self.headers, {**self.body, "project_id": str(DOC)}, 400),
            (self.path + ":preview", self.headers, {**self.body, "document_version_ids": []}, 422),
            (self.path, self.headers, self.body, 400),
            (self.path, {k: v for k, v in self.headers.items() if k != "idempotency-key"},
             {**self.body, "expected_source_fingerprint": "a" * 64,
              "attestation_statement": "I_VERIFIED_DEIDENTIFICATION",
              "expires_at": "2026-10-10T00:00:00Z"}, 422),
            (self.path, self.headers,
             {**self.body, "expected_source_fingerprint": "A" * 64,
              "attestation_statement": "I_VERIFIED_DEIDENTIFICATION",
              "expires_at": "2026-10-10T00:00:00Z"}, 422),
            (self.path + f"/{CONFIRMATION}:revoke", self.headers, {"reason_code": "OTHER"}, 422),
        ]
        for path, headers, body, expected in cases:
            with self.subTest(path=path, expected=expected):
                self.assertEqual(expected, self.client.post(path, headers=headers, json=body).status_code)
        self.assertFalse(self.service.commands)
        self.assertEqual(400, self.client.post(self.path + ":preview", headers=self.headers,
                                          content='{"a":1,"a":2}').status_code)
        self.assertEqual(404, self.client.post("/api/v1/global/reference-solutions",
                                              headers=self.headers, json=self.body).status_code)

    def test_service_failures_are_classified_without_leakage(self):
        for code, expected in (("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
                               ("LICENSE_OPERATION_DENIED", 403), ("SOURCE_UNAVAILABLE", 503)):
            self.service.error = code
            response = self.client.post(self.path + ":preview", headers=self.headers, json=self.body)
            self.assertEqual(expected, response.status_code)
            self.assertNotIn("HUMAN_REVIEWED", response.text)
        self.service.error = "SOURCE_SNAPSHOT_CHANGED"
        response = self.client.post(self.path, headers=self.headers, json={
            **self.body, "expected_source_fingerprint": "f" * 64,
            "attestation_statement": "I_VERIFIED_DEIDENTIFICATION",
            "expires_at": "2026-10-10T00:00:00Z",
        })
        self.assertEqual(409, response.status_code)
        self.assertEqual("SOURCE_SNAPSHOT_CHANGED", response.json()["error"]["code"])
        self.service.error = "SOLUTION_CONFLICT"
        self.assertEqual(409, self.client.post(self.path + f"/{CONFIRMATION}:revoke",
                                               headers=self.headers,
                                               json={"reason_code": "ADMIN_REVIEW"}).status_code)


if __name__ == "__main__":
    unittest.main()
