from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.retire_prompt_template import create_ai_prompt_retire_router
from plm_assistant.modules.ai.application.retire_prompt_template import (
    PromptRetireError, RetirePromptTemplate, RetiredPromptTemplate,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Retirements:
    def __init__(self) -> None:
        self.failure: str | None = None
        self.last: RetirePromptTemplate | None = None
        self.replay = False
        self.mismatch = False

    def retire(self, command: RetirePromptTemplate) -> RetiredPromptTemplate:
        self.last = command
        if self.failure:
            raise PromptRetireError(self.failure)
        result = RetiredPromptTemplate(
            uuid.uuid4(), command.prompt_template_id, uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4() if self.replay else command.trace_id,
            "ACTIVE", 2, "RETIRED", command.expected_lock_version,
            command.expected_lock_version + 1,
        )
        return replace(result, prompt_template_id=uuid.uuid4()) if self.mismatch else result


class AIPromptRetireApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.retirements = Retirements()
        router = create_ai_prompt_retire_router(
            sessions=Sessions(), retirements=self.retirements,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_prompt_retire_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.template_id = uuid.uuid4()
        self.path = f"/api/v1/admin/ai/prompt-templates/{self.template_id}:retire"
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test", "if-match": '"v3"',
        }

    def post(self, body: object | None = None, *, headers: dict[str, str] | None = None,
             path: str | None = None):
        return self.client.post(path or self.path, json={} if body is None else body,
                                headers=self.headers if headers is None else headers)

    def test_default_closed_and_first_result(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(self.path, json={}, headers=self.headers).status_code, 404)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v4"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"], {
            "prompt_template_id": str(self.template_id), "state": "RETIRED", "etag": '"v4"',
        })
        self.assertEqual(self.retirements.last.expected_lock_version, 3)
        self.retirements.replay = True
        self.assertEqual(self.post().status_code, 200)
        self.retirements.mismatch = True
        self.assertEqual(self.post().status_code, 503)

    def test_strict_request_and_security(self) -> None:
        for body in ({"state": "RETIRED"}, [], "", None):
            with self.subTest(body=body):
                response = (self.client.post(self.path, headers=self.headers)
                            if body is None else self.post(body))
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.post(headers={k: v for k, v in self.headers.items()
                                           if k != "if-match"}).status_code, 428)
        self.assertEqual(self.post(headers={**self.headers, "if-match": 'W/"v3"'}).status_code, 400)
        self.assertEqual(self.post(headers={**self.headers, "origin": "https://evil.test"}).status_code, 403)
        self.assertEqual(self.post(headers={**self.headers, "cookie": "plm_session=short"}).status_code, 401)
        self.assertEqual(self.post(path=self.path + "?bad=1").status_code, 400)
        self.assertEqual(self.post(path=self.path.replace(str(self.template_id), str(uuid.UUID(int=0)))).status_code, 404)
        self.assertEqual(self.client.post(
            self.path, content='{"x":1,"x":2}',
            headers={**self.headers, "content-type": "application/json"},
        ).status_code, 400)

    def test_error_mapping(self) -> None:
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404), ("AI_PROMPT_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("AI_PROMPT_STATE_CONFLICT", 409),
            ("CONFLICT_VERSION", 409), ("CONFLICT_IDEMPOTENCY", 409),
            ("AI_PROMPT_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.retirements.failure = code
                self.assertEqual(self.post().status_code, status)


if __name__ == "__main__":
    unittest.main()
