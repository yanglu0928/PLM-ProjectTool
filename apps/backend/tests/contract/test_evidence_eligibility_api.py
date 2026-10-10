from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.evidence.api.set_eligibility import create_evidence_eligibility_router
from plm_assistant.modules.evidence.application.set_eligibility import (
    EvidenceEligibilityCommandError, SetEvidenceEligibilityResult,
)


class _Sessions:
    def __init__(self, user_id):
        self.user_id = user_id

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.user_id})()


class _Service:
    failure = None

    def __init__(self):
        self.calls = []

    def set(self, command, *, idempotency_key):
        self.calls.append((command, idempotency_key))
        if self.failure:
            raise EvidenceEligibilityCommandError(self.failure)
        return SetEvidenceEligibilityResult(
            command.evidence_id, command.requested_state,
            command.reason, f'"v{command.expected_version + 1}"',
        )


class EvidenceEligibilityApiTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.evidence = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.service = _Service()
        self.factory_calls = []

        def factory(token, csrf):
            self.factory_calls.append((token, csrf))
            return self.service

        router = create_evidence_eligibility_router(
            sessions=_Sessions(self.actor),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=factory,
        )
        self.client = TestClient(create_app(evidence_eligibility_router=router),
                                 base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.project}/evidence/"
                     f"{self.evidence}:set-eligibility")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": "k" * 16,
            "if-match": '"v0"',
        }
        self.body = {"eligibility_state": "ELIGIBLE", "reason": "人工已核对原文"}

    def test_default_closed_and_project_success(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["etag"], '"v1"')
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"]["eligibility_state"], "ELIGIBLE")
        command, key = self.service.calls[-1]
        self.assertEqual((command.actor_id, command.project_id,
                          command.expected_version, key),
                         (self.actor, self.project, 0, "k" * 16))
        self.assertEqual(self.factory_calls[-1], (b"s" * 32, b"c" * 32))

    def test_global_scope_and_ineligible(self):
        response = self.client.post(
            f"/api/v1/global/evidence/{self.evidence}:set-eligibility",
            headers=self.headers,
            json={"eligibility_state": "INELIGIBLE", "reason": "来源不足"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(self.service.calls[-1][0].project_id)
        self.assertEqual(self.service.calls[-1][0].scope, "GLOBAL")

    def test_required_browser_and_precondition_headers(self):
        for missing, expected in (
            ("origin", 403), ("cookie", 401), ("x-csrf-token", 403),
            ("idempotency-key", 422), ("if-match", 428),
        ):
            with self.subTest(missing=missing):
                headers = {name: value for name, value in self.headers.items()
                           if name != missing}
                self.assertEqual(self.client.post(
                    self.path, headers=headers, json=self.body).status_code,
                    expected)
        self.assertEqual(self.service.calls, [])
        for tag in ('W/"v0"', '"v0","v1"', "v0"):
            with self.subTest(tag=tag):
                self.assertEqual(self.client.post(
                    self.path, headers={**self.headers, "if-match": tag},
                    json=self.body).status_code, 400)

    def test_body_and_service_errors_are_bounded(self):
        for body in ({**self.body, "extra": True},
                     {"eligibility_state": "ELIGIBLE"},
                     {"eligibility_state": 1, "reason": "r"}):
            self.assertEqual(self.client.post(
                self.path, headers=self.headers, json=body).status_code, 400)
        self.assertEqual(self.service.calls, [])
        for code, status in (("CONFLICT_VERSION", 409),
                             ("CONFLICT_STATE", 409),
                             ("CONFLICT_IDEMPOTENCY", 409),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("RESOURCE_NOT_FOUND", 404)):
            self.service.failure = code
            with self.subTest(code=code):
                self.assertEqual(self.client.post(
                    self.path, headers=self.headers, json=self.body).status_code,
                    status)


if __name__ == "__main__":
    unittest.main()
