from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.ai.api.prompt_metadata import create_ai_prompt_read_router
from plm_assistant.modules.ai.application.prompt_metadata import (
    PromptMetadataError, PromptMetadataPage, PromptMetadataView,
)
from plm_assistant.modules.ai.domain.prompt_identity import PromptTaskType
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError


class Sessions:
    valid = True

    def validate(self, token: bytes) -> object:
        if not self.valid:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Metadata:
    def __init__(self) -> None:
        self.view = PromptMetadataView(
            uuid.uuid4(), PromptTaskType.GAP_ANALYSIS, "ACTIVE", 2,
            "schema.synthetic.v1", 1, "rag.synthetic.v1", "provider.synthetic.v1",
            "a" * 64, "b" * 64, 7, datetime.now(timezone.utc),
        )
        self.failure: str | None = None
        self.calls = 0

    def get(self, query, template_id):
        self.calls += 1
        if self.failure:
            raise PromptMetadataError(self.failure)
        if template_id != self.view.template_id:
            raise PromptMetadataError("RESOURCE_NOT_FOUND")
        return self.view

    def list_page(self, query, *, page_size, cursor):
        self.calls += 1
        if self.failure:
            raise PromptMetadataError(self.failure)
        if cursor is not None and cursor != "synthetic-cursor":
            raise PromptMetadataError("REQUEST_MALFORMED")
        return (PromptMetadataPage((self.view,), "synthetic-cursor", True)
                if cursor is None else PromptMetadataPage((), None, False))


class PromptMetadataApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sessions, self.metadata = Sessions(), Metadata()
        router = create_ai_prompt_read_router(
            sessions=self.sessions, prompts=self.metadata,
            origins=LoginOriginPolicy(["https://plm.example.test"]),
        )
        self.client = TestClient(create_app(ai_prompt_read_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.list_path = "/api/v1/admin/ai/prompt-templates"
        self.detail_path = f"{self.list_path}/{self.metadata.view.template_id}"
        self.cookie = "plm_session=" + "ab" * 32

    def get(self, path: str, *, headers: dict[str, str] | None = None):
        return self.client.get(path, headers=headers if headers is not None else {"cookie": self.cookie})

    def test_default_closed_and_safe_detail_projection(self) -> None:
        with TestClient(create_app(), base_url="https://plm.example.test") as default:
            self.assertEqual(default.get(self.list_path).status_code, 404)
            self.assertEqual(default.get(self.detail_path).status_code, 404)
        response = self.get(self.detail_path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v7"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual(set(data), {
            "prompt_template_id", "task_type", "state", "active_version_no",
            "output_schema_ref", "schema_version", "rag_policy_ref",
            "provider_policy_ref", "system_template_hash", "user_template_hash", "etag",
        })
        self.assertEqual(data["active_version_no"], 2)
        self.assertNotIn("system_template\"", response.text)
        self.assertNotIn("user_template\"", response.text)
        self.assertNotIn("secret", response.text.lower())

    def test_list_validation_and_error_mapping(self) -> None:
        first = self.get(self.list_path + "?page_size=1")
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json()["data"]["has_more"])
        second = self.get(self.list_path + "?page_size=1&cursor=synthetic-cursor")
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["data"]["has_more"])
        for path, status in (
            (self.list_path + "?cursor=bad", 400),
            (self.list_path + "?page_size=1&page_size=2", 400),
            (self.list_path + "?unexpected=1", 400),
            (self.list_path + "?page_size=0", 422),
            (self.list_path + "?page_size=201", 422),
            (self.detail_path + "?unexpected=1", 400),
        ):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, status)

    def test_host_session_permission_license_and_bad_projection_fail_closed(self) -> None:
        for headers, expected in (
            ({}, 401), ({"cookie": "plm_session=short"}, 401),
            ({"cookie": self.cookie, "origin": "https://evil.test"}, 403),
        ):
            self.assertEqual(self.get(self.list_path, headers=headers).status_code, expected)
        self.assertEqual(self.metadata.calls, 0)
        self.sessions.valid = False
        self.assertEqual(self.get(self.list_path).status_code, 401)
        self.assertEqual(self.metadata.calls, 0)
        self.sessions.valid = True
        for failure, status in (
            ("AUTH_ACCESS_DENIED", 404), ("LICENSE_OPERATION_DENIED", 403),
            ("RESOURCE_NOT_FOUND", 404), ("AI_PROMPT_UNAVAILABLE", 503),
        ):
            with self.subTest(failure=failure):
                self.metadata.failure = failure
                self.assertEqual(self.get(self.detail_path).status_code, status)
        self.metadata.failure = None
        self.metadata.view = replace(self.metadata.view, state="RETIRED")
        self.assertEqual(self.get(self.detail_path).status_code, 503)
        self.metadata.view = replace(self.metadata.view, state="ACTIVE", system_template_hash="bad")
        self.assertEqual(self.get(self.detail_path).status_code, 503)


if __name__ == "__main__":
    unittest.main()
