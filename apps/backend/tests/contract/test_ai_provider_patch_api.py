from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.patch_provider import create_ai_provider_patch_router
from plm_assistant.modules.ai.application.append_provider_config import (
    AIProviderAppendError, AppendedAIProviderConfigResult, PatchAIProviderConfig,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    valid = True

    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if not self.valid or token != b"a" * 32 or csrf_token != b"c" * 32 or not require_csrf:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Appender:
    def __init__(self, provider_id: uuid.UUID) -> None:
        self.provider_id = provider_id
        self.failure: str | None = None
        self.last: PatchAIProviderConfig | None = None

    def patch_result(self, command: PatchAIProviderConfig) -> AppendedAIProviderConfigResult:
        self.last = command
        if self.failure:
            raise AIProviderAppendError(self.failure)
        return AppendedAIProviderConfigResult(self.provider_id, uuid.uuid4(), 2, 1)


class AIProviderPatchApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider_id = uuid.uuid4()
        self.sessions = Sessions()
        self.appender = Appender(self.provider_id)
        router = create_ai_provider_patch_router(
            sessions=self.sessions, providers=self.appender,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_provider_patch_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = "/api/v1/admin/ai/providers/" + str(self.provider_id)
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "if-match": '"v0"',
            "origin": "https://plm.example.test",
        }

    def patch(self, body=None, *, headers=None, path=None):
        return self.client.patch(path or self.path,
                                 json={"display_name": "Synthetic v2"} if body is None else body,
                                 headers=self.headers if headers is None else headers)

    def test_default_closed_and_optional_key_200(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.patch(self.path, json={"display_name": "x"}, headers=self.headers).status_code, 404)
        response = self.patch()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual(response.json()["data"], {
            "provider_id": str(self.provider_id), "config_version": 2, "etag": '"v1"',
        })
        self.assertEqual(self.appender.last.changes, {"display_name": "Synthetic v2"})
        self.assertEqual(len(self.appender.last.idempotency_key), 36)
        supplied = str(uuid.uuid4())
        self.assertEqual(self.patch(headers={**self.headers, "idempotency-key": supplied}).status_code, 200)
        self.assertEqual(self.appender.last.idempotency_key, supplied)

    def test_strict_preconditions_and_partial_body(self) -> None:
        for headers, status in (
            ({key: value for key, value in self.headers.items() if key != "if-match"}, 428),
            ({**self.headers, "if-match": 'W/"v0"'}, 400),
            ({**self.headers, "idempotency-key": "short"}, 422),
            ({**self.headers, "origin": "https://evil.test"}, 403),
            ({**self.headers, "x-csrf-token": "short"}, 403),
        ):
            with self.subTest(headers=headers):
                self.assertEqual(self.patch(headers=headers).status_code, status)
        for body, status in (
            ({}, 400), ({"kind": "CUSTOM"}, 400),
            ({"api_key": "synthetic-rejected"}, 400),
            ({"display_name": None}, 422),
            ({"capabilities": ["CHAT", "CHAT"]}, 422),
            ({"secret_ref": "not-a-uuid"}, 422),
        ):
            with self.subTest(body=body):
                self.assertEqual(self.patch(body).status_code, status)
        self.assertEqual(self.patch(path=self.path + "?unexpected=1").status_code, 400)

    def test_safe_error_mapping(self) -> None:
        self.sessions.valid = False
        self.assertEqual(self.patch().status_code, 401)
        self.sessions.valid = True
        for failure, status in (
            ("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("CONFLICT_VERSION", 409),
            ("CONFLICT_IDEMPOTENCY", 409), ("AI_PROVIDER_STATE_CONFLICT", 409),
            ("AI_PROVIDER_SECRET_UNAVAILABLE", 503),
        ):
            with self.subTest(failure=failure):
                self.appender.failure = failure
                self.assertEqual(self.patch().status_code, status)


if __name__ == "__main__":
    unittest.main()
