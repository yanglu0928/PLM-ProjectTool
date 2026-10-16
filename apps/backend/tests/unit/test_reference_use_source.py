from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from unittest.mock import Mock

from plm_assistant.modules.document.application.prove_reference_use_document import (
    ReferenceUseDocumentProof,
)
from plm_assistant.modules.evidence.application.prove_reference_use_evidence import (
    ReferenceUseEvidenceProof,
)
from plm_assistant.modules.solution.application.prove_reference_use import (
    CurrentReferenceUseSnapshot,
    ReferenceUseQuery,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    fingerprint_reference_sources,
)
from plm_assistant.modules.solution.infrastructure.reference_use_source import (
    CurrentReferenceSourceAdapter,
)


class CurrentReferenceSourceAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tx = object()
        self.project = uuid.uuid4()
        self.root = uuid.uuid4()
        self.version = uuid.uuid4()
        self.document = uuid.uuid4()
        self.evidence_id = uuid.uuid4()
        self.doc_hash = b"d" * 32
        self.evidence_hash = b"e" * 32
        self.query = ReferenceUseQuery(uuid.uuid4(), self.project, self.root,
                                       self.version, "PROJECT")
        self.snapshot = CurrentReferenceUseSnapshot(
            self.root, self.version, "PROJECT", self.project, "ELIGIBLE",
            uuid.uuid4(), self.version, "ELIGIBLE", (self.document,),
            (self.evidence_id,), b"s" * 32, None,
            "PROJECT_REFERENCE", "NOT_REQUIRED", {"product": "PLM"})
        self.documents = Mock()
        self.documents.prove.return_value = ReferenceUseDocumentProof(
            self.document, "PROJECT", self.project, self.doc_hash)
        self.evidence = Mock()
        self.evidence.prove.return_value = ReferenceUseEvidenceProof(
            self.evidence_id, self.document, "PROJECT", self.project,
            self.evidence_hash)
        self.adapter = CurrentReferenceSourceAdapter(
            documents=self.documents, evidence=self.evidence)

    def test_project_recomputes_creation_canonical_fingerprint(self) -> None:
        result = self.adapter.prove(self.tx, query=self.query,
                                    current=self.snapshot)
        self.assertIsNotNone(result)
        self.assertEqual(result.source_fingerprint,
                         fingerprint_reference_sources(
                             scope="PROJECT", project_id=self.project,
                             documents=((self.document, self.doc_hash),),
                             evidence=((self.evidence_id, self.document,
                                        self.evidence_hash),),
                             source_project_class="PROJECT_REFERENCE",
                             deidentification_class="NOT_REQUIRED",
                             applicability={"product": "PLM"}))
        self.assertNotIn(self.doc_hash.hex(), repr(result))

    def test_global_uses_opaque_service_ports_without_admin_session(self) -> None:
        self.query = replace(self.query, scope="GLOBAL")
        self.snapshot = replace(self.snapshot, scope="GLOBAL",
                                source_project_id=None)
        self.documents.prove.return_value = ReferenceUseDocumentProof(
            self.document, "GLOBAL", None, self.doc_hash)
        self.evidence.prove.return_value = ReferenceUseEvidenceProof(
            self.evidence_id, self.document, "GLOBAL", None,
            self.evidence_hash)
        self.assertIsNotNone(self.adapter.prove(
            self.tx, query=self.query, current=self.snapshot))
        self.documents.prove.assert_called_once_with(
            self.tx, scope="GLOBAL", project_id=None,
            document_version_id=self.document)
        self.evidence.prove.assert_called_once_with(
            self.tx, scope="GLOBAL", project_id=None,
            evidence_id=self.evidence_id)

    def test_wrong_scope_id_digest_or_port_failure_closes(self) -> None:
        for altered in (
            replace(self.snapshot, source_project_id=uuid.uuid4()),
            replace(self.snapshot, applicability={"bad": float("nan")}),
            replace(self.snapshot, applicability={"large": "a" * 65_000}),
        ):
            with self.subTest(altered=altered):
                self.assertIsNone(self.adapter.prove(
                    self.tx, query=self.query, current=altered))
        self.documents.prove.return_value = replace(
            self.documents.prove.return_value, content_sha256=b"short")
        self.assertIsNone(self.adapter.prove(
            self.tx, query=self.query, current=self.snapshot))
        self.documents.prove.side_effect = RuntimeError("unavailable")
        self.assertIsNone(self.adapter.prove(
            self.tx, query=self.query, current=self.snapshot))

    def test_evidence_mismatch_closes(self) -> None:
        self.evidence.prove.return_value = replace(
            self.evidence.prove.return_value, project_id=uuid.uuid4())
        self.assertIsNone(self.adapter.prove(
            self.tx, query=self.query, current=self.snapshot))


if __name__ == "__main__":
    unittest.main()
