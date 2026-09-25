from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.entrypoints.trace_document_owner import DocumentVersionTraceOwner
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadError, DocumentVersionView,
)
from plm_assistant.modules.trace.application.target_proof import (
    TraceProofQuery, TraceTargetProof, TraceTargetProofError,
    TraceTargetProofService,
)
from plm_assistant.modules.trace.domain.link_shape import TraceEdgeShape, TraceVersionRef


class _Owner:
    def __init__(self, forged=False) -> None:
        self.forged = forged
        self.calls = 0

    def prove(self, query, ref):
        self.calls += 1
        return TraceTargetProof(replace(ref, version_id=uuid.uuid4())
                                if self.forged else ref)


class _Documents:
    def __init__(self) -> None:
        self.calls = []
        self.error = None
        self.mismatch = False

    def get_version(self, query, document_id, version_id):
        self.calls.append((query, document_id, version_id))
        if self.error:
            raise DocumentReadError(self.error)
        return DocumentVersionView(
            uuid.uuid4() if self.mismatch else version_id,
            document_id, 1, "a" * 64, 1, "application/pdf", "AVAILABLE",
            None, datetime.now(timezone.utc), None,
        )


class TraceTargetProofTests(unittest.TestCase):
    def setUp(self) -> None:
        project = uuid.uuid4()
        self.source = TraceVersionRef("document", "DOC-02", uuid.uuid4(),
                                      uuid.uuid4(), "PROJECT", project)
        self.target = TraceVersionRef("requirement", "REQ-03", uuid.uuid4(),
                                      uuid.uuid4(), "PROJECT", project)
        self.edge = TraceEdgeShape(self.source, self.target, "DERIVED_FROM")
        self.query = TraceProofQuery(b"s" * 32, uuid.uuid4())

    def test_unregistered_target_fails_closed(self) -> None:
        document = _Owner()
        service = TraceTargetProofService({("document", "DOC-02"): document})
        with self.assertRaises(TraceTargetProofError) as caught:
            service.prove_edge(self.query, self.edge)
        self.assertEqual(caught.exception.code, "RESOURCE_NOT_FOUND")
        self.assertEqual(document.calls, 1)

    def test_both_exact_proofs_required(self) -> None:
        document, requirement = _Owner(), _Owner()
        service = TraceTargetProofService({
            ("document", "DOC-02"): document,
            ("requirement", "REQ-03"): requirement,
        })
        proofs = service.prove_edge(self.query, self.edge)
        self.assertEqual(tuple(proof.ref for proof in proofs),
                         (self.source, self.target))
        requirement.forged = True
        with self.assertRaises(TraceTargetProofError) as caught:
            service.prove_edge(self.query, self.edge)
        self.assertEqual(caught.exception.code, "TRACE_UNAVAILABLE")

    def test_bad_query_does_not_call_owner(self) -> None:
        owner = _Owner()
        service = TraceTargetProofService({("document", "DOC-02"): owner})
        with self.assertRaises(TraceTargetProofError) as caught:
            service.prove_edge(replace(self.query, session_token=b"short"), self.edge)
        self.assertEqual(caught.exception.code, "VALIDATION_FAILED")
        self.assertEqual(owner.calls, 0)

    def test_document_bridge_uses_scoped_read_and_no_metadata_projection(self) -> None:
        documents = _Documents()
        bridge = DocumentVersionTraceOwner(documents)
        proof = bridge.prove(self.query, self.source)
        self.assertEqual(proof, TraceTargetProof(self.source))
        document_query, document_id, version_id = documents.calls[0]
        self.assertEqual((document_id, version_id),
                         (self.source.object_id, self.source.version_id))
        self.assertEqual((document_query.scope, document_query.project_id),
                         ("PROJECT", self.source.project_id))
        self.assertFalse(hasattr(proof, "storage_locator"))
        self.assertFalse(hasattr(proof, "content_sha256"))

    def test_document_bridge_hides_unauthorized_and_bad_version(self) -> None:
        documents = _Documents()
        bridge = DocumentVersionTraceOwner(documents)
        for code, expected in (("RESOURCE_NOT_FOUND", "RESOURCE_NOT_FOUND"),
                               ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND"),
                               ("LICENSE_OPERATION_DENIED", "LICENSE_OPERATION_DENIED"),
                               ("DOCUMENT_UNAVAILABLE", "TRACE_UNAVAILABLE")):
            documents.error = code
            with self.subTest(code=code), self.assertRaises(TraceTargetProofError) as caught:
                bridge.prove(self.query, self.source)
            self.assertEqual(caught.exception.code, expected)
        documents.error = None
        documents.mismatch = True
        with self.assertRaises(TraceTargetProofError) as caught:
            bridge.prove(self.query, self.source)
        self.assertEqual(caught.exception.code, "TRACE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
