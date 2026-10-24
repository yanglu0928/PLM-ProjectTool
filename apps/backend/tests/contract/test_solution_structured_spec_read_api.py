"""Frozen SOL_SPEC_GET default-closed HTTP detail contract."""

from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from plm_assistant.entrypoints.api import create_app
from plm_assistant.modules.auth.api.login_origin_policy import LoginOriginPolicy
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.solution.api.structured_spec_read import (
    create_structured_spec_read_router,
)
from plm_assistant.modules.solution.application.read_structured_spec import (
    StructuredSpecHistoryView, StructuredSpecReadError,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef,
)


PROJECT, SPEC, SERIES, ACTOR = (uuid.uuid4() for _ in range(4))
REQ, REQ_VERSION, SECTION, SECTION_VERSION, EVIDENCE = (
    uuid.uuid4() for _ in range(5))
VIEW = StructuredSpecHistoryView(
    SPEC, SERIES, PROJECT, "MIGRATION_SPEC", 1, "DRAFT",
    b"c" * 32, b'{"scope":"Parts"}', b"p" * 32,
    (SpecRequirementRef(REQ, REQ_VERSION),),
    (SpecSectionRef(SECTION, SECTION_VERSION),),
    (EVIDENCE,), (), None, None, None, ACTOR,
    datetime(2026, 10, 16, tzinfo=timezone.utc))


class Sessions:
    def validate(self, token):
        if token != b"s" * 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
        return object()


class Reads:
    error = None
    view = VIEW

    def get(self, query, spec_id):
        if self.error:
            raise StructuredSpecReadError(self.error)
        assert query.session_token == b"s" * 32
        assert query.project_id == PROJECT and spec_id == SPEC
        return self.view


class StructuredSpecReadApiTests(unittest.TestCase):
    def setUp(self):
        self.reads = Reads()
        self.path = f"/api/v1/projects/{PROJECT}/structured-solution-specs/{SPEC}"
        self.headers = {"cookie": "plm_session=" + (b"s" * 32).hex(),
                        "origin": "https://plm.example.test"}
        router = create_structured_spec_read_router(
            sessions=Sessions(), origins=LoginOriginPolicy(
                ["https://plm.example.test"]), reads=self.reads)
        self.client = TestClient(create_app(
            solution_structured_spec_read_router=router),
            base_url="https://plm.example.test")
        self.addCleanup(self.client.close)

    def test_default_closed_and_fixed_history_detail(self):
        with TestClient(create_app(), base_url="https://plm.example.test") as bare:
            self.assertEqual(404, bare.get(self.path, headers=self.headers).status_code)
        response = self.client.get(self.path, headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-store", response.headers["cache-control"])
        self.assertEqual(response.headers["x-trace-id"], response.json()["trace_id"])
        data = response.json()["data"]
        self.assertEqual((data["structured_solution_spec_id"], data["project_id"]),
                         (str(SPEC), str(PROJECT)))
        self.assertEqual((data["version_no"], data["version_state"]), (1, "DRAFT"))
        self.assertEqual(data["payload"], {"scope": "Parts"})
        self.assertEqual(data["requirement_refs"], [{
            "requirement_id": str(REQ), "requirement_version_id": str(REQ_VERSION)}])
        self.assertEqual(data["section_refs"], [{
            "solution_section_id": str(SECTION),
            "solution_section_version_id": str(SECTION_VERSION)}])
        self.assertEqual(data["evidence_ids"], [str(EVIDENCE)])
        self.assertEqual(data["created_at"], "2026-10-16T00:00:00Z")

    def test_session_host_query_and_path_rejection(self):
        self.assertEqual(401, self.client.get(self.path, headers={
            "origin": self.headers["origin"]}).status_code)
        self.assertEqual(400, self.client.get(self.path + "?unknown=1",
                                               headers=self.headers).status_code)
        self.assertEqual(404, self.client.get(self.path.replace(str(SPEC), "bad"),
                                              headers=self.headers).status_code)
        self.assertEqual(403, self.client.get(self.path, headers={
            **self.headers, "host": "untrusted.example.test"}).status_code)

    def test_authorization_license_and_corrupt_projection_fail_closed(self):
        for code, status in (("RESOURCE_NOT_FOUND", 404),
                             ("LICENSE_OPERATION_DENIED", 403),
                             ("AUTH_ACCESS_DENIED", 401),
                             ("SOLUTION_UNAVAILABLE", 503)):
            self.reads.error = code
            response = self.client.get(self.path, headers=self.headers)
            self.assertEqual(status, response.status_code, code)
            self.assertNotIn("Traceback", response.text)
        self.reads.error = None
        self.reads.view = replace(VIEW, project_id=uuid.uuid4())
        self.assertEqual(503, self.client.get(
            self.path, headers=self.headers).status_code)
