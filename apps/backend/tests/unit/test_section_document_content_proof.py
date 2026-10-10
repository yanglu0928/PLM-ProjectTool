from __future__ import annotations

import dataclasses
import unittest
import uuid

from plm_assistant.modules.document.application.prove_fixed_source import (
    VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentEvidenceSourceFacts,
)
from plm_assistant.modules.document.application.reference_version_identity import (
    ReferenceVersionIdentity,
)
from plm_assistant.modules.solution.application.prove_section_document_content import (
    SectionDocumentContentError,
)
from plm_assistant.modules.solution.infrastructure.section_document_content_proof import (
    SectionDocumentContentProofAdapter,
)


DOCUMENT = uuid.uuid4()
VERSION = uuid.uuid4()
PROJECT = uuid.uuid4()
TRACE = uuid.uuid4()


class _Identity:
    def __init__(self) -> None:
        self.result = ReferenceVersionIdentity(DOCUMENT, VERSION, "PROJECT", PROJECT)
        self.calls = []

    def get(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.result


class _Fixed:
    def __init__(self) -> None:
        self.result = VerifiedFixedSource(DocumentEvidenceSourceFacts(
            DOCUMENT, VERSION, "PROJECT", PROJECT, "PROJECT_RECORD",
            "ACTIVE", (b"d" * 32).hex(),
        ))
        self.calls = []

    def prove(self, transaction, query, **kwargs):
        self.calls.append((transaction, query, kwargs))
        return self.result


class SectionDocumentContentProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.identities, self.fixed = _Identity(), _Fixed()
        self.adapter = SectionDocumentContentProofAdapter(
            identities=self.identities, fixed_sources=self.fixed)
        self.transaction = object()

    def prove(self, **overrides):
        values = dict(transaction=self.transaction, session_token=b"s" * 32,
                      trace_id=TRACE, project_id=PROJECT,
                      document_version_id=VERSION)
        values.update(overrides)
        return self.adapter.prove(**values)

    def denied(self, code="SOURCE_UNAVAILABLE", **overrides) -> None:
        with self.assertRaises(SectionDocumentContentError) as captured:
            self.prove(**overrides)
        self.assertEqual(captured.exception.code, code)

    def test_project_identity_and_physical_proof_share_transaction(self) -> None:
        result = self.prove()
        self.assertEqual(result.project_id, PROJECT)
        self.assertEqual(result.document_id, DOCUMENT)
        self.assertEqual(result.document_version_id, VERSION)
        self.assertEqual(result.content_sha256, b"d" * 32)
        self.assertNotIn((b"d" * 32).hex(), repr(result))
        self.assertIs(self.identities.calls[0][0], self.transaction)
        self.assertEqual(self.identities.calls[0][1]["scope"], "PROJECT")
        self.assertIs(self.fixed.calls[0][0], self.transaction)
        self.assertEqual(self.fixed.calls[0][1].session_token, b"s" * 32)
        self.assertEqual(self.fixed.calls[0][1].project_id, PROJECT)
        self.assertEqual(self.fixed.calls[0][2]["document_id"], DOCUMENT)

    def test_invalid_query_fails_before_any_source_call(self) -> None:
        for overrides in (
            dict(transaction=None), dict(session_token=b"short"),
            dict(session_token="not bytes"), dict(trace_id=uuid.UUID(int=0)),
            dict(project_id=None), dict(document_version_id=uuid.UUID(int=0)),
        ):
            with self.subTest(overrides=overrides):
                self.denied("VALIDATION_FAILED", **overrides)
        self.assertEqual(self.identities.calls, [])
        self.assertEqual(self.fixed.calls, [])

    def test_missing_or_cross_project_identity_never_reaches_file_proof(self) -> None:
        for identity in (
            None,
            ReferenceVersionIdentity(DOCUMENT, VERSION, "GLOBAL", None),
            ReferenceVersionIdentity(DOCUMENT, VERSION, "PROJECT", uuid.uuid4()),
            ReferenceVersionIdentity(DOCUMENT, uuid.uuid4(), "PROJECT", PROJECT),
        ):
            with self.subTest(identity=identity):
                self.identities.result = identity
                self.denied()
        self.assertEqual(self.fixed.calls, [])

    def test_fixed_proof_mismatch_archived_or_corrupt_digest_fails(self) -> None:
        facts = self.fixed.result.facts
        for altered in (
            dataclasses.replace(facts, project_id=uuid.uuid4()),
            dataclasses.replace(facts, document_id=uuid.uuid4()),
            dataclasses.replace(facts, scope="GLOBAL", project_id=None),
            dataclasses.replace(facts, document_state="ARCHIVED"),
            dataclasses.replace(facts, content_sha256="not hex"),
            dataclasses.replace(facts, content_sha256="00"),
        ):
            with self.subTest(altered=altered):
                self.fixed.result = VerifiedFixedSource(altered)
                self.denied()

    def test_document_error_is_sanitized(self) -> None:
        def unavailable(*_args, **_kwargs):
            raise RuntimeError("private storage locator")
        self.fixed.prove = unavailable
        self.denied()


if __name__ == "__main__":
    unittest.main()
