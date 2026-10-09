"""Frozen PROJECT/GLOBAL Reference revise opt-in HTTP contract."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_revise import (
    create_global_reference_revise_router, create_project_reference_revise_router,
)
from plm_assistant.modules.solution.application.revise_reference_solution import (
    ReferenceReviseError, ReferenceRevisionView,
)


PROJECT, REFERENCE, VERSION, PRIOR, DOCUMENT, EVIDENCE = (
    uuid.uuid4() for _ in range(6))


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Revises:
    def __init__(self):
        self.commands = []
        self.error = None
        self.bad_project = False
        self.result_lock_version = 1

    def revise(self, command):
        self.commands.append(command)
        if self.error:
            raise ReferenceReviseError(self.error)
        project = command.sources.project_id
        return ReferenceRevisionView(
            command.reference_solution_id, VERSION, command.sources.scope,
            uuid.uuid4() if self.bad_project else project,
            2, PRIOR, b"c" * 32, b"s" * 32,
            datetime(2026, 10, 9, tzinfo=timezone.utc), self.result_lock_version,
        )


class ReferenceReviseApiTests(unittest.TestCase):
    def setUp(self):
        self.revises = Revises()
        self.origins = LoginOriginPolicy(["https://plm.example.test"])
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "revise-" + "r" * 16,
            "if-match": '"v0"',
        }
        self.body = {
            "document_version_ids": [str(DOCUMENT)],
            "evidence_ids": [str(EVIDENCE)],
            "source_project_class": "PLM",
            "deidentification_class": "PROJECT_INTERNAL",
            "applicability": {"industry": "synthetic"},
        }
        self.project_path = (f"/api/v1/projects/{PROJECT}/reference-solutions/"
                             f"{REFERENCE}:revise")
        self.global_path = f"/api/v1/global/reference-solutions/{REFERENCE}:revise"
        routers = (
            create_project_reference_revise_router(
                sessions=Sessions(), origins=self.origins, revises=self.revises),
            create_global_reference_revise_router(
                sessions=Sessions(), origins=self.origins, revises=self.revises),
        )
        self.client = TestClient(create_app(
            project_reference_revise_router=routers[0],
            global_reference_revise_router=routers[1]),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_opt_in_created_and_original_version_shape(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.post(
                self.project_path, headers=self.headers, json=self.body).status_code)
            self.assertEqual(404, bare.post(
                self.global_path, headers=self.headers, json=self.body).status_code)
        for path, scope, project in (
                (self.project_path, "PROJECT", PROJECT),
                (self.global_path, "GLOBAL", None)):
            with self.subTest(scope=scope):
                response = self.client.post(path, headers=self.headers, json=self.body)
                self.assertEqual(201, response.status_code, response.text)
                self.assertEqual('"v1"', response.headers["etag"])
                self.assertEqual("no-store", response.headers["cache-control"])
                self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
                data = response.json()["data"]
                self.assertEqual(str(VERSION), data["reference_version_id"])
                self.assertEqual(str(PRIOR), data["supersedes_version_ref"])
                self.assertEqual(2, data["version_no"])
                self.assertEqual(scope, data["scope"])
                self.assertEqual(str(project) if project else None, data["project_id"])
                self.assertNotIn("content_fingerprint", data)
                self.assertEqual(project, self.revises.commands[-1].sources.project_id)
                self.assertEqual(0, self.revises.commands[-1].expected_lock_version)
                self.assertEqual((DOCUMENT,), self.revises.commands[-1].sources.document_version_ids)

    def test_etag_uses_persisted_lock_not_version_number(self):
        self.revises.result_lock_version = 6
        response = self.client.post(
            self.project_path, headers=self.headers, json=self.body)
        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual(2, response.json()["data"]["version_no"])
        self.assertEqual('"v6"', response.headers["etag"])
        self.assertEqual('"v6"', response.json()["data"]["etag"])

    def test_session_origin_headers_and_body_fail_closed(self):
        variants = (
            (self.project_path, {k: v for k, v in self.headers.items() if k != "cookie"},
             self.body, 401),
            (self.project_path, {**self.headers, "origin": "https://evil.test"},
             self.body, 403),
            (self.project_path, {**self.headers, "x-csrf-token": (b"x" * 32).hex()},
             self.body, 403),
            (self.project_path, {k: v for k, v in self.headers.items() if k != "if-match"},
             self.body, 428),
            (self.project_path, {**self.headers, "if-match": 'W/"v0"'},
             self.body, 400),
            (self.project_path, {k: v for k, v in self.headers.items() if k != "idempotency-key"},
             self.body, 422),
            (self.project_path + "?scope=GLOBAL", self.headers, self.body, 400),
            (self.project_path, self.headers, {**self.body, "name": "forbidden"}, 400),
            (self.project_path, self.headers, {**self.body, "document_version_ids": ["bad"]}, 422),
        )
        for path, headers, body, expected in variants:
            with self.subTest(expected=expected, path=path):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code, response.text)
        self.assertFalse(self.revises.commands)

    def test_service_errors_and_wrong_owner_view(self):
        for code, expected in (("RESOURCE_NOT_FOUND", 404),
                               ("VERSION_CONFLICT", 409),
                               ("CONFLICT_IDEMPOTENCY", 409),
                               ("LICENSE_OPERATION_DENIED", 403),
                               ("SOURCE_UNAVAILABLE", 503)):
            self.revises.error = code
            with self.subTest(code=code):
                response = self.client.post(
                    self.project_path, headers=self.headers, json=self.body)
                self.assertEqual(expected, response.status_code, response.text)
        self.revises.error = None
        self.revises.bad_project = True
        self.assertEqual(503, self.client.post(
            self.project_path, headers=self.headers, json=self.body).status_code)


if __name__ == "__main__":
    unittest.main()
