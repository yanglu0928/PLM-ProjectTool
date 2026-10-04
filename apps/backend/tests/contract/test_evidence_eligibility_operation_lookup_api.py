from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.evidence.api.lookup_eligibility_operation import (
    create_evidence_eligibility_operation_lookup_router,
)
from plm_assistant.modules.evidence.application.lookup_eligibility_operation import (
    EvidenceEligibilityLookupError, EvidenceEligibilityOperationStatus,
)


class _Sessions:
    def __init__(self, actor):
        self.actor = actor

    def validate(self, token, *, csrf_token, require_csrf):
        if token != b"s" * 32 or csrf_token != b"c" * 32 or require_csrf is not True:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return type("Principal", (), {"user_id": self.actor})()


class _Service:
    def __init__(self):
        self.calls = []
        self.result = None
        self.failure = None

    def lookup(self, query):
        self.calls.append(query)
        if self.failure:
            raise EvidenceEligibilityLookupError(self.failure)
        return self.result or EvidenceEligibilityOperationStatus(
            "COMPLETED", query.evidence_id, 200)


class EvidenceEligibilityOperationLookupApiTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.project, self.evidence = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        self.service = _Service()
        self.factory_calls = []

        def factory(token, csrf):
            self.factory_calls.append((token, csrf))
            return self.service

        router = create_evidence_eligibility_operation_lookup_router(
            sessions=_Sessions(self.actor),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            service_factory=factory,
        )
        self.client = TestClient(create_app(
            evidence_eligibility_operation_lookup_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.path = (f"/api/v1/projects/{self.project}/evidence/"
                     f"{self.evidence}:lookup-eligibility-operation")
        self.headers = {
            "origin": "https://plm.example.test",
            "cookie": "plm_session=" + (b"s" * 32).hex(),
            "x-csrf-token": (b"c" * 32).hex(),
        }
        self.body = {"operation_key": "k" * 16}

    def test_default_closed_and_project_completed_is_minimal(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(bare.post(self.path, headers=self.headers,
                                       json=self.body).status_code, 404)
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["data"], {"status": "COMPLETED",
            "evidence_id": str(self.evidence), "first_status_code": 200})
        self.assertNotIn("operation_key", response.text)
        self.assertNotIn("k" * 16, response.text)
        query = self.service.calls[-1]
        self.assertEqual((query.actor_id, query.project_id, query.scope,
                          query.evidence_id, query.operation_key),
                         (self.actor, self.project, "PROJECT", self.evidence, "k" * 16))
        self.assertEqual(self.factory_calls[-1], (b"s" * 32, b"c" * 32))

    def test_unconfirmed_and_global_do_not_expose_current_state(self):
        self.service.result = EvidenceEligibilityOperationStatus("UNCONFIRMED")
        response = self.client.post(self.path, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"status": "UNCONFIRMED"})
        response = self.client.post(
            f"/api/v1/global/evidence/{self.evidence}:lookup-eligibility-operation",
            headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.service.calls[-1].scope, self.service.calls[-1].project_id),
                         ("GLOBAL", None))

    def test_browser_and_body_boundaries_fail_before_service(self):
        for missing, status in (("origin", 403), ("cookie", 401),
                                ("x-csrf-token", 403)):
            with self.subTest(missing=missing):
                headers = {key: value for key, value in self.headers.items() if key != missing}
                self.assertEqual(self.client.post(self.path, headers=headers,
                                                  json=self.body).status_code, status)
        for body, status in (({"operation_key": "short"}, 422),
                             ({"operation_key": 3}, 422),
                             ({"operation_key": "k" * 16, "reason": "private"}, 400),
                             ({}, 400)):
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.path, headers=self.headers,
                                                  json=body).status_code, status)
        self.assertEqual(self.client.post(self.path + "?operation_key=hidden",
                                          headers=self.headers, json=self.body).status_code, 400)
        self.assertEqual(self.service.calls, [])

    def test_service_errors_and_bad_result_are_safe(self):
        for code, status in (("AUTH_ACCESS_DENIED", 401), ("RESOURCE_NOT_FOUND", 404),
                             ("CONFLICT_IDEMPOTENCY", 409),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("SYSTEM_UNAVAILABLE", 503)):
            self.service.failure = code
            with self.subTest(code=code):
                response = self.client.post(self.path, headers=self.headers, json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertNotIn("k" * 16, response.text)
        self.service.failure = None
        self.service.result = EvidenceEligibilityOperationStatus("COMPLETED", uuid.uuid4(), 200)
        self.assertEqual(self.client.post(self.path, headers=self.headers,
                                          json=self.body).status_code, 503)


if __name__ == "__main__":
    unittest.main()
