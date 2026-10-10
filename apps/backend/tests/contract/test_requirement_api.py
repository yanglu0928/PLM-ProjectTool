from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.requirement.api.requirement_cursor import RequirementCursorCodec
from plm_assistant.modules.requirement.api.requirements import create_requirement_router
from plm_assistant.modules.requirement.application.create_identity import (
    RequirementIdentityCreateError, RequirementInitialView,
)
from plm_assistant.modules.requirement.application.mutate_requirement import (
    RequirementIdentityView, RequirementMutationError,
)
from plm_assistant.modules.requirement.application.read_identities import (
    RequirementIdentityReadError, RequirementPage, RequirementSummary,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, REQUIREMENT, ACTOR, EVIDENCE = (
    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
SUMMARY = RequirementSummary(
    REQUIREMENT, PROJECT, "REQ-001", "ACTIVE", None,
    ACTOR, NOW, None, NOW, '"v0"')


class Sessions:
    def validate(self, token, *, csrf_token=None, require_csrf=False):
        if (token != b"s" * 32 or require_csrf and csrf_token != b"c" * 32):
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    fail = None

    def _check(self, query):
        self.query = query
        if self.fail:
            raise RequirementIdentityReadError(self.fail)

    def list_requirements(self, query, *, page_size, after_updated_at=None,
                          after_requirement_id=None):
        self._check(query)
        self.after = (after_updated_at, after_requirement_id)
        more = after_updated_at is None
        return RequirementPage(
            (SUMMARY,), NOW if more else None, REQUIREMENT if more else None, more)

    def get_requirement(self, query, requirement_id):
        self._check(query)
        return SUMMARY


class Creates:
    fail = None

    def create_requirement(self, command):
        self.command = command
        if self.fail:
            raise RequirementIdentityCreateError(self.fail)
        return RequirementInitialView(
            REQUIREMENT, PROJECT, command.requirement_code, NOW)


class Mutations:
    fail = None

    def _result(self, command, operation):
        self.command, self.operation = command, operation
        if self.fail:
            raise RequirementMutationError(self.fail)
        state = {"DEFER": "DEFERRED", "REJECT": "REJECTED",
                 "ARCHIVE": "ARCHIVED"}.get(operation, "ACTIVE")
        decision = operation in {"DEFER", "REJECT"}
        return RequirementIdentityView(
            REQUIREMENT, PROJECT,
            getattr(command, "requirement_code", "REQ-001"), state,
            uuid.uuid4() if decision else None,
            command.reason if decision else None,
            command.impact if decision else None,
            command.evidence_ids if decision else (),
            f'"v{command.expected_version + 1}"')

    def patch(self, command):
        return self._result(command, "PATCH")

    def defer(self, command):
        return self._result(command, "DEFER")

    def reject(self, command):
        return self._result(command, "REJECT")

    def archive(self, command):
        return self._result(command, "ARCHIVE")


class RequirementApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates, self.mutations = Reads(), Creates(), Mutations()
        self.reads.fail = self.creates.fail = self.mutations.fail = None
        router = create_requirement_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, creates=self.creates, mutations=self.mutations,
            cursors=RequirementCursorCodec(b"r" * 32))
        self.client = TestClient(
            create_app(requirement_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = f"/api/v1/projects/{PROJECT}/requirements"
        self.detail = f"{self.root}/{REQUIREMENT}"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers, "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
        }
        self.decision = {
            "reason": "Customer decision", "impact": "Schedule impact",
            "evidence_ids": [str(EVIDENCE)],
        }

    def test_default_closed_and_seven_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for method, path in (
                ("get", self.root), ("post", self.root),
                ("get", self.detail), ("patch", self.detail),
                ("post", self.detail + ":defer"),
                ("post", self.detail + ":reject"),
                ("post", self.detail + ":archive"),
            ):
                self.assertEqual(404, getattr(bare, method)(path).status_code)

        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers)
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers)
        self.assertEqual((NOW, REQUIREMENT), self.reads.after)
        self.assertFalse(second.json()["data"]["has_more"])

        created = self.client.post(
            self.root, headers=self.write_headers,
            json={"requirement_code": "REQ-001"})
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v0"', created.headers["etag"])
        self.assertEqual(self.detail, created.headers["location"])

        detail = self.client.get(self.detail, headers=self.read_headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual('"v0"', detail.headers["etag"])
        self.assertIsNone(detail.json()["data"]["current_approved_version_ref"])

        patch_headers = {key: value for key, value in self.write_headers.items()
                         if key != "idempotency-key"}
        patched = self.client.patch(
            self.detail, headers=patch_headers,
            json={"requirement_code": "REQ-002"})
        self.assertEqual(200, patched.status_code)
        self.assertEqual("REQ-002", self.mutations.command.requirement_code)
        self.assertFalse(hasattr(self.mutations.command, "idempotency_key"))

        for suffix, operation in ((":defer", "DEFER"), (":reject", "REJECT")):
            response = self.client.post(
                self.detail + suffix, headers=self.write_headers,
                json=self.decision)
            self.assertEqual(200, response.status_code)
            self.assertEqual(operation, self.mutations.operation)
            self.assertEqual([str(EVIDENCE)], response.json()["data"]["evidence_refs"])

        archived = self.client.post(
            self.detail + ":archive", headers=self.write_headers)
        self.assertEqual(200, archived.status_code)
        self.assertEqual("ARCHIVED", archived.json()["data"]["state"])

    def test_security_json_and_preconditions_fail_closed(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.get(
            self.root, headers={**self.read_headers, "host": "evil.test"}
        ).status_code)
        self.assertEqual(403, self.client.post(
            self.root, headers={**self.write_headers,
                                "origin": "https://evil.test"},
            json={"requirement_code": "REQ-001"}).status_code)
        no_match = {key: value for key, value in self.write_headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.patch(
            self.detail, headers=no_match,
            json={"requirement_code": "REQ-002"}).status_code)
        no_key = {key: value for key, value in self.write_headers.items()
                  if key != "idempotency-key"}
        self.assertEqual(422, self.client.post(
            self.detail + ":defer", headers=no_key, json=self.decision).status_code)
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1",
            headers=self.read_headers).status_code)
        self.assertEqual(400, self.client.get(
            self.detail + "?extra=1", headers=self.read_headers).status_code)
        self.assertEqual(400, self.client.post(
            self.detail + ":archive", headers=self.write_headers,
            content=b"{}").status_code)
        self.assertEqual(400, self.client.post(
            self.detail + ":defer", headers=self.write_headers,
            json={"reason": "R", "impact": "I"}).status_code)
        duplicate = b'{"requirement_code":"A","requirement_code":"B"}'
        self.assertEqual(400, self.client.post(
            self.root, headers={**self.write_headers,
                                "content-type": "application/json"},
            content=duplicate).status_code)

    def test_cursor_scope_and_output_shape_fail_closed(self):
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers)
        cursor = first.json()["data"]["next_cursor"]
        self.assertEqual(400, self.client.get(
            f"/api/v1/projects/{uuid.uuid4()}/requirements"
            f"?page_size=1&cursor={cursor}", headers=self.read_headers).status_code)
        original = self.reads.list_requirements
        self.reads.list_requirements = lambda *_a, **_k: RequirementPage(
            (SUMMARY,), None, None, True)
        self.assertEqual(503, self.client.get(
            self.root, headers=self.read_headers).status_code)
        self.reads.list_requirements = original

    def test_safe_error_mapping(self):
        for owner, code, method, status in (
            (self.reads, "AUTH_ACCESS_DENIED", "get", 404),
            (self.reads, "LICENSE_OPERATION_DENIED", "get", 403),
            (self.creates, "CONFLICT_IDEMPOTENCY", "post", 409),
            (self.mutations, "CONFLICT_VERSION", "patch", 409),
            (self.mutations, "REQUIREMENT_DECISION_INVALID", "defer", 422),
            (self.mutations, "REQUIREMENT_STATE_INVALID", "archive", 409),
        ):
            with self.subTest(code=code):
                owner.fail = code
                if method == "get":
                    response = self.client.get(self.root, headers=self.read_headers)
                elif method == "post":
                    response = self.client.post(
                        self.root, headers=self.write_headers,
                        json={"requirement_code": "REQ-001"})
                elif method == "patch":
                    response = self.client.patch(
                        self.detail, headers=self.write_headers,
                        json={"requirement_code": "REQ-002"})
                elif method == "defer":
                    response = self.client.post(
                        self.detail + ":defer", headers=self.write_headers,
                        json=self.decision)
                else:
                    response = self.client.post(
                        self.detail + ":archive", headers=self.write_headers)
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
                owner.fail = None


if __name__ == "__main__":
    unittest.main()
