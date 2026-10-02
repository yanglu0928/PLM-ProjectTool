from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.create_task import create_ai_task_create_router
from plm_assistant.modules.ai.application.create_task import (
    AITaskCreateError, CreateAITask, CreatedAITask,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    valid = True

    def validate(self, token: bytes, *, csrf_token: bytes | None = None,
                 require_csrf: bool = False) -> object:
        if (not self.valid or token != b"a" * 32
                or not require_csrf or csrf_token != b"c" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Tasks:
    def __init__(self, result: CreatedAITask) -> None:
        self.result = result
        self.failure: str | None = None
        self.command: CreateAITask | None = None
        self.key: str | None = None

    def create(self, command: CreateAITask, *, idempotency_key: str) -> CreatedAITask:
        self.command, self.key = command, idempotency_key
        if self.failure:
            raise AITaskCreateError(self.failure)
        return self.result


class AITaskCreateApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project_id = uuid.uuid4()
        self.task_id, self.job_id = uuid.uuid4(), uuid.uuid4()
        self.resource_id, self.version_id = uuid.uuid4(), uuid.uuid4()
        self.authorization_id = uuid.uuid4()
        self.sessions = Sessions()
        self.tasks = Tasks(CreatedAITask(self.task_id, self.job_id))
        router = create_ai_task_create_router(
            sessions=self.sessions, tasks=self.tasks,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(
            create_app(ai_task_create_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)
        self.path = f"/api/v1/projects/{self.project_id}/ai-tasks"
        self.body = {
            "task_type": "GAP_ANALYSIS",
            "input_refs": [{
                "resource_type": "DOC-02", "resource_id": str(self.resource_id),
                "version_id": str(self.version_id),
            }],
            "prompt_policy_ref": "prompt.gap.v1",
            "output_schema_ref": "schema.gap.v1",
            "context_policy_ref": "rag.gap.v1",
            "task_parameters": {
                "language": "zh-CN", "max_items": 50, "include_evidence": True,
            },
            "egress_authorization_ref": str(self.authorization_id),
        }
        self.headers = {
            "cookie": "plm_session=" + "61" * 32,
            "x-csrf-token": "63" * 32,
            "idempotency-key": "AI-TASK-CREATE-0001",
            "origin": "https://plm.example.test",
        }

    def test_default_closed_and_explicit_router_returns_safe_202(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.post(
                self.path, json=self.body, headers=self.headers,
            ).status_code, 404)
        response = self.client.post(self.path, json=self.body, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(
            response.headers["location"], self.path + "/" + str(self.task_id),
        )
        self.assertEqual(response.json()["data"], {
            "ai_task_id": str(self.task_id), "job_id": str(self.job_id),
        })
        self.assertEqual(self.tasks.key, "AI-TASK-CREATE-0001")
        self.assertEqual(self.tasks.command.project_id, self.project_id)
        self.assertEqual(self.tasks.command.task_parameters, self.body["task_parameters"])
        self.assertEqual(self.tasks.command.input_refs[0].version_id, self.version_id)
        for forbidden in ("secret", "api_key", "prompt_text", "payload", "traceback"):
            self.assertNotIn(forbidden, response.text.lower())

    def test_strict_request_shape_and_json_validation(self) -> None:
        for change, status in (
            ({"api_key": "forbidden"}, 400),
            ({"input_refs": []}, 422),
            ({"task_parameters": {"nested": []}}, 422),
            ({"task_parameters": {"Bad-Key": "value"}}, 422),
            ({"egress_authorization_ref": str(self.authorization_id).upper()}, 422),
        ):
            with self.subTest(change=change):
                response = self.client.post(
                    self.path, json={**self.body, **change}, headers=self.headers,
                )
                self.assertEqual(response.status_code, status)
        duplicate = '{"task_type":"GAP_ANALYSIS","task_type":"SURVEY_ANALYZE"}'
        self.assertEqual(self.client.post(
            self.path, content=duplicate,
            headers={**self.headers, "content-type": "application/json"},
        ).status_code, 400)
        self.assertEqual(self.client.post(
            self.path + "?unexpected=1", json=self.body, headers=self.headers,
        ).status_code, 400)

    def test_security_preconditions(self) -> None:
        self.assertEqual(self.client.post(
            self.path, json=self.body,
            headers={**self.headers, "origin": "https://evil.test"},
        ).status_code, 403)
        self.assertEqual(self.client.post(
            self.path, json=self.body,
            headers={**self.headers, "x-csrf-token": "short"},
        ).status_code, 403)
        missing_key = dict(self.headers)
        del missing_key["idempotency-key"]
        self.assertEqual(self.client.post(
            self.path, json=self.body, headers=missing_key,
        ).status_code, 422)
        self.sessions.valid = False
        self.assertEqual(self.client.post(
            self.path, json=self.body, headers=self.headers,
        ).status_code, 401)

    def test_safe_error_mapping(self) -> None:
        for code, status in (
            ("AUTH_ACCESS_DENIED", 404), ("RESOURCE_NOT_FOUND", 404),
            ("LICENSE_OPERATION_DENIED", 403), ("CONFLICT_IDEMPOTENCY", 409),
            ("VALIDATION_FAILED", 422), ("AI_TASK_POLICY_INVALID", 422),
            ("AI_TASK_PROMPT_UNAVAILABLE", 422),
            ("AI_EGRESS_AUTHORIZATION_INVALID", 403),
            ("AI_INPUT_UNAVAILABLE", 503), ("AI_TASK_UNAVAILABLE", 503),
        ):
            with self.subTest(code=code):
                self.tasks.failure = code
                response = self.client.post(
                    self.path, json=self.body, headers=self.headers,
                )
                self.assertEqual(response.status_code, status)

    def test_invalid_service_projection_is_not_exposed(self) -> None:
        self.tasks.result = CreatedAITask(uuid.UUID(int=0), self.job_id)
        response = self.client.post(self.path, json=self.body, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.job_id), response.text)


if __name__ == "__main__":
    unittest.main()
