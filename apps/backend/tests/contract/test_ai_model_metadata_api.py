from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.model_metadata import create_ai_model_read_router
from plm_assistant.modules.ai.application.model_metadata import (
    AIModelMetadataError, AIModelMetadataPage, AIModelMetadataView,
)
from plm_assistant.modules.ai.domain.model_definition import AIModelKind
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    valid = True

    def validate(self, token: bytes) -> object:
        if not self.valid:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Metadata:
    def __init__(self) -> None:
        self.view = AIModelMetadataView(
            uuid.uuid4(), uuid.uuid4(), "embed-1", AIModelKind.EMBEDDING,
            "PROVIDER_MANAGED", 1024, False, 8192, ("quality.synthetic.v1",),
            "SUSPENDED", 7, datetime.now(timezone.utc),
        )
        self.failure: str | None = None
        self.calls = 0

    def get(self, query, model_id):
        self.calls += 1
        if self.failure:
            raise AIModelMetadataError(self.failure)
        if model_id != self.view.model_id:
            raise AIModelMetadataError("RESOURCE_NOT_FOUND")
        return self.view

    def list_page(self, query, *, page_size, cursor):
        self.calls += 1
        if self.failure:
            raise AIModelMetadataError(self.failure)
        if cursor is not None and cursor != "synthetic-cursor":
            raise AIModelMetadataError("REQUEST_MALFORMED")
        return (AIModelMetadataPage((self.view,), "synthetic-cursor", True)
                if cursor is None else AIModelMetadataPage((), None, False))


class AIModelMetadataApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.metadata = Sessions(), Metadata()
        router = create_ai_model_read_router(
            sessions=self.sessions, models=self.metadata,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_model_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.list_path = "/api/v1/admin/ai/models"
        self.detail_path = f"{self.list_path}/{self.metadata.view.model_id}"
        self.cookie = "plm_session=" + "ab" * 32

    def get(self, path: str, *, headers: dict[str, str] | None = None):
        return self.client.get(path, headers=headers if headers is not None else {"cookie": self.cookie})

    def test_default_closed_and_safe_detail_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.get(self.list_path).status_code, 404)
            self.assertEqual(default.get(self.detail_path).status_code, 404)
        response = self.get(self.detail_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v7"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual(set(data), {
            "model_id", "provider_id", "provider_model_key", "kind", "revision",
            "embedding_dimension", "capabilities", "quality_profile_refs",
            "quality_status", "state", "etag",
        })
        self.assertEqual(data["quality_status"], "NOT_EVALUATED")
        self.assertEqual(data["state"], "SUSPENDED")
        self.assertNotIn("secret_ref", response.text)
        self.assertNotIn("ciphertext", response.text)

    def test_list_queries_and_error_mapping(self) -> None:
        first = self.get(self.list_path + "?page_size=1")
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["data"]["has_more"])
        second = self.get(self.list_path + "?page_size=1&cursor=synthetic-cursor")
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["data"]["has_more"])
        for path, status in (
            (self.list_path + "?cursor=bad", 400),
            (self.list_path + "?page_size=1&page_size=2", 400),
            (self.list_path + "?order_by=id", 400),
            (self.list_path + "?page_size=0", 422),
            (self.list_path + "?page_size=201", 422),
            (self.detail_path + "?unexpected=1", 400),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, status)

    def test_host_session_and_permission_fail_closed(self) -> None:
        for headers, expected in (
            ({}, 401), ({"cookie": "plm_session=short"}, 401),
            ({"cookie": self.cookie, "origin": "https://evil.test"}, 403),
        ):
            self.assertEqual(self.get(self.list_path, headers=headers).status_code, expected)
        self.assertEqual(self.metadata.calls, 0)
        self.sessions.valid = False
        self.assertEqual(self.get(self.list_path).status_code, 401)
        self.assertEqual(self.metadata.calls, 0)
        self.sessions.valid = True
        for failure, status in (
            ("AUTH_ACCESS_DENIED", 404), ("LICENSE_OPERATION_DENIED", 403),
            ("RESOURCE_NOT_FOUND", 404), ("AI_MODEL_UNAVAILABLE", 503),
        ):
            with self.subTest(failure=failure):
                self.metadata.failure = failure
                self.assertEqual(self.get(self.detail_path).status_code, status)


if __name__ == "__main__":
    unittest.main()
