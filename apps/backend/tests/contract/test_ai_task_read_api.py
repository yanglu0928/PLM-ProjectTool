from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.read_task import create_ai_task_read_router
from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView, AITaskReadError, AITaskView,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


ORIGIN = "https://plm.example.test"


class Reads:
    def __init__(self, value): self.value = value
    def get(self, _query):
        if isinstance(self.value, Exception): raise self.value
        return self.value


class AITaskReadApiTests(unittest.TestCase):
    def setUp(self):
        self.project, self.task = uuid.uuid4(), uuid.uuid4()
        now = datetime(2026, 10, 3, tzinfo=timezone.utc)
        self.view = AITaskView(
            self.task, self.project, "GAP_ANALYSIS", uuid.uuid4(),
            (AITaskInputView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            "gap-analysis.v1", 3, uuid.uuid4(), 2,
            "gap-output.v1", "project-documents.v1", uuid.uuid4(),
            "QUEUED", "NONE", None, uuid.uuid4(), uuid.uuid4(), None, None,
            4, now, None, None,
        )
        self.path = f"/api/v1/projects/{self.project}/ai-tasks/{self.task}"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(), "host": "plm.example.test"}

    def client(self, value=None):
        router = create_ai_task_read_router(
            reads=Reads(self.view if value is None else value),
            origins=LoginOriginPolicy([ORIGIN]),
        )
        return TestClient(create_app(ai_task_read_router=router), base_url=ORIGIN)

    def test_default_closed_and_safe_explicit_projection(self):
        with TestClient(create_app(), base_url=ORIGIN) as closed:
            self.assertEqual(closed.get(self.path, headers=self.headers).status_code, 404)
        with self.client() as client:
            response = client.get(self.path, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v4"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        data = response.json()["data"]
        self.assertEqual(data["prompt_policy_version"], 3)
        self.assertEqual(data["prompt_version_ref"]["version_no"], 2)
        self.assertNotIn("task_parameters", data)
        self.assertNotIn("prompt", data)
        self.assertNotIn("secret", response.text.lower())

    def test_safe_errors_and_query_rejection(self):
        cases = (
            (AITaskReadError("RESOURCE_NOT_FOUND"), 404),
            (AITaskReadError("AUTH_ACCESS_DENIED"), 401),
            (AITaskReadError("LICENSE_OPERATION_DENIED"), 403),
            (AITaskReadError(), 503),
        )
        for error, status in cases:
            with self.subTest(status=status), self.client(error) as client:
                self.assertEqual(client.get(self.path, headers=self.headers).status_code, status)
        with self.client() as client:
            self.assertEqual(client.get(self.path + "?x=1", headers=self.headers).status_code, 400)


if __name__ == "__main__":
    unittest.main()
