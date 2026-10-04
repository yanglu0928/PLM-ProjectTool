from __future__ import annotations

import hashlib
import io
import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.document.application.prepare_download import VerifiedDownload
from plm_assistant.modules.document.application.prove_fixed_source import (
    DocumentFixedSourceProofService, FixedSourceProofError,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts, DocumentReadError, DocumentReadQuery,
)
from plm_assistant.modules.document.application.read_parse_result import (
    FixedParseResultSource, VerifiedParseResult,
)


class _Documents:
    def __init__(self, facts):
        self.facts = facts
        self.calls = []
        self.denied = False

    def get_source_facts_for_evidence(self, tx, query, document_id, version_id):
        self.calls.append((tx, query, document_id, version_id))
        if self.denied:
            raise DocumentReadError("RESOURCE_NOT_FOUND")
        return self.facts


class _Downloads:
    def __init__(self, version_id, digest):
        self.version_id, self.digest = version_id, digest
        self.calls = 0
        self.stream = None

    def prepare(self, *_):
        self.calls += 1
        self.stream = io.BytesIO(b"source")
        return VerifiedDownload(self.version_id, 6, "text/plain",
                                self.digest, self.stream)


class _Metadata:
    def __init__(self, source):
        self.source = source
        self.calls = []

    def get_for_trace(self, tx, **kwargs):
        self.calls.append((tx, kwargs))
        return self.source


class _Parsed:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def read(self, *_args, **_kwargs):
        self.calls += 1
        return self.result


class DocumentFixedSourceProofTests(unittest.TestCase):
    def setUp(self):
        self.tx = object()
        self.project_id = uuid.uuid4()
        self.document_id = uuid.uuid4()
        self.version_id = uuid.uuid4()
        self.record_id = uuid.uuid4()
        self.result_id = uuid.uuid4()
        self.query = DocumentReadQuery(b"s" * 32, uuid.uuid4(),
                                       "PROJECT", self.project_id)
        self.source_sha = hashlib.sha256(b"source").digest()
        self.content = b"parsed"
        self.result_sha = hashlib.sha256(self.content).digest()
        self.facts = DocumentEvidenceSourceFacts(
            self.document_id, self.version_id, "PROJECT", self.project_id,
            "OTHER", "ACTIVE", self.source_sha.hex(),
        )
        self.locked = FixedParseResultSource(
            self.record_id, self.version_id, "PROJECT", self.project_id,
            "PLAIN_TEXT", "1", self.result_id, "private/locator",
            self.result_sha, len(self.content), 1,
        )
        self.parsed = VerifiedParseResult(
            self.record_id, self.version_id, self.result_id,
            "PLAIN_TEXT", "1", self.source_sha, self.result_sha, self.content,
        )
        self.documents = _Documents(self.facts)
        self.downloads = _Downloads(self.version_id, self.source_sha)
        self.metadata = _Metadata(self.locked)
        self.parse_results = _Parsed(self.parsed)
        self.service = DocumentFixedSourceProofService(
            documents=self.documents, downloads=self.downloads,
            parse_metadata=self.metadata, parse_results=self.parse_results,
        )

    def prove(self, record=None):
        return self.service.prove(
            self.tx, self.query, document_id=self.document_id,
            document_version_id=self.version_id, parse_record_id=record,
        )

    def test_whole_document_verifies_physical_snapshot_and_closes_it(self):
        proof = self.prove()
        self.assertEqual(proof.facts, self.facts)
        self.assertIsNone(proof.parse_content)
        self.assertEqual(self.downloads.calls, 1)
        self.assertTrue(self.downloads.stream.closed)
        self.assertEqual(self.metadata.calls, [])
        self.assertIs(self.documents.calls[0][0], self.tx)

    def test_fixed_parse_is_locked_and_bound_to_verified_bytes(self):
        proof = self.prove(self.record_id)
        self.assertEqual(proof.parse_content, self.content)
        self.assertEqual(proof.result_sha256, self.result_sha)
        self.assertIs(self.metadata.calls[0][0], self.tx)
        self.assertEqual(self.parse_results.calls, 1)
        self.assertNotIn("private/locator", repr(proof))
        self.assertNotIn("parsed", repr(proof))

    def test_authorization_and_cross_project_fail_before_physical_read(self):
        self.documents.denied = True
        with self.assertRaisesRegex(FixedSourceProofError, "RESOURCE_NOT_FOUND"):
            self.prove(self.record_id)
        self.assertEqual(self.metadata.calls, [])
        self.documents.denied = False
        self.documents.facts = replace(self.facts, project_id=uuid.uuid4())
        with self.assertRaisesRegex(FixedSourceProofError, "RESOURCE_NOT_FOUND"):
            self.prove(self.record_id)
        self.assertEqual(self.parse_results.calls, 0)

    def test_missing_or_drifted_metadata_fails_closed(self):
        for source in (None, replace(self.locked, result_ref_id=uuid.uuid4()),
                       replace(self.locked, scope="GLOBAL", project_id=None)):
            with self.subTest(source=source):
                self.metadata.source = source
                with self.assertRaisesRegex(FixedSourceProofError, "RESOURCE_NOT_FOUND"):
                    self.prove(self.record_id)

    def test_file_and_parse_integrity_drift_fail_closed(self):
        self.downloads.digest = b"x" * 32
        with self.assertRaisesRegex(FixedSourceProofError, "FILE_INTEGRITY_MISMATCH"):
            self.prove()
        self.assertTrue(self.downloads.stream.closed)
        self.parse_results.result = replace(self.parsed, source_sha256=b"x" * 32)
        with self.assertRaisesRegex(FixedSourceProofError, "RESOURCE_NOT_FOUND"):
            self.prove(self.record_id)
        self.parse_results.result = replace(self.parsed, content=b"tamper")
        with self.assertRaisesRegex(FixedSourceProofError, "RESOURCE_NOT_FOUND"):
            self.prove(self.record_id)

    def test_invalid_identity_rejected_before_document_access(self):
        with self.assertRaisesRegex(FixedSourceProofError, "RESOURCE_NOT_FOUND"):
            self.service.prove(None, self.query, document_id=self.document_id,
                               document_version_id=self.version_id)
        self.assertEqual(self.documents.calls, [])


if __name__ == "__main__":
    unittest.main()
