from __future__ import annotations

import dataclasses
import unittest
import uuid

from plm_assistant.modules.document.application.prove_fixed_source import VerifiedFixedSource
from plm_assistant.modules.document.application.read_documents import DocumentEvidenceSourceFacts
from plm_assistant.modules.document.application.reference_version_identity import ReferenceVersionIdentity
from plm_assistant.modules.solution.infrastructure.reference_document_proof import (
    ReferenceDocumentProofAdapter,
)


DOCUMENT = uuid.uuid4()
VERSION = uuid.uuid4()
PROJECT = uuid.uuid4()
TRACE = uuid.uuid4()


class _Identity:
    def __init__(self):
        self.result = ReferenceVersionIdentity(DOCUMENT, VERSION, "PROJECT", PROJECT)
        self.calls = []

    def get(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.result


class _Fixed:
    def __init__(self):
        self.result = VerifiedFixedSource(DocumentEvidenceSourceFacts(
            DOCUMENT, VERSION, "PROJECT", PROJECT, "REFERENCE_MATERIAL",
            "ACTIVE", (b"d" * 32).hex(),
        ))
        self.calls = []

    def prove(self, transaction, query, **kwargs):
        self.calls.append((transaction, query, kwargs))
        return self.result


class ReferenceDocumentProofAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identities, self.fixed = _Identity(), _Fixed()
        self.adapter = ReferenceDocumentProofAdapter(
            identities=self.identities, fixed_sources=self.fixed)
        self.transaction = object()

    def _prove(self, **overrides):
        values = dict(transaction=self.transaction, session_token=b"s" * 32,
                      trace_id=TRACE, scope="PROJECT", project_id=PROJECT,
                      document_version_id=VERSION)
        values.update(overrides)
        return self.adapter.prove(**values)

    def test_fixed_source_uses_same_transaction_after_identity_lookup(self):
        proof = self._prove()
        self.assertEqual(proof.document_version_id, VERSION)
        self.assertEqual(proof.content_sha256, b"d" * 32)
        self.assertIs(self.identities.calls[0][0], self.transaction)
        self.assertIs(self.fixed.calls[0][0], self.transaction)
        self.assertEqual(self.fixed.calls[0][1].project_id, PROJECT)
        self.assertEqual(self.fixed.calls[0][2]["document_id"], DOCUMENT)

    def test_missing_or_cross_scope_identity_never_calls_fixed_source(self):
        self.identities.result = None
        self.assertIsNone(self._prove())
        self.identities.result = ReferenceVersionIdentity(DOCUMENT, VERSION, "GLOBAL", None)
        self.assertIsNone(self._prove())
        self.assertEqual(self.fixed.calls, [])

    def test_invalid_query_is_rejected_before_lookup(self):
        self.assertIsNone(self._prove(scope="GLOBAL"))
        self.assertIsNone(self._prove(project_id=None))
        self.assertIsNone(self._prove(session_token=b"short"))
        self.assertEqual(self.identities.calls, [])

    def test_fixed_proof_mismatch_and_bad_digest_fail_closed(self):
        self.fixed.result = VerifiedFixedSource(dataclasses.replace(
            self.fixed.result.facts, project_id=uuid.uuid4()))
        self.assertIsNone(self._prove())
        self.fixed.result = VerifiedFixedSource(dataclasses.replace(
            self.fixed.result.facts, project_id=PROJECT, content_sha256="no"))
        self.assertIsNone(self._prove())

    def test_global_admin_path_keeps_global_scope(self):
        self.identities.result = ReferenceVersionIdentity(DOCUMENT, VERSION, "GLOBAL", None)
        self.fixed.result = VerifiedFixedSource(dataclasses.replace(
            self.fixed.result.facts, scope="GLOBAL", project_id=None))
        proof = self._prove(scope="GLOBAL", project_id=None)
        self.assertEqual(proof.scope, "GLOBAL")
        self.assertIsNone(proof.project_id)
        self.assertEqual(self.fixed.calls[0][1].scope, "GLOBAL")


if __name__ == "__main__":
    unittest.main()
