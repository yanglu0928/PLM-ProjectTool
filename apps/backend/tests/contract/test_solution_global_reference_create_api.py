"""Frozen GLOBAL Reference create HTTP shape remains opt-in and fail-closed."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_create import create_global_reference_create_router
from plm_assistant.modules.solution.application.create_reference_solution import (
    ReferenceCreateError, ReferenceInitialView,
)


REFERENCE, VERSION, ACTOR, DOCUMENT, EVIDENCE, CONFIRMATION = (
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
        self.scope = "GLOBAL"
        self.confirmation = CONFIRMATION

    def create(self, command):
        self.commands.append(command)
        if self.error is not None:
            raise ReferenceCreateError(self.error)
        return ReferenceInitialView(
            REFERENCE, VERSION, self.scope, None, command.name,
            b"a" * 32, b"b" * 32, self.confirmation, ACTOR,
            datetime(2026, 10, 9, tzinfo=timezone.utc),
        )


class GlobalReferenceCreateApiTests(unittest.TestCase):
    def setUp(self):
        self.creates = Creates()
        self.path = "/api/v1/global/reference-solutions"
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "g" * 16,
        }
        self.body = {
            "name": "Synthetic Global Reference",
            "document_version_ids": [str(DOCUMENT)],
            "evidence_ids": [str(EVIDENCE)],
            "source_project_class": "PLM",
            "deidentification_class": "DEIDENTIFIED",
            "applicability": {"industry": "synthetic"},
        }
        router = create_global_reference_create_router(
            sessions=Sessions(), origins=LoginOriginPolicy(["https://plm.example.test"]),
            creates=self.creates,
        )
        self.client = TestClient(create_app(global_reference_create_router=router),
                                 base_url="https://plm.example.test")
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
            "scope": "GLOBAL", "project_id": None,
            "name": "Synthetic Global Reference",
            "eligibility_state": "REFERENCE_ONLY", "version_state": "DRAFT",
            "created_by": str(ACTOR), "created_at": "2026-10-09T00:00:00Z",
            "etag": '"v0"',
        }, response.json()["data"])
        self.assertNotIn("deidentification_confirmation_id", response.json()["data"])
        command = self.creates.commands[-1]
        self.assertEqual("GLOBAL", command.sources.scope)
        self.assertIsNone(command.sources.project_id)
        self.assertEqual((DOCUMENT,), command.sources.document_version_ids)
        self.assertEqual((EVIDENCE,), command.sources.evidence_ids)
        self.assertEqual(b"s" * 32, command.sources.session_token)
        self.assertEqual(b"c" * 32, command.csrf_token)

    def test_security_and_frozen_six_field_shape(self):
        variants = [
            (self.path, {k: v for k, v in self.headers.items() if k != "cookie"}, self.body, 401),
            (self.path, {**self.headers, "origin": "https://evil.test"}, self.body, 403),
            (self.path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()}, self.body, 403),
            (self.path, {k: v for k, v in self.headers.items() if k != "idempotency-key"}, self.body, 422),
            (self.path + "?scope=GLOBAL", self.headers, self.body, 400),
            (self.path, self.headers, {**self.body, "project_id": str(uuid.uuid4())}, 400),
            (self.path, self.headers, {**self.body, "deidentification_confirmation_id": str(CONFIRMATION)}, 400),
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
            f"/api/v1/projects/{uuid.uuid4()}/reference-solutions",
            headers=self.headers, json=self.body).status_code)

    def test_duplicate_json_source_failure_and_wrong_owner_view(self):
        self.assertEqual(400, self.client.post(
            self.path, headers=self.headers,
            content='{"name":"A","name":"B"}').status_code)
        self.creates.error = "RESOURCE_NOT_FOUND"
        self.assertEqual(404, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)
        self.creates.error = "CONFLICT_IDEMPOTENCY"
        self.assertEqual(409, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)
        self.creates.error = "SOURCE_UNAVAILABLE"
        unavailable = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(503, unavailable.status_code)
        self.assertNotIn("Traceback", unavailable.text)
        self.creates.error = None
        self.creates.confirmation = None
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)
        self.creates.confirmation = CONFIRMATION
        self.creates.scope = "PROJECT"
        self.assertEqual(503, self.client.post(
            self.path, headers=self.headers, json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
