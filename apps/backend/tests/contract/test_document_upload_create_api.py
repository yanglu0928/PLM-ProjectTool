from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.create_upload import create_document_upload_create_router
from plm_assistant.modules.document.application.create_upload_intent import (
    CreatedUploadIntent, UploadIntentCreateError,
)
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccessError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Sessions:
    def __init__(self, user_id):
        self.user_id = user_id

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.user_id})()


class _Guard:
    denied = False

    def require_valid(self, *, trace_id):
        if self.denied:
            raise RuntimeLicenseError("EXPIRED")
        return object()


class _Service:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.result = CreatedUploadIntent(
            uuid.uuid4(), datetime(2026, 9, 26, tzinfo=timezone.utc), "t" * 43,
        )

    def create(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if self.failure == "ACCESS":
            raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
        if self.failure:
            raise UploadIntentCreateError(self.failure)
        return self.result


class DocumentUploadCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.project_id = uuid.uuid4(), uuid.uuid4()
        self.sessions, self.guard, self.service = _Sessions(self.user_id), _Guard(), _Service()
        self.factory_calls = []

        def factory(token, csrf):
            self.factory_calls.append((token, csrf))
            return self.service

        router = create_document_upload_create_router(
            sessions=self.sessions, origins=LoginOriginPolicy(["https://plm.example.test"]),
            license_guard=self.guard, service_factory=factory,
        )
        self.client = TestClient(create_app(document_upload_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test", "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(), "idempotency-key": "k" * 16,
        }
        self.body = {
            "purpose": "PROJECT_RECORD", "category": "PROJECT_RECORD",
            "title": "Interview", "display_name": "interview.pdf",
            "size_hint_bytes": 120, "mime_hint": "application/pdf",
        }
        self.path = f"/api/v1/projects/{self.project_id}/document-uploads"

    def test_default_closed_and_project_create(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"]["upload_token"], "t" * 43)
        command, key = self.service.calls[-1]
        self.assertEqual((command.scope, command.project_id, command.actor_id),
                         ("PROJECT", self.project_id, self.user_id))
        self.assertEqual((command.purpose_code, key), ("PROJECT_RECORD", "k" * 16))
        self.assertEqual(self.factory_calls, [(b"s" * 32, b"c" * 32)])

    def test_global_and_existing_parent(self):
        document_id, parent = uuid.uuid4(), uuid.uuid4()
        response = self.client.post("/api/v1/global/document-uploads", headers=self.headers,
                                    json={"purpose": "STANDARD_CAPABILITY",
                                          "document_id": str(document_id),
                                          "supersedes_version_id": str(parent),
                                          "display_name": "manual.pdf"})
        self.assertEqual(response.status_code, 201)
        command, _ = self.service.calls[-1]
        self.assertEqual((command.scope, command.project_id, command.target_document_id,
                          command.supersedes_version_id), ("GLOBAL", None, document_id, parent))

    def test_origin_session_csrf_idempotency_and_license_fail_closed(self):
        for missing, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403), ("idempotency-key", 422)):
            with self.subTest(missing=missing):
                headers = {key: value for key, value in self.headers.items() if key != missing}
                self.assertEqual(self.client.post(self.path, headers=headers,
                                                  json=self.body).status_code, status)
        self.guard.denied = True
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json=self.body).status_code, 403)
        self.assertEqual(self.service.calls, [])

    def test_malformed_and_parent_shape_rejected(self):
        for body in ({"purpose": "PROJECT_RECORD", "display_name": "a.pdf"},
                     {**self.body, "supersedes_version_id": str(uuid.uuid4())},
                     {**self.body, "unexpected": True}):
            with self.subTest(body=body):
                response = self.client.post(self.path, headers=self.headers, json=body)
                self.assertIn(response.status_code, (400, 422))
        self.assertEqual(self.service.calls, [])

    def test_safe_failure_mapping(self):
        for failure, code in (("ACCESS", "RESOURCE_NOT_FOUND"),
                              ("CONFLICT_VERSION", "CONFLICT_VERSION"),
                              ("FILE_UPLOAD_EXPIRED", "FILE_UPLOAD_EXPIRED"),
                              ("CONFLICT_IDEMPOTENCY", "CONFLICT_IDEMPOTENCY")):
            self.service.failure = failure
            with self.subTest(failure=failure):
                response = self.client.post(self.path, headers=self.headers, json=self.body)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
