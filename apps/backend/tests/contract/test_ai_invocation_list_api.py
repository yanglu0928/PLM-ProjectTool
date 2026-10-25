from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest import TestCase

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.invocation_list_cursor import (
    AIInvocationListCursorCodec,
)
from plm_assistant.modules.ai.api.list_invocations import (
    create_ai_invocation_list_router,
)
from plm_assistant.modules.ai.application.invocation_read import (
    AIInvocationContextView,
    AIInvocationPage,
    AIInvocationReadError,
    AIInvocationView,
)
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy


ORIGIN = "https://plm.example.test"


class Reads:
    def __init__(self, value): self.value, self.query = value, None
    def list(self, query):
        self.query = query
        if isinstance(self.value, Exception): raise self.value
        return self.value


class AIInvocationListApiTests(TestCase):
    def setUp(self) -> None:
        self.project, self.task = uuid.uuid4(), uuid.uuid4()
        self.now = datetime(2026, 10, 3, 14, tzinfo=timezone.utc)
        self.invocation = AIInvocationView(
            uuid.uuid4(), self.task, self.project, 2,
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), "model-v1",
            uuid.uuid4(), 2, "gap-output.v2", 2,
            AIInvocationContextView(
                uuid.uuid4(), 1, "project-documents.v1", "NONE", None, None,
            ),
            "SUCCEEDED", "VALID", 100, 20, 300, None, None,
            self.now, self.now, self.now,
        )
        self.position = (2, self.invocation.ai_invocation_id)
        self.page = AIInvocationPage((self.invocation,), self.position, True)
        self.path = (
            f"/api/v1/projects/{self.project}/ai-tasks/{self.task}/invocations"
        )
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "host": "plm.example.test",
        }
        self.codec = AIInvocationListCursorCodec(b"c" * 32)

    def client(self, value=None):
        reads = Reads(self.page if value is None else value)
        router = create_ai_invocation_list_router(
            reads=reads, origins=LoginOriginPolicy([ORIGIN]), cursors=self.codec,
        )
        client = TestClient(
            create_app(ai_task_invocation_list_router=router), base_url=ORIGIN,
        )
        client.reads = reads
        return client

    def test_default_closed_and_minimal_attempt_page(self):
        with TestClient(create_app(), base_url=ORIGIN) as closed:
            self.assertEqual(
                closed.get(self.path, headers=self.headers).status_code, 404,
            )
        with self.client() as client:
            response = client.get(
                self.path + "?page_size=1", headers=self.headers,
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()["data"]
            item = data["items"][0]
            self.assertEqual(item["schema_validation_state"], "VALID")
            self.assertEqual(item["context"]["mode"], "NONE")
            self.assertTrue(data["next_cursor"].startswith("aii1."))
            for forbidden in (
                "provider_request_ref", "request_payload", "response_fingerprint",
                "secret", "context_bundle_fingerprint",
            ):
                self.assertNotIn(forbidden, response.text.lower())
            second = client.get(
                self.path + "?page_size=1&cursor=" + data["next_cursor"],
                headers=self.headers,
            )
            self.assertEqual(second.status_code, 200)
            self.assertEqual(client.reads.query.before, self.position)

    def test_query_and_safe_errors(self):
        with self.client() as client:
            for suffix, status in (
                ("?x=1", 400), ("?page_size=101", 422),
                ("?page_size=1&page_size=2", 400),
                ("?cursor=aii1.invalid", 400),
            ):
                with self.subTest(suffix=suffix):
                    self.assertEqual(
                        client.get(self.path + suffix, headers=self.headers).status_code,
                        status,
                    )
        for error, status in (
            (AIInvocationReadError("AUTH_ACCESS_DENIED"), 401),
            (AIInvocationReadError("RESOURCE_NOT_FOUND"), 404),
            (AIInvocationReadError("LICENSE_OPERATION_DENIED"), 403),
            (AIInvocationReadError(), 503),
        ):
            with self.subTest(status=status), self.client(error) as client:
                self.assertEqual(
                    client.get(self.path, headers=self.headers).status_code, status,
                )


if __name__ == "__main__":
    import unittest
    unittest.main()
