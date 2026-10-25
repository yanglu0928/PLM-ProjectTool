"""Frozen PROJECT Reference create HTTP shape and fail-closed checks."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_create import create_project_reference_create_router
from plm_assistant.modules.solution.application.create_reference_solution import (
    ReferenceCreateError, ReferenceInitialView,
)


PROJECT, REFERENCE, VERSION, ACTOR, DOCUMENT, EVIDENCE = (
    uuid.uuid4() for _ in range(6))


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Creates:
    def __init__(self):
        self.commands = []
        self.error = None
        self.result_project = PROJECT

    def create(self, command):
        self.commands.append(command)
        if self.error is not None:
            raise ReferenceCreateError(self.error)
        return ReferenceInitialView(
            REFERENCE, VERSION, "PROJECT", self.result_project, command.name,
            b"a" * 32, b"b" * 32, None, ACTOR,
            datetime(2026, 10, 9, tzinfo=timezone.utc),
        )


class ReferenceCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = f"/api/v1/projects/{PROJECT}/reference-solutions"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "r" * 16,
        }
        self.body = {
            "name": "Project Reference",
            "document_version_ids": [str(DOCUMENT)],
            "evidence_ids": [str(EVIDENCE)],
            "source_project_class": "PLM",
            "deidentification_class": "PROJECT_INTERNAL",
            "applicability": {"industry": "synthetic"},
        }
        router = create_project_reference_create_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates,
        )
        self.client = TestClient(
            create_app(project_reference_create_router=router),
            base_url="https://plm.example.test",
        )
        self.addCleanup(self.client.close)

    def test_opt_in_and_created_contract(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.path, headers=self.headers, json=self.body).status_code)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(201, response.status_code)
        self.assertEqual('"v0"', response.headers["etag"])
        self.assertEqual(f"{self.path}/{REFERENCE}", response.headers["location"])
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        self.assertEqual({
            "reference_solution_id": str(REFERENCE),
            "reference_version_id": str(VERSION),
            "scope": "PROJECT", "project_id": str(PROJECT),
            "name": "Project Reference",
            "eligibility_state": "REFERENCE_ONLY", "version_state": "DRAFT",
            "created_by": str(ACTOR), "created_at": "2026-10-09T00:00:00Z",
            "etag": '"v0"',
        }, response.json()["data"])
        command = self.creates.commands[-1]
        self.assertEqual(PROJECT, command.sources.project_id)
        self.assertEqual((DOCUMENT,), command.sources.document_version_ids)
        self.assertEqual((EVIDENCE,), command.sources.evidence_ids)
        self.assertEqual(b"s" * 32, command.sources.session_token)
        self.assertEqual(b"c" * 32, command.csrf_token)

    def test_security_scope_and_shape_fail_closed(self):
        variants = [
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"}, self.body, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, self.body, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()}, self.body, 403),
            (self.path, {k: v for k, v in self.headers.items() if k != "idempotency-key"}, self.body, 422),
            (self.path + "?scope=GLOBAL", self.headers, self.body, 400),
            (self.path, self.headers, {**self.body, "project_id": str(PROJECT)}, 400),
            (self.path, self.headers, {**self.body, "document_version_ids": ["not-uuid"]}, 422),
            (self.path, self.headers, {**self.body, "applicability": []}, 422),
        ]
        for path, headers, body, expected in variants:
            with self.subTest(expected=expected, path=path, body=body):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code)
                self.assertIn("error", response.json())
        self.assertFalse(self.creates.commands)
        self.assertEqual(404, self.client.post(
            "/api/v1/global/reference-solutions", headers=self.headers,
            json=self.body).status_code)

    def test_duplicate_json_and_source_failure(self):
        raw = '{"name":"A","name":"B"}'
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers, content=raw).status_code)
        self.creates.error = "RESOURCE_NOT_FOUND"
        denied = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(404, denied.status_code)
        self.assertNotIn("PROJECT_INTERNAL", str(denied.json()))
        self.creates.error = "CONFLICT_IDEMPOTENCY"
        conflict = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(409, conflict.status_code)
        self.creates.error = "SOURCE_UNAVAILABLE"
        unavailable = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(503, unavailable.status_code)
        self.assertNotIn("Traceback", unavailable.text)

    def test_wrong_owner_view_is_not_returned(self):
        self.creates.result_project = uuid.uuid4()
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
