"""Frozen PROJECT/GLOBAL Reference eligibility opt-in HTTP contract."""

from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.reference_eligibility import (
    create_global_reference_eligibility_router,
    create_project_reference_eligibility_router,
)
from plm_assistant.modules.solution.application.set_reference_eligibility import (
    ReferenceEligibilityCommandError, ReferenceEligibilityResult,
)


PROJECT, REFERENCE, VERSION, EVENT = (uuid.uuid4() for _ in range(4))


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        if not require_csrf or csrf_token != b"c" * 32:
            raise SessionError("AUTH_ACCESS_DENIED")
        return object()


class Eligibility:
    def __init__(self) -> None:
        self.commands = []
        self.error = None
        self.wrong_project = False
        self.wrong_lock = False

    def set(self, command):
        self.commands.append(command)
        if self.error is not None:
            raise ReferenceEligibilityCommandError(self.error)
        return ReferenceEligibilityResult(
            EVENT, command.reference_solution_id, VERSION, command.scope,
            uuid.uuid4() if self.wrong_project else command.project_id,
            command.requested_state, command.reason,
            command.expected_lock_version + (2 if self.wrong_lock else 1),
        )


class ReferenceEligibilityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.eligibility = Eligibility()
        self.origins = LoginOriginPolicy(["https://plm.example.test"])
        self.headers = {
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "eligibility-" + "e" * 16,
            "if-match": '"v0"',
        }
        self.body = {"eligibility_state": "ELIGIBLE", "reason": "Human reviewed"}
        self.project_path = (f"/api/v1/projects/{PROJECT}/reference-solutions/"
                             f"{REFERENCE}:set-eligibility")
        self.global_path = (f"/api/v1/global/reference-solutions/"
                            f"{REFERENCE}:set-eligibility")
        routers = (
            create_project_reference_eligibility_router(
                sessions=Sessions(), origins=self.origins,
                eligibility=self.eligibility),
            create_global_reference_eligibility_router(
                sessions=Sessions(), origins=self.origins,
                eligibility=self.eligibility),
        )
        self.client = TestClient(create_app(
            project_reference_eligibility_router=routers[0],
            global_reference_eligibility_router=routers[1]),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_both_whitelist_paths(self) -> None:
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
                self.assertEqual(200, response.status_code, response.text)
                self.assertEqual('"v1"', response.headers["etag"])
                self.assertEqual("no-store", response.headers["cache-control"])
                self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
                data = response.json()["data"]
                self.assertEqual(str(EVENT), data["eligibility_event_id"])
                self.assertEqual(str(REFERENCE), data["reference_solution_id"])
                self.assertEqual(str(VERSION), data["reference_version_id"])
                self.assertEqual(scope, data["scope"])
                self.assertEqual(str(project) if project else None, data["project_id"])
                self.assertEqual("ELIGIBLE", data["eligibility_state"])
                self.assertEqual("Human reviewed", data["eligibility_reason"])
                self.assertEqual('"v1"', data["etag"])
                self.assertEqual(project, self.eligibility.commands[-1].project_id)
                self.assertEqual(0, self.eligibility.commands[-1].expected_lock_version)

    def test_response_uses_first_result_lock_and_rejects_wrong_projection(self) -> None:
        headers = {**self.headers, "if-match": '"v6"'}
        response = self.client.post(self.project_path, headers=headers, json=self.body)
        self.assertEqual(200, response.status_code, response.text)
        self.assertEqual('"v7"', response.headers["etag"])
        self.eligibility.wrong_project = True
        self.assertEqual(503, self.client.post(
            self.project_path, headers=headers, json=self.body).status_code)
        self.eligibility.wrong_project = False
        self.eligibility.wrong_lock = True
        self.assertEqual(503, self.client.post(
            self.project_path, headers=headers, json=self.body).status_code)

    def test_session_origin_headers_and_body_fail_closed(self) -> None:
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
            (self.project_path, {k: v for k, v in self.headers.items()
                                 if k != "idempotency-key"}, self.body, 422),
            (self.project_path + "?scope=GLOBAL", self.headers, self.body, 400),
            (self.project_path, self.headers, {**self.body, "extra": True}, 400),
            (self.project_path, self.headers, {**self.body, "reason": 4}, 422),
        )
        for path, headers, body, expected in variants:
            with self.subTest(path=path, expected=expected):
                response = self.client.post(path, headers=headers, json=body)
                self.assertEqual(expected, response.status_code, response.text)
        self.assertFalse(self.eligibility.commands)

    def test_service_error_mapping_and_no_internal_detail(self) -> None:
        for code, status in (
                ("AUTH_ACCESS_DENIED", 404),
                ("RESOURCE_NOT_FOUND", 404),
                ("VERSION_CONFLICT", 409),
                ("CONFLICT_STATE", 409),
                ("CONFLICT_IDEMPOTENCY", 409),
                ("LICENSE_OPERATION_DENIED", 403),
                ("SOURCE_UNAVAILABLE", 503)):
            self.eligibility.error = code
            with self.subTest(code=code):
                response = self.client.post(
                    self.project_path, headers=self.headers, json=self.body)
                self.assertEqual(status, response.status_code, response.text)
                self.assertNotIn("Traceback", response.text)


if __name__ == "__main__":
    unittest.main()
