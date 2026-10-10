from __future__ import annotations

import io
import uuid
import unittest
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.document.application.prove_reference_use_document import (
    CurrentReferenceDocumentSource,
    ReferenceUseDocumentError,
    ReferenceUseDocumentProofService,
)


class ReferenceUseDocumentProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.version = uuid.uuid4()
        self.digest = b"d" * 32
        self.source = CurrentReferenceDocumentSource(
            uuid.uuid4(), self.version, "PROJECT", self.project,
            "PROJECT_RECORD", self.digest, 3, "text/plain",
            "projects/opaque/object")
        self.sources = Mock()
        self.sources.current.return_value = self.source
        self.storage = Mock()
        self.storage.open_verified_snapshot.side_effect = lambda *_a, **_k: io.BytesIO(b"abc")
        self.service = ReferenceUseDocumentProofService(
            sources=self.sources, storage=self.storage)
        self.tx = object()

    def reject(self, **changes) -> None:
        with self.assertRaisesRegex(ReferenceUseDocumentError, "DOCUMENT_UNAVAILABLE"):
            self.service.prove(self.tx, scope="PROJECT", project_id=self.project,
                               document_version_id=self.version)

    def test_project_proof_is_opaque_and_storage_verified(self) -> None:
        proof = self.service.prove(self.tx, scope="PROJECT", project_id=self.project,
                                   document_version_id=self.version)
        self.assertEqual(proof.document_version_id, self.version)
        self.assertEqual(proof.content_sha256, self.digest)
        self.assertNotIn("locator", repr(proof))
        self.storage.open_verified_snapshot.assert_called_once_with(
            self.source.storage_locator, expected_sha256=self.digest,
            expected_size=3, max_bytes=100_000_000)

    def test_global_accepts_only_global_category_and_no_project(self) -> None:
        self.sources.current.return_value = replace(
            self.source, scope="GLOBAL", project_id=None,
            document_category="REFERENCE_MATERIAL")
        proof = self.service.prove(self.tx, scope="GLOBAL", project_id=None,
                                   document_version_id=self.version)
        self.assertEqual(proof.scope, "GLOBAL")
        self.sources.current.return_value = replace(
            self.source, scope="GLOBAL", project_id=None,
            document_category="CONTRACTUAL")
        with self.assertRaises(ReferenceUseDocumentError):
            self.service.prove(self.tx, scope="GLOBAL", project_id=None,
                               document_version_id=self.version)

    def test_source_identity_scope_digest_and_storage_fail_closed(self) -> None:
        for source in (
            None,
            replace(self.source, document_version_id=uuid.uuid4()),
            replace(self.source, project_id=uuid.uuid4()),
            replace(self.source, scope="GLOBAL"),
            replace(self.source, content_sha256=b"bad"),
            replace(self.source, size_bytes=100_000_001),
            replace(self.source, storage_locator=""),
        ):
            with self.subTest(source=source):
                self.sources.current.return_value = source
                self.reject()
        self.sources.current.return_value = self.source
        self.storage.open_verified_snapshot.side_effect = RuntimeError("tampered file")
        self.reject()

    def test_invalid_input_does_not_read_source(self) -> None:
        with self.assertRaisesRegex(ReferenceUseDocumentError, "VALIDATION_FAILED"):
            self.service.prove(self.tx, scope="GLOBAL", project_id=self.project,
                               document_version_id=self.version)
        self.sources.current.assert_not_called()


if __name__ == "__main__":
    unittest.main()
