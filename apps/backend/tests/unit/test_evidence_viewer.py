from __future__ import annotations

import hashlib
import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.document.application.read_documents import DocumentVersionView
from plm_assistant.modules.evidence.application.document_source_proof import EvidenceDocumentProof
from plm_assistant.modules.evidence.application.parsed_node_proof import EvidenceParsedNodeProof
from plm_assistant.modules.evidence.application.read_evidence import (
    EvidenceReadError, EvidenceReadQuery, EvidenceView,
)
from plm_assistant.modules.evidence.application.view_evidence import (
    EvidenceViewerError, EvidenceViewerService,
)


class Evidence:
    def __init__(self, view):
        self.result = view

    def get(self, _query, _id):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Versions:
    def __init__(self, version):
        self.result = version

    def get_version(self, *_args):
        return self.result


class DocumentProof:
    def __init__(self, proof):
        self.result = proof
        self.calls = 0

    def prove(self, *_args, **_kwargs):
        self.calls += 1
        return self.result


class NodeProof(DocumentProof):
    pass


class EvidenceViewerTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.document = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.evidence_id = uuid.uuid4()
        self.record = uuid.uuid4()
        self.digest = hashlib.sha256(b"source").digest()
        self.query = EvidenceReadQuery(b"s" * 32, uuid.uuid4(), "PROJECT", self.project)
        self.view = EvidenceView(
            self.evidence_id, "PROJECT", self.project, self.document,
            self.version_id, {"locator_type": "DOCUMENT"}, self.digest,
            "Whole file", "short", "CANDIDATE", datetime.now(timezone.utc), '"v0"',
        )
        self.version = DocumentVersionView(
            self.version_id, self.document, 1, self.digest.hex(), 6,
            "text/plain", "AVAILABLE", None, datetime.now(timezone.utc), None,
        )
        self.document_proof = DocumentProof(EvidenceDocumentProof(
            self.version_id, {"locator_type": "DOCUMENT"}, self.digest,
        ))
        self.node_proof = NodeProof(None)
        self.evidence = Evidence(self.view)
        self.versions = Versions(self.version)
        self.service = EvidenceViewerService(
            evidence=self.evidence, versions=self.versions,
            document_proof=self.document_proof, node_proof=self.node_proof,
        )

    def error(self, code):
        with self.assertRaises(EvidenceViewerError) as caught:
            self.service.view(self.query, self.evidence_id)
        self.assertEqual(caught.exception.code, code)

    def test_whole_document_fixed_descriptor(self):
        result = self.service.view(self.query, self.evidence_id)
        self.assertEqual(result.document_version_id, self.version_id)
        self.assertEqual(result.precision, "DOCUMENT")
        self.assertEqual(result.short_preview, "short")
        self.assertFalse(hasattr(result, "storage_locator"))
        self.assertEqual(self.node_proof.calls, 0)

    def test_parse_provenance_and_fingerprint(self):
        locator = {"locator_type": "PAGE", "page_no": 2}
        self.evidence.result = replace(self.view, locator=locator,
                                       source_parse_record_id=self.record)
        self.node_proof.result = EvidenceParsedNodeProof(
            self.version_id, self.record, "n1", locator, self.digest,
            source_sha256=self.digest,
        )
        result = self.service.view(self.query, self.evidence_id)
        self.assertEqual(result.locator, locator)
        self.assertEqual(result.precision, "PARSED_NODE")
        self.assertEqual(self.document_proof.calls, 0)
        self.evidence.result = replace(self.evidence.result, source_parse_record_id=None)
        self.error("EVIDENCE_RESOLUTION_UNAVAILABLE")
        self.assertEqual(self.node_proof.calls, 1)
        self.evidence.result = replace(self.evidence.result, source_parse_record_id=self.record)
        self.node_proof.result = replace(self.node_proof.result,
                                         content_fingerprint=b"x" * 32)
        self.error("EVIDENCE_FINGERPRINT_MISMATCH")
        self.node_proof.result = replace(self.node_proof.result,
                                         content_fingerprint=self.digest,
                                         source_sha256=b"y" * 32)
        self.error("EVIDENCE_FINGERPRINT_MISMATCH")

    def test_embedded_structured_record_is_fixed(self):
        locator = {"locator_type": "STRUCTURED_NODE",
                   "parse_record_id": str(self.record), "node_id": "n1",
                   "source_locator": {"locator_type": "PAGE", "page_no": 1}}
        self.evidence.result = replace(self.view, locator=locator)
        self.node_proof.result = EvidenceParsedNodeProof(
            self.version_id, self.record, "n1", locator, self.digest,
            source_sha256=self.digest,
        )
        self.assertEqual(self.service.view(self.query, self.evidence_id).precision,
                         "PARSED_NODE")
        self.evidence.result = replace(self.evidence.result,
                                       source_parse_record_id=uuid.uuid4())
        self.error("EVIDENCE_RESOLUTION_UNAVAILABLE")

    def test_revocation_and_authorization_close_view(self):
        self.versions.result = replace(self.version, availability_state="REVOKED")
        self.error("EVIDENCE_RESOLUTION_UNAVAILABLE")
        self.assertEqual(self.document_proof.calls, 0)
        self.versions.result = self.version
        self.evidence.result = EvidenceReadError("RESOURCE_NOT_FOUND")
        self.error("RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
