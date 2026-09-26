from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.document.api.finalize_upload import create_document_upload_finalize_router
from plm_assistant.modules.document.application.abort_upload import AbortedUpload, UploadAbortError
from plm_assistant.modules.document.application.commit_upload import CommittedUpload, UploadCommitError
from plm_assistant.modules.document.application.upload_access import DocumentUploadAccessError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class _Sessions:
    def __init__(self, user_id):
        self.user_id = user_id

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.user_id})()


class _Commit:
    def __init__(self):
        self.calls = []
        self.failure = None

    def commit(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if self.failure == "ACCESS":
            raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
        if self.failure == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.failure:
            raise UploadCommitError(self.failure)
        return CommittedUpload(command.upload_id, uuid.uuid4(), uuid.uuid4(), 1,
                               uuid.uuid4())


class _Abort:
    def __init__(self):
        self.calls = []
        self.failure = None

    def abort(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if self.failure == "ACCESS":
            raise DocumentUploadAccessError("RESOURCE_NOT_FOUND")
        if self.failure == "LICENSE":
            raise RuntimeLicenseError("EXPIRED")
        if self.failure:
            raise UploadAbortError(self.failure)
        return AbortedUpload(command.upload_id, True)


class DocumentUploadFinalizeApiTests(unittest.TestCase):
    def setUp(self):
        self.user_id, self.project_id, self.upload_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        self.commit, self.abort = _Commit(), _Abort()
        self.factory_calls = []

        def commit_factory(token, csrf):
            self.factory_calls.append(("commit", token, csrf))
            return self.commit

        def abort_factory(token, csrf):
            self.factory_calls.append(("abort", token, csrf))
            return self.abort

        router = create_document_upload_finalize_router(
            sessions=_Sessions(self.user_id),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            commit_factory=commit_factory, abort_factory=abort_factory,
        )
        self.client = TestClient(create_app(document_upload_finalize_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "f" * 16,
        }
        self.base = f"/api/v1/projects/{self.project_id}/document-uploads/{self.upload_id}"

    def test_default_closed_and_project_commit(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.base + ":commit").status_code, 404)
            self.assertEqual(bare.post(self.base + ":abort").status_code, 404)
        response = self.client.post(self.base + ":commit", headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn("/documents/", response.headers["location"])
        self.assertEqual(response.json()["data"]["upload_id"], str(self.upload_id))
        command, key = self.commit.calls[-1]
        self.assertEqual((command.scope, command.project_id, command.actor_id,
                          command.expected_document_version, key),
                         ("PROJECT", self.project_id, self.user_id, None, "f" * 16))
        self.assertEqual(self.factory_calls, [("commit", b"s" * 32, b"c" * 32)])

    def test_global_parent_version_and_abort_pending(self):
        path = f"/api/v1/global/document-uploads/{self.upload_id}"
        response = self.client.post(path + ":commit",
                                    headers={**self.headers, "if-match": '"v3"'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual((self.commit.calls[-1][0].scope,
                          self.commit.calls[-1][0].expected_document_version),
                         ("GLOBAL", 3))
        response = self.client.post(path + ":abort", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {
            "upload_id": str(self.upload_id), "state": "ABORTED", "cleanup_pending": True,
        })
        self.assertEqual(self.abort.calls[-1][0].project_id, None)

    def test_origin_session_csrf_key_and_body_fail_closed(self):
        for missing, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403), ("idempotency-key", 422)):
            with self.subTest(missing=missing):
                headers = {name: value for name, value in self.headers.items()
                           if name != missing}
                self.assertEqual(self.client.post(self.base + ":commit",
                                                  headers=headers).status_code, status)
        self.assertEqual(self.client.post(self.base + ":abort", headers=self.headers,
                                          content=b"unexpected").status_code, 400)
        self.assertEqual(self.commit.calls, [])
        self.assertEqual(self.abort.calls, [])

    def test_if_match_and_safe_error_mapping(self):
        for tag in ('W/"v1"', '"v1","v2"', '"v-1"'):
            with self.subTest(tag=tag):
                self.assertEqual(self.client.post(self.base + ":commit",
                                                  headers={**self.headers, "if-match": tag}).status_code, 400)
        self.commit.failure = "PRECONDITION_REQUIRED"
        self.assertEqual(self.client.post(self.base + ":commit",
                                          headers=self.headers).status_code, 428)
        self.commit.failure = "ACCESS"
        self.assertEqual(self.client.post(self.base + ":commit",
                                          headers=self.headers).status_code, 404)
        self.commit.failure = "LICENSE"
        self.assertEqual(self.client.post(self.base + ":commit",
                                          headers=self.headers).status_code, 403)
        self.abort.failure = "CONFLICT_STATE"
        response = self.client.post(self.base + ":abort", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("Traceback", response.text)
        self.abort.failure = "ACCESS"
        self.assertEqual(self.client.post(self.base + ":abort",
                                          headers=self.headers).status_code, 404)
        self.abort.failure = "LICENSE"
        self.assertEqual(self.client.post(self.base + ":abort",
                                          headers=self.headers).status_code, 403)


if __name__ == "__main__":
    unittest.main()
