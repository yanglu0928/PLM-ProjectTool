from __future__ import annotations

import hashlib
import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.upload_content import create_document_upload_content_router
from plm_assistant.modules.document.application.receive_upload_content import (
    ReceivedUploadContent, UploadContentError,
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


class _Service:
    def __init__(self):
        self.calls = []
        self.failure = None

    def receive(self, command, *, chunks):
        body = b"".join(chunks)
        self.calls.append((command, body))
        if self.failure == "ACCESS":
            raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
        if self.failure == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.failure:
            raise UploadContentError(self.failure)
        return ReceivedUploadContent(command.upload_id, uuid.uuid4(), len(body),
                                     hashlib.sha256(body).digest(), "application/pdf")


class DocumentUploadContentApiTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.project_id, self.upload_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.service = _Service()
        router = create_document_upload_content_router(
            sessions=_Sessions(self.user_id), origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=lambda token, csrf: self.service, max_bytes=3_000_000,
        )
        self.client = TestClient(create_app(document_upload_content_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.body = b"%PDF-1.7\nsynthetic\n%%EOF\n"
        self.headers = {
            "origin": "https://plm.example.test", "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(), "x-upload-token": "u" * 43,
            "x-content-sha256": hashlib.sha256(self.body).hexdigest(),
            "content-type": "application/octet-stream",
        }
        self.path = f"/api/v1/projects/{self.project_id}/document-uploads/{self.upload_id}/content"

    def test_default_closed_project_and_global_success(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.put(self.path, content=self.body).status_code, 404)
        response = self.client.put(self.path, headers=self.headers, content=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"]["sha256"], hashlib.sha256(self.body).hexdigest())
        self.assertNotIn("locator", response.text)
        command, captured = self.service.calls[-1]
        self.assertEqual((command.scope, command.project_id, command.actor_id, captured),
                         ("PROJECT", self.project_id, self.user_id, self.body))
        global_path = f"/api/v1/global/document-uploads/{self.upload_id}/content"
        self.assertEqual(self.client.put(global_path, headers=self.headers,
                                         content=self.body).status_code, 200)
        self.assertEqual(self.service.calls[-1][0].scope, "GLOBAL")

    def test_stream_is_split_into_bounded_chunks(self):
        pieces = []
        body = b"x" * 1_100_000

        class Probe:
            def receive(self, command, *, chunks):
                for chunk in chunks:
                    pieces.append(len(chunk))
                return ReceivedUploadContent(command.upload_id, uuid.uuid4(), len(body),
                                             hashlib.sha256(body).digest(), "text/plain")

        self.service.receive = Probe().receive
        result = self.client.put(self.path, headers={**self.headers,
            "x-content-sha256": hashlib.sha256(body).hexdigest()}, content=body)
        self.assertEqual(result.status_code, 200)
        self.assertGreater(len(pieces), 1)
        self.assertLessEqual(max(pieces), 1_048_576)

    def test_origin_session_claims_and_oversize_gate(self):
        for missing, expected in (("origin", 403), ("cookie", 401),
                                  ("x-csrf-token", 403), ("x-upload-token", 400),
                                  ("x-content-sha256", 400)):
            with self.subTest(missing=missing):
                headers = {key: value for key, value in self.headers.items() if key != missing}
                self.assertEqual(self.client.put(self.path, headers=headers,
                                                 content=self.body).status_code, expected)
        self.assertEqual(self.client.put(self.path, headers={**self.headers,
            "x-content-sha256": "0" * 64}, content=self.body).status_code, 503)
        self.assertEqual(self.client.put(self.path, headers=self.headers,
                                         content=b"x" * 3_000_001).status_code, 413)

    def test_safe_error_mapping(self):
        for failure, code in (("ACCESS", "RESOURCE_NOT_FOUND"),
                              ("LICENSE", "LICENSE_OPERATION_DENIED"),
                              ("FILE_INTEGRITY_MISMATCH", "FILE_INTEGRITY_MISMATCH"),
                              ("FILE_UPLOAD_EXPIRED", "FILE_UPLOAD_EXPIRED")):
            self.service.failure = failure
            with self.subTest(failure=failure):
                response = self.client.put(self.path, headers=self.headers, content=self.body)
                self.assertEqual(response.json()["error"]["code"], code)


if __name__ == "__main__":
    unittest.main()
