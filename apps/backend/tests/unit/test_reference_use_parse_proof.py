from __future__ import annotations

import hashlib
import json
import uuid
import unittest
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProof,
)
from plm_assistant.modules.document.application.prove_reference_use_parse import (
    ReferenceUseParseError, ReferenceUseParseProofService,
)
from plm_assistant.modules.document.application.read_parse_result import (
    FixedParseResultSource, VerifiedParseResult,
)


class ReferenceUseParseProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.version = uuid.uuid4()
        self.record = uuid.uuid4()
        self.result = uuid.uuid4()
        self.digest = b"s" * 32
        self.document = ReferenceUseDocumentProof(
            self.version, "GLOBAL", None, self.digest)
        self.content = json.dumps({
            "schema_version": "1", "document_version_id": str(self.version),
            "source_sha256": self.digest.hex(), "parser_profile": "PLAIN_TEXT",
            "parser_version": "1", "nodes": [],
        }, separators=(",", ":")).encode()
        self.metadata_row = FixedParseResultSource(
            self.record, self.version, "GLOBAL", None,
            "PLAIN_TEXT", "1", self.result, "results/global/x",
            hashlib.sha256(self.content).digest(), len(self.content), 1)
        self.documents = Mock()
        self.documents.prove.return_value = self.document
        self.metadata = Mock()
        self.metadata.get_for_trace.return_value = self.metadata_row
        self.storage = Mock()
        self.storage.read_verified.return_value = self.content
        self.service = ReferenceUseParseProofService(
            documents=self.documents, metadata=self.metadata,
            storage=self.storage)
        self.tx = object()

    def prove(self) -> VerifiedParseResult:
        return self.service.prove(
            self.tx, scope="GLOBAL", project_id=None,
            document_version_id=self.version, parse_record_id=self.record)

    def test_valid_result_is_internal_verified_parse(self) -> None:
        result = self.prove()
        self.assertIs(type(result), VerifiedParseResult)
        self.assertEqual(result.source_sha256, self.digest)
        self.assertEqual(result.content, self.content)
        self.assertNotIn(self.content.decode(), repr(result))
        self.assertEqual(self.documents.prove.call_count, 2)
        self.assertEqual(self.metadata.get_for_trace.call_count, 2)

    def test_metadata_result_or_content_mismatch_rejected(self) -> None:
        for bad in (
            None,
            replace(self.metadata_row, document_version_id=uuid.uuid4()),
            replace(self.metadata_row, result_sha256=b"r" * 32),
        ):
            with self.subTest(bad=bad):
                self.metadata.get_for_trace.return_value = bad
                with self.assertRaises(ReferenceUseParseError):
                    self.prove()
        self.metadata.get_for_trace.return_value = self.metadata_row
        self.storage.read_verified.return_value = self.content[:-1] + b"!"
        with self.assertRaises(ReferenceUseParseError):
            self.prove()

    def test_payload_source_binding_and_second_read_required(self) -> None:
        altered = self.content.replace(self.digest.hex().encode(), (b"a" * 64))
        self.storage.read_verified.return_value = altered
        self.metadata.get_for_trace.return_value = replace(
            self.metadata_row, result_sha256=hashlib.sha256(altered).digest(),
            size_bytes=len(altered))
        with self.assertRaises(ReferenceUseParseError):
            self.prove()
        self.storage.read_verified.return_value = self.content
        self.metadata.get_for_trace.return_value = self.metadata_row
        self.documents.prove.side_effect = [
            self.document, replace(self.document, content_sha256=b"t" * 32)]
        with self.assertRaises(ReferenceUseParseError):
            self.prove()

    def test_invalid_scope_never_reads_ports(self) -> None:
        with self.assertRaisesRegex(ReferenceUseParseError, "VALIDATION_FAILED"):
            self.service.prove(
                self.tx, scope="GLOBAL", project_id=uuid.uuid4(),
                document_version_id=self.version, parse_record_id=self.record)
        self.documents.prove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
