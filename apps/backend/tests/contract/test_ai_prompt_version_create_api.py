from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.create_prompt_version import (
    MAX_PROMPT_VERSION_BODY, create_ai_prompt_version_router,
)
from plm_assistant.modules.ai.application.append_prompt_version import (
    AppendPromptVersion, AppendedPromptVersion, PromptVersionAppendError,
)
from plm_assistant.modules.ai.domain.prompt_version import PromptVersionDraft
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    def validate(self, token: bytes, *, csrf_token: bytes, require_csrf: bool) -> object:
        if token != b"a" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Versions:
    def __init__(self) -> None:
        self.failure: str | None = None
        self.last: AppendPromptVersion | None = None
        self.replay = False
        self.mismatch = False

    def append(self, command: AppendPromptVersion) -> AppendedPromptVersion:
        self.last = command
        if self.failure:
            raise PromptVersionAppendError(self.failure)
        draft = PromptVersionDraft(
            command.prompt_template_id, command.task_type,
            command.system_template, command.user_template,
            command.output_schema_ref, command.schema_version,
            command.rag_policy_ref, command.provider_policy_ref,
        )
        result = AppendedPromptVersion(
            uuid.uuid4(), command.prompt_template_id, 2, uuid.uuid4(),
            uuid.uuid4(), uuid.uuid4() if self.replay else command.trace_id,
            draft.fingerprint, draft.system_hash, draft.user_hash,
            command.output_schema_ref, command.schema_version,
            command.rag_policy_ref, command.provider_policy_ref,
            command.expected_lock_version, command.expected_lock_version + 1,
        )
        return replace(result, user_hash="0" * 64) if self.mismatch else result


class AIPromptVersionCreateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.versions = Versions()
        router = create_ai_prompt_version_router(
            sessions=Sessions(), versions=self.versions,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_prompt_version_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.template_id = uuid.uuid4()
        self.path = f"/api/v1/admin/ai/prompt-templates/{self.template_id}/versions"
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": str(uuid.uuid4()),
            "origin": "https://plm.example.test", "if-match": '"v3"',
        }
        self.body = {
            "task_type": "GAP_ANALYSIS",
            "system_template": "Synthetic system {context}",
            "user_template": "Synthetic user {input}",
            "output_schema_ref": "schema.synthetic.v1", "schema_version": 1,
            "rag_policy_ref": "rag.synthetic.v1",
            "provider_policy_ref": "provider.synthetic.v1",
        }

    def post(self, body: object | None = None, *, headers: dict[str, str] | None = None):
        return self.client.post(self.path, json=self.body if body is None else body,
                                headers=self.headers if headers is None else headers)

    def test_default_closed_and_safe_201_replay(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(self.path, json=self.body,
                                          headers=self.headers).status_code, 404)
        response = self.post()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["etag"], '"v4"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["location"], self.path + "/2")
        self.assertEqual(response.json()["data"]["version_no"], 2)
        self.assertEqual(self.versions.last.expected_lock_version, 3)
        self.assertNotIn("Synthetic system", response.text)
        self.assertNotIn("Synthetic user", response.text)
        self.versions.replay = True
        self.assertEqual(self.post().status_code, 201)
        self.versions.mismatch = True
        self.assertEqual(self.post().status_code, 503)

    def test_strict_json_version_and_security(self) -> None:
        for body, status in (
            ({**self.body, "extra": "no"}, 400),
            ({**self.body, "schema_version": True}, 422),
            ({**self.body, "task_type": "UNKNOWN"}, 422),
            ([], 400),
        ):
            with self.subTest(body=body):
                self.assertEqual(self.post(body).status_code, status)
        self.assertEqual(self.post(headers={k: v for k, v in self.headers.items()
                                           if k != "if-match"}).status_code, 428)
        self.assertEqual(self.post(headers={**self.headers, "if-match": 'W/"v3"'}).status_code, 400)
        self.assertEqual(self.post(headers={**self.headers, "origin": "https://evil.test"}).status_code, 403)
        self.assertEqual(self.post(headers={**self.headers, "cookie": "plm_session=short"}).status_code, 401)
        self.assertEqual(self.client.post(self.path + "?bad=1", json=self.body,
                                          headers=self.headers).status_code, 400)
        self.assertEqual(self.client.post(
            self.path,
            content='{"task_type":"GAP_ANALYSIS","task_type":"GAP_ANALYSIS"}',
            headers={**self.headers, "content-type": "application/json"},
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.path, content=b"x" * (MAX_PROMPT_VERSION_BODY + 1),
            headers={**self.headers, "content-type": "application/json"},
        ).status_code, 400)

    def test_error_mapping(self) -> None:
        for code, status in (("AUTH_ACCESS_DENIED", 404), ("AI_PROMPT_NOT_FOUND", 404),
                             ("AI_PROMPT_STATE_CONFLICT", 409),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("CONFLICT_VERSION", 409),
                             ("CONFLICT_IDEMPOTENCY", 409),
                             ("AI_PROMPT_CONTENT_UNAPPROVED", 422),
                             ("AI_PROMPT_UNAVAILABLE", 503)):
            with self.subTest(code=code):
                self.versions.failure = code
                self.assertEqual(self.post().status_code, status)


if __name__ == "__main__":
    unittest.main()
