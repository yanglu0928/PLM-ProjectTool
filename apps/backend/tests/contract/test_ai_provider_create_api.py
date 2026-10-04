from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.create_provider import create_ai_provider_create_router
from plm_assistant.modules.ai.application.create_provider import AIProviderCreateError, CreateAIProvider
from plm_assistant.modules.ai.application.provider_metadata import AIProviderMetadataView
from plm_assistant.modules.ai.domain.provider_configuration import ProviderCapability, ProviderKind
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    valid = True
    calls = 0

    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        self.calls += 1
        if not self.valid or token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Creator:
    def __init__(self) -> None:
        self.view = AIProviderMetadataView(
            uuid.uuid4(), ProviderKind.OPENAI_COMPATIBLE, "Synthetic Provider",
            "endpoint.synthetic.v1", "cn-beijing", "EXTERNAL_APPROVAL_REQUIRED",
            frozenset({ProviderCapability.CHAT}), "****12345678", "CONFIGURED", 1, 0,
        )
        self.failure: str | None = None
        self.calls = 0
        self.last_command: CreateAIProvider | None = None

    def create_view(self, command: CreateAIProvider) -> AIProviderMetadataView:
        self.calls += 1
        self.last_command = command
        if self.failure:
            raise AIProviderCreateError(self.failure)
        return self.view


class AIProviderCreateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.creator = Sessions(), Creator()
        router = create_ai_provider_create_router(
            sessions=self.sessions, providers=self.creator,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_provider_create_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = "/api/v1/admin/ai/providers"
        self.secret = uuid.uuid4()
        self.body = {
            "kind": "OPENAI_COMPATIBLE", "display_name": "Synthetic Provider",
            "endpoint_policy_ref": "endpoint.synthetic.v1", "secret_ref": str(self.secret),
            "data_region": "cn-beijing", "egress_class": "EXTERNAL_APPROVAL_REQUIRED",
            "capabilities": ["CHAT"],
        }
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test",
        }

    def post(self, body=None, *, headers=None, path=None):
        return self.client.post(path or self.path, json=self.body if body is None else body,
                                headers=self.headers if headers is None else headers)

    def test_default_closed_and_safe_201(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(self.path, json=self.body, headers=self.headers).status_code, 404)
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v0"')
        self.assertEqual(response.headers["location"], self.path + "/" + str(self.creator.view.provider_id))
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual(response.json()["data"]["secret_ref_masked"], "****12345678")
        self.assertNotIn(str(self.secret), response.text)
        self.assertEqual(self.creator.last_command.secret_ref, self.secret)

    def test_strict_body_and_query(self) -> None:
        for change, expected in (
            ({"api_key": "must-not-be-accepted"}, 400),
            ({"secret_ref": "not-a-uuid"}, 422),
            ({"capabilities": ["CHAT", "CHAT"]}, 422),
            ({"kind": "UNKNOWN"}, 422),
        ):
            with self.subTest(change=change):
                result = self.post({**self.body, **change})
                self.assertEqual(result.status_code, expected)
        self.assertEqual(self.post(path=self.path + "?unexpected=1").status_code, 400)
        raw = '{"kind":"OPENAI_COMPATIBLE","kind":"CUSTOM"}'
        self.assertEqual(self.client.post(self.path, content=raw, headers={**self.headers, "content-type": "application/json"}).status_code, 400)

    def test_security_and_error_mapping(self) -> None:
        for change, status in (
            ({"origin": "https://evil.test"}, 403),
            ({"cookie": "plm_session=short"}, 401),
            ({"x-csrf-token": "short"}, 403),
            ({"idempotency-key": "short"}, 422),
        ):
            with self.subTest(change=change):
                self.assertEqual(self.post(headers={**self.headers, **change}).status_code, status)
        self.sessions.valid = False
        self.assertEqual(self.post().status_code, 401)
        self.sessions.valid = True
        for failure, status in (
            ("AUTH_ACCESS_DENIED", 404),
            ("LICENSE_OPERATION_DENIED", 403),
            ("CONFLICT_IDEMPOTENCY", 409),
            ("AI_PROVIDER_SECRET_UNAVAILABLE", 503),
            ("AI_PROVIDER_UNAVAILABLE", 503),
        ):
            with self.subTest(failure=failure):
                self.creator.failure = failure
                response = self.post()
                self.assertEqual(response.status_code, status)
                self.assertNotIn(str(self.secret), response.text)


if __name__ == "__main__":
    unittest.main()
