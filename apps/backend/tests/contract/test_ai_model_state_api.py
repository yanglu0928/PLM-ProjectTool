from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.change_model_state import create_ai_model_state_router
from plm_assistant.modules.ai.application.change_model_state import (
    AIModelStateError, AIModelStateResult, ChangeAIModelState,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class States:
    def __init__(self) -> None:
        self.failure: str | None = None
        self.last: ChangeAIModelState | None = None

    def change(self, command: ChangeAIModelState) -> AIModelStateResult:
        self.last = command
        if self.failure:
            raise AIModelStateError(self.failure)
        before = "AVAILABLE" if command.operation == "SUSPEND" else "SUSPENDED"
        state = "SUSPENDED" if command.operation == "SUSPEND" else "RETIRED"
        return AIModelStateResult(
            uuid.uuid4(), command.model_id, uuid.uuid4(), uuid.uuid4(),
            command.trace_id, command.operation, before, state,
            command.expected_lock_version, command.expected_lock_version + 1,
        )


class AIModelStateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.states = States()
        router = create_ai_model_state_router(
            sessions=Sessions(), models=self.states,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_model_state_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = "/api/v1/admin/ai/models/" + str(uuid.uuid4()) + ":set-state"
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test", "if-match": '"v3"',
        }

    def post(self, body: object | None = None, *, headers: dict[str, str] | None = None):
        return self.client.post(self.path, json={"state": "RETIRED"} if body is None else body,
                                headers=self.headers if headers is None else headers)

    def test_default_closed_and_safe_200(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(self.path, json={"state": "RETIRED"},
                                          headers=self.headers).status_code, 404)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v4"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"]["state"], "RETIRED")
        self.assertEqual(self.states.last.operation, "RETIRE")
        suspended = self.post({"state": "SUSPENDED"})
        self.assertEqual(suspended.status_code, 200)
        self.assertEqual(self.states.last.operation, "SUSPEND")

    def test_strict_body_version_and_security(self) -> None:
        for body, status in (
            ({"state": "AVAILABLE"}, 422),
            ({"state": "RETIRED", "quality_profile_ref": "synthetic"}, 400),
            ({"state": 1}, 422),
            ([], 400),
        ):
            with self.subTest(body=body):
                self.assertEqual(self.post(body).status_code, status)
        self.assertEqual(self.post(headers={k: v for k, v in self.headers.items()
                                           if k != "if-match"}).status_code, 428)
        self.assertEqual(self.post(headers={**self.headers, "if-match": 'W/"v3"'}).status_code, 400)
        self.assertEqual(self.post(headers={**self.headers, "origin": "https://evil.test"}).status_code, 403)
        self.assertEqual(self.post(headers={**self.headers, "cookie": "plm_session=short"}).status_code, 401)
        self.assertEqual(self.client.post(self.path + "?bad=1", json={"state": "RETIRED"},
                                          headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post(self.path, content='{"state":"RETIRED","state":"SUSPENDED"}',
                                          headers={**self.headers, "content-type": "application/json"}).status_code, 400)

    def test_error_mapping(self) -> None:
        for code, status in (("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
                             ("LICENSE_OPERATION_DENIED", 403), ("CONFLICT_VERSION", 409),
                             ("CONFLICT_STATE", 409), ("CONFLICT_IDEMPOTENCY", 409),
                             ("AI_MODEL_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.states.failure = code
                self.assertEqual(self.post().status_code, status)


if __name__ == "__main__":
    unittest.main()
