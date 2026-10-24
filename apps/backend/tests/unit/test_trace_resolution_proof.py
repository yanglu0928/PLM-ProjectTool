from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.trace.application.resolution_proof import (
    TraceResolutionProofError, TraceResolutionProofService,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceTargetProof, TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class Repository:
    def __init__(self, edge):
        self.edge = edge

    def active_project_edge(self, transaction, *, project_id, trace_link_id):
        return self.edge


class Owner:
    def prove(self, transaction, query, ref):
        return TraceTargetProof(ref)


class TraceResolutionProofTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.analysis = uuid.uuid4()
        self.version = uuid.uuid4()
        self.link = uuid.uuid4()
        self.source = TraceVersionRef(
            "handover", "HND-02", self.analysis, self.version,
            "PROJECT", self.project,
        )
        self.target = TraceVersionRef(
            "requirement", "REQ-03", uuid.uuid4(), uuid.uuid4(),
            "PROJECT", self.project,
        )
        self.edge = TraceEdgeShape(self.source, self.target, "REFINES")
        owner = Owner()
        self.service = TraceResolutionProofService(
            Repository(self.edge), TraceTargetProofService({
                ("handover", "HND-02"): owner,
                ("requirement", "REQ-03"): owner,
            }),
        )

    def prove(self, **changes):
        values = dict(
            transaction=object(), session_token=b"s" * 32,
            trace_id=uuid.uuid4(), project_id=self.project,
            trace_link_id=self.link, source_kind="ANALYSIS_ITEM",
            source_analysis_id=self.analysis,
            source_analysis_version_id=self.version, reason="Resolved",
        )
        values.update(changes)
        return self.service.prove(**values)

    def test_analysis_source_requires_exact_fixed_version(self):
        self.assertEqual(self.link, self.prove().trace_link_id)
        with self.assertRaises(TraceResolutionProofError):
            self.prove(source_analysis_version_id=uuid.uuid4())

    def test_human_source_requires_formal_downstream_target(self):
        proof = self.prove(
            source_kind="HUMAN", source_analysis_id=None,
            source_analysis_version_id=None,
        )
        self.assertEqual(self.target, proof.edge.target)
        self.service._repository.edge = replace(
            self.edge,
            target=TraceVersionRef(
                "document", "DOC-02", uuid.uuid4(), uuid.uuid4(),
                "PROJECT", self.project,
            ),
        )
        with self.assertRaises(TraceResolutionProofError):
            self.prove(source_kind="HUMAN", source_analysis_id=None,
                       source_analysis_version_id=None)

    def test_missing_or_unproved_link_fails_closed(self):
        self.service._repository.edge = None
        with self.assertRaises(TraceResolutionProofError):
            self.prove()


if __name__ == "__main__":
    unittest.main()
