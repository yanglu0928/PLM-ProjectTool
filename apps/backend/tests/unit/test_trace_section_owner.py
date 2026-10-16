from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.entrypoints.trace_section_owner import SectionVersionTraceOwner
from plm_assistant.modules.solution.application.read_section_version import SectionVersionReadError
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceResourceVersionRef, TraceTargetProof,
    TraceTargetProofError,
)
from plm_assistant.modules.trace.domain.link_shape import TraceVersionRef


class _Sections:
    def __init__(self):
        self.calls = []
        self.error = None

    def get_for_trace(self, transaction, query, version_id):
        self.calls.append((transaction, query, version_id))
        if self.error:
            raise SectionVersionReadError(self.error)
        return object()


class SectionTraceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.sections = _Sections()
        self.owner = SectionVersionTraceOwner(self.sections)
        self.project, self.section, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.ref = TraceVersionRef("solution", "SOL-05", self.section,
                                   self.version, "PROJECT", self.project)
        self.public = TraceResourceVersionRef("SOL-05", self.section, self.version)
        self.query = TraceProofQuery(b"s" * 32, uuid.uuid4())
        self.transaction = object()

    def test_resolve_and_prove_fixed_section_version(self):
        self.assertEqual(self.owner.resolve(
            self.transaction, self.query, self.project, self.public), self.ref)
        self.assertEqual(self.owner.prove(
            self.transaction, self.query, self.ref), TraceTargetProof(self.ref))
        self.assertTrue(all(call[0] is self.transaction for call in self.sections.calls))
        self.assertEqual(self.sections.calls[0][1].solution_section_id, self.section)
        self.assertEqual(self.sections.calls[0][2], self.version)

    def test_wrong_type_is_not_queried(self):
        with self.assertRaises(TraceTargetProofError):
            self.owner.resolve(self.transaction, self.query, self.project,
                               replace(self.public, resource_type="REQ-03"))
        with self.assertRaises(TraceTargetProofError):
            self.owner.prove(self.transaction, self.query, TraceVersionRef(
                "document", "DOC-02", self.section, self.version, "GLOBAL", None))
        self.assertEqual(self.sections.calls, [])

    def test_error_mapping_does_not_enumerate_unauthorized_target(self):
        for code, expected in (("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"),
                               ("RESOURCE_NOT_FOUND", "RESOURCE_NOT_FOUND"),
                               ("LICENSE_OPERATION_DENIED", "LICENSE_OPERATION_DENIED"),
                               ("SOLUTION_UNAVAILABLE", "TRACE_UNAVAILABLE")):
            self.sections.error = code
            with self.subTest(code=code), self.assertRaises(TraceTargetProofError) as caught:
                self.owner.prove(self.transaction, self.query, self.ref)
            self.assertEqual(caught.exception.code, expected)


if __name__ == "__main__":
    unittest.main()
