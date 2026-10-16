from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest import TestCase

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.list_tasks import create_ai_task_list_router
from plm_assistant.modules.ai.api.task_list_cursor import AITaskListCursorCodec
from plm_assistant.modules.ai.application.task_read import (
    AITaskInputView,
    AITaskPage,
    AITaskReadError,
    AITaskView,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


ORIGIN = "https://plm.example.test"


class Reads:
    def __init__(self, value):
        self.value = value
        self.query = None

    def list(self, query):
        self.query = query
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class AITaskListApiTests(TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.now = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
        self.task = self._view()
        self.position = (self.task.requested_at, self.task.ai_task_id)
        self.page = AITaskPage((self.task,), self.position, True)
        self.path = f"/api/v1/projects/{self.project}/ai-tasks"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "host": "plm.example.test",
        }
        self.codec = AITaskListCursorCodec(b"c" * 32)

    def _view(self):
        return AITaskView(
            uuid.uuid4(), self.project, "GAP_ANALYSIS", uuid.uuid4(),
            (AITaskInputView("DOC-02", uuid.uuid4(), uuid.uuid4()),),
            "gap-analysis.v1", 1, uuid.uuid4(), 2,
            "gap-output.v2", "project-documents.v1", uuid.uuid4(),
            "SUCCEEDED", "AVAILABLE", uuid.uuid4(), uuid.uuid4(),
            uuid.uuid4(), None, None, 2, self.now, self.now, self.now,
        )

    def client(self, value=None):
        reads = Reads(self.page if value is None else value)
        router = create_ai_task_list_router(
            reads=reads, origins=LoginOriginPolicy([ORIGIN]), cursors=self.codec,
        )
        client = TestClient(
            create_app(ai_task_list_router=router), base_url=ORIGIN,
        )
        client.reads = reads
        return client

    def test_default_closed_and_safe_stable_page(self):
        with TestClient(create_app(), base_url=ORIGIN) as closed:
            self.assertEqual(
                closed.get(self.path, headers=self.headers).status_code, 404,
            )
        with self.client() as client:
            response = client.get(
                self.path + "?page_size=1", headers=self.headers,
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()["data"]
            self.assertEqual(len(body["items"]), 1)
            self.assertTrue(body["has_more"])
            self.assertTrue(body["next_cursor"].startswith("ait1."))
            self.assertNotIn(str(self.task.ai_task_id), body["next_cursor"])
            self.assertNotIn("task_parameters", response.text)
            self.assertNotIn("secret", response.text.lower())
            second = client.get(
                self.path + "?page_size=1&cursor=" + body["next_cursor"],
                headers=self.headers,
            )
            self.assertEqual(second.status_code, 200)
            self.assertEqual(client.reads.query.before, self.position)

    def test_query_cursor_and_safe_errors(self):
        with self.client() as client:
            for suffix, status in (
                ("?unknown=1", 400),
                ("?page_size=101", 422),
                ("?page_size=1&page_size=2", 400),
                ("?cursor=ait1.invalid", 400),
            ):
                with self.subTest(suffix=suffix):
                    self.assertEqual(
                        client.get(self.path + suffix, headers=self.headers).status_code,
                        status,
                    )
        for error, status in (
            (AITaskReadError("AUTH_ACCESS_DENIED"), 401),
            (AITaskReadError("RESOURCE_NOT_FOUND"), 404),
            (AITaskReadError("LICENSE_OPERATION_DENIED"), 403),
            (AITaskReadError(), 503),
        ):
            with self.subTest(status=status), self.client(error) as client:
                self.assertEqual(
                    client.get(self.path, headers=self.headers).status_code, status,
                )


if __name__ == "__main__":
    import unittest
    unittest.main()
