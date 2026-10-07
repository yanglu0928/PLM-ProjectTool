from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.requirement.api.version_cursor import RequirementVersionCursorCodec
from plm_assistant.modules.requirement.api.versions import create_requirement_version_router
from plm_assistant.modules.requirement.application.create_version import (
    CreatedRequirementVersion, RequirementVersionCreateError,
)
from plm_assistant.modules.requirement.application.read_versions import (
    RequirementAcceptanceView, RequirementSourceEvidenceView,
    RequirementSourceView, RequirementVersionPage, RequirementVersionReadError,
    RequirementVersionSummary, RequirementVersionView,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionValidationError, RequirementVersionValidationReport,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)
PROJECT, REQUIREMENT, VERSION, ACTOR, EVIDENCE = (
    uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
SUMMARY = RequirementVersionSummary(
    VERSION, REQUIREMENT, PROJECT, 2, "DRAFT", "Export package", "OUTPUT",
    "HIGH", "MEDIUM", "PENDING_CONFIRMATION", "ab" * 32,
    1, 1, 0, 0, 0, 0, 0, None, None, None, ACTOR, NOW)
DETAIL = RequirementVersionView(
    SUMMARY, "The system exports a package.", "Controlled delivery.",
    (RequirementSourceView(
        0, "PROJECT_EVIDENCE", EVIDENCE, None,
        (RequirementSourceEvidenceView(EVIDENCE, 0),)),),
    (RequirementAcceptanceView(
        0, "Package exists", "Run validation", "Project data",
        "Windows 11", "Signed report"),),
    (), (), (), (), ())


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
            raise RequirementVersionReadError(self.fail)

    def list_versions(self, query, *, requirement_id, page_size,
                      after_version_no=None):
        self._check(query)
        self.after = after_version_no
        more = after_version_no is None
        return RequirementVersionPage((SUMMARY,), 2 if more else None, more)

    def get_version(self, query, *, requirement_id, requirement_version_id):
        self._check(query)
        return DETAIL


class Creates:
    fail = None

    def create(self, command):
        self.command = command
        if self.fail:
            raise RequirementVersionCreateError(self.fail)
        return CreatedRequirementVersion(
            VERSION, REQUIREMENT, PROJECT, 1, "DRAFT",
            b"f" * 32, None, ACTOR, NOW,
            command.expected_lock_version, command.expected_lock_version + 1)


class Validations:
    fail = None
    result_trace = None

    def validate(self, command):
        self.command = command
        if self.fail:
            raise RequirementVersionValidationError(self.fail)
        return RequirementVersionValidationReport(
            uuid.uuid4(), self.result_trace or command.trace_id,
            REQUIREMENT, VERSION, PROJECT,
            1, "DRAFT", "PENDING_CONFIRMATION", 1, 1, 0, 0, 0, 0, 1,
            False, ("PENDING_CONFIRMATION",), NOW)


class RequirementVersionApiTests(unittest.TestCase):
    def setUp(self):
        self.reads, self.creates, self.validations = Reads(), Creates(), Validations()
        self.reads.fail = self.creates.fail = self.validations.fail = None
        self.validations.result_trace = None
        router = create_requirement_version_router(
            sessions=Sessions(),
            origins=LoginOriginPolicy(["https://plm.example.test"]),
            reads=self.reads, creates=self.creates,
            validations=self.validations,
            cursors=RequirementVersionCursorCodec(b"v" * 32))
        self.client = TestClient(
            create_app(requirement_version_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)
        self.root = (
            f"/api/v1/projects/{PROJECT}/requirements/{REQUIREMENT}/versions")
        self.detail = f"{self.root}/{VERSION}"
        self.read_headers = {"cookie": "plm_session=" + (b"s" * 32).hex()}
        self.write_headers = {
            **self.read_headers, "origin": "https://plm.example.test",
            "x-csrf-token": (b"c" * 32).hex(),
            "idempotency-key": str(uuid.uuid4()), "if-match": '"v0"',
        }
        self.body = {
            "initial": True, "base_version_ref": None,
            "title": "Export package",
            "statement": "The system exports a package.",
            "rationale": "Controlled delivery.", "domain_name": "OUTPUT",
            "priority": "HIGH", "risk": "MEDIUM",
            "classification": "PENDING_CONFIRMATION",
            "sources": [{
                "source_type": "PROJECT_EVIDENCE",
                "source_object_id": str(EVIDENCE),
                "source_version_ref": None,
                "evidence_refs": [str(EVIDENCE)],
            }],
            "acceptance_criteria": [], "capability_assessments": [],
            "assumptions": [], "exclusions": [], "dependencies": [],
            "ai_task_refs": [], "client_reason": "Create draft",
        }

    def test_default_closed_and_four_success_contracts(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            for method, path in (
                ("get", self.root), ("post", self.root),
                ("get", self.detail), ("post", self.detail + ":validate"),
            ):
                self.assertEqual(404, getattr(bare, method)(path).status_code)

        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers)
        self.assertEqual(200, first.status_code)
        cursor = first.json()["data"]["next_cursor"]
        second = self.client.get(
            self.root + f"?page_size=1&cursor={cursor}",
            headers=self.read_headers)
        self.assertEqual(2, self.reads.after)
        self.assertFalse(second.json()["data"]["has_more"])

        created = self.client.post(
            self.root, headers=self.write_headers, json=self.body)
        self.assertEqual(201, created.status_code)
        self.assertEqual('"v1"', created.headers["etag"])
        self.assertEqual(self.detail, created.headers["location"])
        self.assertEqual((), self.creates.command.ai_task_refs)

        detail = self.client.get(self.detail, headers=self.read_headers)
        self.assertEqual(200, detail.status_code)
        self.assertEqual("PROJECT_EVIDENCE",
                         detail.json()["data"]["sources"][0]["source_type"])
        self.assertEqual("Package exists", detail.json()["data"]
                         ["acceptance_criteria"][0]["observable_result"])

        validate_headers = {key: value for key, value in self.write_headers.items()
                            if key != "if-match"}
        validated = self.client.post(
            self.detail + ":validate", headers=validate_headers)
        self.assertEqual(200, validated.status_code)
        self.assertFalse(validated.json()["data"]["valid"])
        self.assertEqual(["PENDING_CONFIRMATION"],
                         validated.json()["data"]["blocking_issues"])
        self.validations.result_trace = uuid.uuid4()
        replayed = self.client.post(
            self.detail + ":validate", headers=validate_headers)
        self.assertEqual(200, replayed.status_code)
        self.assertNotEqual(validated.json()["trace_id"],
                            replayed.json()["trace_id"])

    def test_security_json_and_preconditions_fail_closed(self):
        self.assertEqual(401, self.client.get(self.root).status_code)
        self.assertEqual(403, self.client.get(
            self.root, headers={**self.read_headers, "host": "evil.test"}
        ).status_code)
        no_match = {key: value for key, value in self.write_headers.items()
                    if key != "if-match"}
        self.assertEqual(428, self.client.post(
            self.root, headers=no_match, json=self.body).status_code)
        no_key = {key: value for key, value in self.write_headers.items()
                  if key not in {"idempotency-key", "if-match"}}
        self.assertEqual(422, self.client.post(
            self.detail + ":validate", headers=no_key).status_code)
        self.assertEqual(400, self.client.post(
            self.detail + ":validate", headers={
                **no_match, "idempotency-key": str(uuid.uuid4())},
            content=b"{}").status_code)
        malformed = dict(self.body)
        malformed["sources"] = [{"source_type": "PROJECT_EVIDENCE"}]
        self.assertEqual(400, self.client.post(
            self.root, headers=self.write_headers, json=malformed).status_code)
        self.assertEqual(400, self.client.get(
            self.root + "?page_size=1&page_size=1",
            headers=self.read_headers).status_code)
        duplicate = b'{"initial":true,"initial":false}'
        self.assertEqual(400, self.client.post(
            self.root, headers={**self.write_headers,
                                "content-type": "application/json"},
            content=duplicate).status_code)

    def test_cursor_scope_and_output_shape_fail_closed(self):
        first = self.client.get(
            self.root + "?page_size=1", headers=self.read_headers)
        cursor = first.json()["data"]["next_cursor"]
        other = (
            f"/api/v1/projects/{PROJECT}/requirements/{uuid.uuid4()}/versions"
            f"?page_size=1&cursor={cursor}")
        self.assertEqual(400, self.client.get(
            other, headers=self.read_headers).status_code)
        original = self.reads.list_versions
        self.reads.list_versions = lambda *_a, **_k: RequirementVersionPage(
            (SUMMARY,), None, True)
        self.assertEqual(503, self.client.get(
            self.root, headers=self.read_headers).status_code)
        self.reads.list_versions = original

    def test_safe_error_mapping(self):
        for owner, code, method, status in (
            (self.reads, "AUTH_ACCESS_DENIED", "get", 404),
            (self.reads, "LICENSE_OPERATION_DENIED", "get", 403),
            (self.creates, "CONFLICT_VERSION", "create", 409),
            (self.creates, "REQUIREMENT_SOURCE_UNAVAILABLE", "create", 422),
            (self.validations, "CONFLICT_IDEMPOTENCY", "validate", 409),
        ):
            with self.subTest(code=code):
                owner.fail = code
                if method == "get":
                    response = self.client.get(self.root, headers=self.read_headers)
                elif method == "create":
                    response = self.client.post(
                        self.root, headers=self.write_headers, json=self.body)
                else:
                    response = self.client.post(
                        self.detail + ":validate",
                        headers={key: value for key, value in self.write_headers.items()
                                 if key != "if-match"})
                self.assertEqual(status, response.status_code)
                self.assertNotIn("Traceback", response.text)
                owner.fail = None


if __name__ == "__main__":
    unittest.main()
