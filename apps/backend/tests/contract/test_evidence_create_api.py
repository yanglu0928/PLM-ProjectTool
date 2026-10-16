from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.evidence.api.create_evidence import create_evidence_create_router
from plm_assistant.modules.evidence.application.create_evidence import CreatedEvidence, EvidenceCreateError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Sessions:
    def __init__(self, user_id):
        self.user_id = user_id

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.user_id})()


class _Service:
    def __init__(self):
        self.calls = []
        self.failure = None

    def create(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if self.failure == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.failure:
            raise EvidenceCreateError(self.failure)
        return CreatedEvidence(
            uuid.uuid4(), command.scope, command.project_id,
            command.document_id, command.document_version_id,
            command.locator, b"x" * 32, command.display_label,
            command.display_excerpt, datetime(2026, 10, 1, tzinfo=timezone.utc),
        )


class EvidenceCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project = uuid.uuid4(), uuid.uuid4()
        self.service = _Service()
        self.factory_calls = []

        def factory(token, csrf):
            self.factory_calls.append((token, csrf))
            return self.service

        router = create_evidence_create_router(
            sessions=_Sessions(self.actor), origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=factory,
        )
        self.client = TestClient(create_app(evidence_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test", "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(), "idempotency-key": "k" * 16,
        }
        self.body = {
            "document_id": str(uuid.uuid4()), "document_version_id": str(uuid.uuid4()),
            "locator": {"locator_type": "DOCUMENT"}, "display_label": "全文",
        }
        self.path = f"/api/v1/projects/{self.project}/evidence"

    def test_default_closed_and_project_response(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        result = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.headers["cache-control"], "no-store")
        self.assertEqual(result.headers["etag"], '"v0"')
        self.assertEqual(result.json()["data"]["eligibility_state"], "CANDIDATE")
        self.assertEqual(result.json()["data"]["content_fingerprint"], "78" * 32)
        self.assertNotIn("storage_locator", result.text)
        command, key = self.service.calls[-1]
        self.assertEqual((command.actor_id, command.project_id, key),
                         (self.actor, self.project, "k" * 16))
        self.assertEqual(self.factory_calls, [(b"s" * 32, b"c" * 32)])

    def test_global_and_parser_node_shape(self):
        parse_record = uuid.uuid4()
        body = {**self.body, "locator": {"locator_type": "SECTION", "section_path": "word/heading/1/1"},
                "parse_record_id": str(parse_record)}
        result = self.client.post("/api/v1/global/evidence", headers=self.headers, json=body)
        self.assertEqual(result.status_code, 201)
        command, _ = self.service.calls[-1]
        self.assertEqual((command.scope, command.project_id, command.parse_record_id),
                         ("GLOBAL", None, parse_record))

    def test_browser_controls_and_malformed_body(self):
        for missing, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403), ("idempotency-key", 422)):
            with self.subTest(missing=missing):
                headers = {key: value for key, value in self.headers.items() if key != missing}
                self.assertEqual(self.client.post(self.path, headers=headers,
                                                  json=self.body).status_code, status)
        for body in ({**self.body, "unexpected": 1},
                     {"document_id": self.body["document_id"]},
                     {**self.body, "document_version_id": "bad"}):
            with self.subTest(body=body):
                self.assertIn(self.client.post(self.path, headers=self.headers,
                                               json=body).status_code, (400, 422))
        self.assertEqual(self.service.calls, [])

    def test_safe_error_mapping(self):
        for failure, status, code in (("RESOURCE_NOT_FOUND", 404, "RESOURCE_NOT_FOUND"),
                                      ("EVIDENCE_LOCATOR_INVALID", 422, "EVIDENCE_LOCATOR_INVALID"),
                                      ("EVIDENCE_RESOLUTION_UNAVAILABLE", 422, "EVIDENCE_LOCATOR_INVALID"),
                                      ("CONFLICT_IDEMPOTENCY", 409, "CONFLICT_IDEMPOTENCY"),
                                      ("LICENSE", 403, "LICENSE_OPERATION_DENIED")):
            self.service.failure = failure
            with self.subTest(failure=failure):
                response = self.client.post(self.path, headers=self.headers, json=self.body)
                self.assertEqual((response.status_code, response.json()["error"]["code"]),
                                 (status, code))
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
