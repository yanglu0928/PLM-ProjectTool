from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.entrypoints.trace_requirement_owner import RequirementVersionTraceOwner
from plm_assistant.modules.requirement.application.read_versions import RequirementVersionReadError
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProof,
    TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class _Requirements:
    def __init__(self) -> None:
        self.calls = []
        self.error = None

    def get_version_for_trace(self, transaction, query, **kwargs):
        self.calls.append((transaction, query, kwargs))
        if self.error:
            raise RequirementVersionReadError(self.error)
        return object()


class RequirementTraceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.requirements = _Requirements()
        self.owner = RequirementVersionTraceOwner(self.requirements)
        self.project, self.requirement, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.ref = TraceVersionRef("requirement", "REQ-03", self.requirement,
                                   self.version, "PROJECT", self.project)
        self.public = TraceResourceVersionRef("REQ-03", self.requirement, self.version)
        self.query = TraceProofQuery(b"s" * 32, uuid.uuid4())
        self.tx = object()

    def test_resolve_and_prove_fixed_identity(self):
        self.assertEqual(self.owner.resolve(
            self.tx, self.query, self.project, self.public), self.ref)
        self.assertEqual(self.owner.prove(self.tx, self.query, self.ref),
                         TraceTargetProof(self.ref))
        self.assertTrue(all(call[0] is self.tx for call in self.requirements.calls))
        self.assertEqual(self.requirements.calls[0][1].project_id, self.project)
        self.assertEqual(self.requirements.calls[0][2]["requirement_version_id"],
                         self.version)

    def test_foreign_type_and_global_scope_fail_before_read(self):
        with self.assertRaises(TraceTargetProofError):
            self.owner.resolve(self.tx, self.query, self.project,
                               replace(self.public, resource_type="DOC-02"))
        with self.assertRaises(TraceTargetProofError):
            self.owner.prove(self.tx, self.query, TraceVersionRef(
                "document", "DOC-02", self.requirement, self.version,
                "GLOBAL", None))
        self.assertEqual(self.requirements.calls, [])

    def test_owner_errors_mask_auth_and_keep_license_explicit(self):
        for code, expected in (("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"),
                               ("RESOURCE_NOT_FOUND", "RESOURCE_NOT_FOUND"),
                               ("LICENSE_OPERATION_DENIED", "LICENSE_OPERATION_DENIED"),
                               ("REQUIREMENT_UNAVAILABLE", "TRACE_UNAVAILABLE")):
            self.requirements.error = code
            with self.subTest(code=code), self.assertRaises(TraceTargetProofError) as caught:
                self.owner.prove(self.tx, self.query, self.ref)
            self.assertEqual(caught.exception.code, expected)


if __name__ == "__main__":
    unittest.main()
