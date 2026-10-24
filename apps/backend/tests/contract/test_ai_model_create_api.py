from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.create_model import create_ai_model_create_router
from plm_assistant.modules.ai.application.create_model import AIModelCreateError, CreateAIModel
from plm_assistant.modules.ai.application.model_metadata import AIModelMetadataView
from plm_assistant.modules.ai.domain.model_definition import AIModelKind
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Creator:
    def __init__(self) -> None:
        self.view = AIModelMetadataView(
            uuid.uuid4(), uuid.uuid4(), "embed-synthetic", AIModelKind.EMBEDDING,
            "PROVIDER_MANAGED", 1024, False, 8192, (), "SUSPENDED", 0,
            datetime(2026, 10, 2, tzinfo=timezone.utc),
        )
        self.failure: str | None = None
        self.last: CreateAIModel | None = None

    def create_view(self, command: CreateAIModel) -> AIModelMetadataView:
        self.last = command
        if self.failure:
            raise AIModelCreateError(self.failure)
        return self.view


class AIModelCreateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.creator = Creator()
        router = create_ai_model_create_router(
            sessions=Sessions(), models=self.creator,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_model_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = "/api/v1/admin/ai/models"
        self.body = {
            "provider_id": str(self.creator.view.provider_id),
            "provider_model_key": "embed-synthetic", "kind": "EMBEDDING",
            "revision": "PROVIDER_MANAGED", "embedding_dimension": 1024,
            "capabilities": {"structured_output": False, "context_window_tokens": 8192},
            "quality_profile_refs": [],
        }
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test",
        }

    def post(self, body: object | None = None, *, headers: dict[str, str] | None = None):
        return self.client.post(self.path, json=self.body if body is None else body,
                                headers=self.headers if headers is None else headers)

    def test_default_closed_and_initial_201(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(self.path, json=self.body,
                                          headers=self.headers).status_code, 404)
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["location"], self.path + "/" + str(self.creator.view.model_id))
        self.assertEqual(response.json()["data"]["quality_status"], "NOT_EVALUATED")
        self.assertEqual(response.json()["data"]["state"], "SUSPENDED")
        self.assertEqual(self.creator.last.embedding_dimension, 1024)

    def test_strict_request_and_security(self) -> None:
        for body, status in (
            ({**self.body, "api_key": "not-allowed"}, 400),
            ({**self.body, "embedding_dimension": True}, 422),
            ({**self.body, "provider_id": "invalid"}, 422),
            ({**self.body, "capabilities": {"structured_output": False}}, 400),
        ):
            with self.subTest(body=body):
                self.assertEqual(self.post(body).status_code, status)
        self.assertEqual(self.post(headers={**self.headers, "origin": "https://evil.test"}).status_code, 403)
        self.assertEqual(self.post(headers={**self.headers, "cookie": "plm_session=short"}).status_code, 401)
        self.assertEqual(self.client.post(self.path + "?bad=1", json=self.body,
                                          headers=self.headers).status_code, 400)

    def test_safe_error_mapping(self) -> None:
        for code, status in (("AI_MODEL_QUALITY_UNVERIFIED", 422),
                             ("AI_MODEL_ALREADY_EXISTS", 409),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("CONFLICT_IDEMPOTENCY", 409),
                             ("AI_MODEL_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.creator.failure = code
                self.assertEqual(self.post().status_code, status)


if __name__ == "__main__":
    unittest.main()
