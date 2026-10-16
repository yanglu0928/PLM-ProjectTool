from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProof,
)
from plm_assistant.modules.document.application.read_parse_result import VerifiedParseResult
from plm_assistant.modules.evidence.application.fixed_source_record import LockedEvidenceSource
from plm_assistant.modules.evidence.application.parsed_node_proof import EvidenceParsedNodeProof
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import (
    ReferenceUseEvidenceError, ReferenceUseEvidenceProofService,
)


class ReferenceUseEvidenceProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.evidence_id = uuid.uuid4()
        self.version = uuid.uuid4()
        self.digest = b"d" * 32
        self.source = LockedEvidenceSource(
            self.evidence_id, "PROJECT", self.project, uuid.uuid4(),
            self.version, None, {"locator_type": "DOCUMENT"}, self.digest, 1)
        self.evidence = Mock()
        self.evidence.get_for_trace.return_value = self.source
        self.documents = Mock()
        self.documents.prove.return_value = ReferenceUseDocumentProof(
            self.version, "PROJECT", self.project, self.digest)
        self.parses = Mock()
        self.service = ReferenceUseEvidenceProofService(
            evidence=self.evidence, documents=self.documents, parses=self.parses)
        self.tx = object()

    def prove(self):
        return self.service.prove(
            self.tx, scope="PROJECT", project_id=self.project,
            evidence_id=self.evidence_id)

    def test_document_locator_matches_current_verified_document(self) -> None:
        proof = self.prove()
        self.assertEqual(proof.content_fingerprint, self.digest)
        self.assertEqual(proof.document_version_id, self.version)
        self.assertNotIn("locator", repr(proof))
        self.parses.prove.assert_not_called()

    def test_withdrawn_cross_project_and_digest_mismatch_fail_closed(self) -> None:
        self.evidence.get_for_trace.return_value = None
        with self.assertRaises(ReferenceUseEvidenceError):
            self.prove()
        self.evidence.get_for_trace.return_value = replace(
            self.source, project_id=uuid.uuid4())
        with self.assertRaises(ReferenceUseEvidenceError):
            self.prove()
        self.evidence.get_for_trace.return_value = replace(
            self.source, content_fingerprint=b"x" * 32)
        with self.assertRaises(ReferenceUseEvidenceError):
            self.prove()

    def test_parsed_locator_requires_matching_node_and_source_sha(self) -> None:
        parse_id = uuid.uuid4()
        locator = {"locator_type": "TEXT_RANGE", "section_path": "root",
                   "start_offset": 0, "end_offset": 1,
                   "normalized_fingerprint": "a" * 64}
        self.evidence.get_for_trace.return_value = replace(
            self.source, source_parse_record_id=parse_id,
            locator=locator, content_fingerprint=b"n" * 32)
        parsed = VerifiedParseResult(
            parse_id, self.version, uuid.uuid4(), "PLAIN_TEXT", "1",
            self.digest, b"r" * 32, b"result")
        self.parses.prove.return_value = parsed
        node = EvidenceParsedNodeProof(
            self.version, parse_id, "node", locator, b"n" * 32,
            source_sha256=self.digest)
        with patch(
            "plm_assistant.modules.evidence.application.prove_reference_use_evidence."
            "ParsedNodeEvidenceProofService.prove_verified", return_value=node):
            self.assertEqual(self.prove().content_fingerprint, b"n" * 32)
        with patch(
            "plm_assistant.modules.evidence.application.prove_reference_use_evidence."
            "ParsedNodeEvidenceProofService.prove_verified",
            return_value=replace(node, source_sha256=b"x" * 32)):
            with self.assertRaises(ReferenceUseEvidenceError):
                self.prove()
        self.parses.prove.return_value = replace(parsed, source_sha256=b"x" * 32)
        with self.assertRaises(ReferenceUseEvidenceError):
            self.prove()

    def test_invalid_scope_is_rejected_before_any_port(self) -> None:
        with self.assertRaisesRegex(ReferenceUseEvidenceError, "VALIDATION_FAILED"):
            self.service.prove(
                self.tx, scope="GLOBAL", project_id=self.project,
                evidence_id=self.evidence_id)
        self.evidence.get_for_trace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
