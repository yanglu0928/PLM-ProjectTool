from __future__ import annotations

import unittest
import uuid

from plm_assistant.modules.trace.application.implements_coverage import (
    TraceImplementsCoverageError, TraceImplementsCoverageService,
)
from plm_assistant.modules.trace.application.query_one_hop import TraceAdjacency
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceTargetProof, TraceTargetProofError,
    TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class Repository:
    def __init__(self):
        self.rows = ()
        self.calls = []
        self.fail = False

    def active_for_section(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        if self.fail:
            raise RuntimeError("database unavailable")
        return self.rows


class Owner:
    def __init__(self):
        self.calls = []
        self.deny = None

    def prove(self, transaction, query, ref):
        self.calls.append(ref)
        if self.deny == ref:
            raise TraceTargetProofError("RESOURCE_NOT_FOUND")
        return TraceTargetProof(ref)


class TraceImplementsCoverageTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.section = TraceVersionRef("solution", "SOL-05", uuid.uuid4(),
                                       uuid.uuid4(), "PROJECT", self.project)
        self.req1 = TraceVersionRef("requirement", "REQ-03", uuid.uuid4(),
                                    uuid.uuid4(), "PROJECT", self.project)
        self.req2 = TraceVersionRef("requirement", "REQ-03", uuid.uuid4(),
                                    uuid.uuid4(), "PROJECT", self.project)
        self.repository, self.owner = Repository(), Owner()
        self.service = TraceImplementsCoverageService(
            repository=self.repository,
            owners=TraceTargetProofService({
                ("requirement", "REQ-03"): self.owner,
                ("solution", "SOL-05"): self.owner,
            }),
        )
        self.query = TraceProofQuery(b"s" * 32, uuid.uuid4())
        self.transaction = object()

    def row(self, source=None, target=None, relation="IMPLEMENTS"):
        return TraceAdjacency(uuid.uuid4(), TraceEdgeShape(
            source or self.req1, target or self.section, relation))

    def prove(self, expected=None):
        return self.service.prove(
            self.transaction, query=self.query, section=self.section,
            requirement_refs=(self.req1, self.req2) if expected is None else expected,
        )

    def denied(self, expected=None, code="TRACE_COVERAGE_REQUIRED"):
        with self.assertRaises(TraceImplementsCoverageError) as caught:
            self.prove(expected)
        self.assertEqual(caught.exception.code, code)

    def test_exact_current_set_reproves_all_endpoints(self):
        rows = (self.row(self.req2), self.row(self.req1))
        self.repository.rows = rows
        proof = self.prove()
        self.assertEqual(proof.section, self.section)
        self.assertEqual(proof.trace_link_ids,
                         tuple(row.trace_link_id for row in rows))
        self.assertEqual(self.repository.calls[0][1]["limit"], 501)
        self.assertIs(self.repository.calls[0][0], self.transaction)
        self.assertEqual(self.owner.calls.count(self.section), 3)
        self.assertEqual(self.owner.calls.count(self.req1), 1)
        self.assertEqual(self.owner.calls.count(self.req2), 1)

    def test_missing_extra_or_old_version_fails(self):
        self.repository.rows = (self.row(self.req1),)
        self.denied()
        self.repository.rows = (self.row(self.req1), self.row(self.req2),
                                self.row(TraceVersionRef(
                                    "requirement", "REQ-03", uuid.uuid4(),
                                    uuid.uuid4(), "PROJECT", self.project)))
        self.denied()
        old = TraceVersionRef("requirement", "REQ-03", self.req1.object_id,
                              uuid.uuid4(), "PROJECT", self.project)
        self.repository.rows = (self.row(old), self.row(self.req2))
        self.denied()

    def test_revoke_or_supersede_removing_active_edge_fails(self):
        self.repository.rows = (self.row(self.req1), self.row(self.req2))
        self.prove()
        self.repository.rows = (self.repository.rows[0],)
        self.denied()

    def test_wrong_relation_target_and_duplicate_fail(self):
        self.repository.rows = (self.row(self.req1, relation="REFINES"),
                                self.row(self.req2))
        self.denied()
        self.repository.rows = (self.row(self.req1, target=TraceVersionRef(
            "solution", "SOL-05", self.section.object_id, uuid.uuid4(),
            "PROJECT", self.project)), self.row(self.req2))
        self.denied()
        self.repository.rows = (self.row(self.req1), self.row(self.req1))
        self.denied()

    def test_empty_duplicate_or_foreign_expected_fails_before_repository(self):
        self.denied(())
        self.denied((self.req1, self.req1))
        foreign = TraceVersionRef("requirement", "REQ-03", uuid.uuid4(),
                                  uuid.uuid4(), "PROJECT", uuid.uuid4())
        self.denied((foreign,))
        self.assertEqual(self.repository.calls, [])

    def test_owner_denial_and_database_failure_fail_closed(self):
        self.repository.rows = (self.row(self.req1), self.row(self.req2))
        self.owner.deny = self.req2
        self.denied()
        self.owner.deny = None
        self.repository.fail = True
        self.denied(code="TRACE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
