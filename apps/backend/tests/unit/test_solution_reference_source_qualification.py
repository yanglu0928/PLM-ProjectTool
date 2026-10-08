from __future__ import annotations

import dataclasses
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from plm_assistant.modules.solution.application.reference_source_qualification import (
    ReferenceSourceError, ReferenceSourceQualificationService,
    ReferenceSourceRequest, VerifiedReferenceDeidentification,
    VerifiedReferenceDocument, VerifiedReferenceEvidence,
)


SESSION = b"s" * 32
TRACE = uuid.uuid4()
PROJECT = uuid.uuid4()
DOCUMENT = uuid.uuid4()
VERSION = uuid.uuid4()
EVIDENCE = uuid.uuid4()


class _Documents:
    def __init__(self) -> None:
        self.proof = VerifiedReferenceDocument(
            DOCUMENT, VERSION, "PROJECT", PROJECT, "REFERENCE_MATERIAL", b"d" * 32)
        self.calls = []

    def prove(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.proof


class _Evidence:
    def __init__(self) -> None:
        self.proof = VerifiedReferenceEvidence(EVIDENCE, VERSION, "PROJECT", PROJECT, b"e" * 32)
        self.calls = []

    def prove(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        return self.proof


class _Attestations:
    def __init__(self) -> None:
        self.confirm = True
        self.wrong_fingerprint = False
        self.expired = False
        self.future = False
        self.calls = []

    def prove(self, transaction, **kwargs):
        self.calls.append((transaction, kwargs))
        if not self.confirm:
            return None
        return VerifiedReferenceDeidentification(
            uuid.uuid4(), uuid.uuid4(),
            b"wrong" if self.wrong_fingerprint else kwargs["source_fingerprint"],
            datetime(2026, 10, 8, tzinfo=timezone.utc) + (
                timedelta(days=1) if self.future else timedelta(days=-1)),
            datetime(2026, 10, 8, tzinfo=timezone.utc) + (
                timedelta(days=-1) if self.expired else timedelta(days=1)),
        )


class ReferenceSourceQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents, self.evidence, self.attestations = (
            _Documents(), _Evidence(), _Attestations())
        self.service = ReferenceSourceQualificationService(
            documents=self.documents, evidence=self.evidence,
            deidentification=self.attestations,
            clock=lambda: datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.transaction = object()
        self.request = ReferenceSourceRequest(
            SESSION, TRACE, "PROJECT", PROJECT, (VERSION,), (EVIDENCE,),
            "PLM", "PROJECT_ONLY", {"industry": "制造"},
        )

    def test_project_uses_fixed_proofs_without_global_attestation(self) -> None:
        result = self.service.qualify(self.transaction, self.request)
        self.assertEqual(result.scope, "PROJECT")
        self.assertEqual(result.project_id, PROJECT)
        self.assertEqual(result.document_versions[0].document_version_id, VERSION)
        self.assertEqual(result.evidence[0].evidence_id, EVIDENCE)
        self.assertEqual(len(result.content_fingerprint), 32)
        self.assertIsNone(result.deidentification_confirmation_id)
        self.assertEqual(self.documents.calls[0][0], self.transaction)
        self.assertEqual(self.evidence.calls[0][0], self.transaction)
        self.assertEqual(self.attestations.calls, [])

    def test_global_requires_same_fingerprint_human_admin_confirmation(self) -> None:
        self.documents.proof = dataclasses.replace(
            self.documents.proof, scope="GLOBAL", project_id=None)
        self.evidence.proof = dataclasses.replace(
            self.evidence.proof, scope="GLOBAL", project_id=None)
        request = dataclasses.replace(
            self.request, scope="GLOBAL", project_id=None,
            deidentification_class="DEIDENTIFIED")
        result = self.service.qualify(self.transaction, request)
        self.assertIsNotNone(result.deidentification_confirmation_id)
        self.assertEqual(self.attestations.calls[0][0], self.transaction)
        self.assertEqual(self.attestations.calls[0][1]["source_fingerprint"],
                         result.content_fingerprint)
        self.attestations.confirm = False
        self._reject(request)
        self.attestations.confirm = True
        self.attestations.wrong_fingerprint = True
        self._reject(request)
        self.attestations.wrong_fingerprint = False
        self.attestations.expired = True
        self._reject(request)
        self.attestations.expired = False
        self.attestations.future = True
        self._reject(request)
        self.attestations.future = False
        self.documents.proof = dataclasses.replace(
            self.documents.proof, document_category="PROJECT_RECORD")
        self._reject(request)

    def test_scope_category_and_cross_project_mismatch_fail_closed(self) -> None:
        self.documents.proof = dataclasses.replace(self.documents.proof, project_id=uuid.uuid4())
        self._reject(self.request)
        self.documents.proof = dataclasses.replace(
            self.documents.proof, project_id=PROJECT, document_category="TEMPLATE")
        self._reject(self.request)
        self.documents.proof = dataclasses.replace(
            self.documents.proof, document_category="REFERENCE_MATERIAL")
        self.evidence.proof = dataclasses.replace(self.evidence.proof, scope="GLOBAL", project_id=None)
        self._reject(self.request)
        self.evidence.proof = dataclasses.replace(
            self.evidence.proof, scope="PROJECT", project_id=PROJECT,
            content_fingerprint=b"bad")
        self._reject(self.request)

    def test_wrong_document_version_or_digest_fail_closed(self) -> None:
        self.documents.proof = dataclasses.replace(
            self.documents.proof, document_version_id=uuid.uuid4())
        self._reject(self.request)
        self.documents.proof = dataclasses.replace(
            self.documents.proof, document_version_id=VERSION, content_sha256=b"bad")
        self._reject(self.request)

    def test_duplicate_missing_and_invalid_inputs_are_rejected_before_ports(self) -> None:
        for request in (
            dataclasses.replace(self.request, document_version_ids=()),
            dataclasses.replace(self.request, document_version_ids=(VERSION, VERSION)),
            dataclasses.replace(self.request, evidence_ids=(EVIDENCE, EVIDENCE)),
            dataclasses.replace(self.request, scope="GLOBAL"),
            dataclasses.replace(self.request, project_id=None),
            dataclasses.replace(self.request, applicability={"score": float("nan")}),
            dataclasses.replace(self.request, session_token=b"short"),
        ):
            self._reject(request, "VALIDATION_FAILED")
        self.assertEqual(self.documents.calls, [])

    def test_unavailable_port_is_not_treated_as_success(self) -> None:
        def unavailable(*args, **kwargs):
            raise ConnectionError("source unavailable")
        self.documents.prove = unavailable
        self._reject(self.request, "SOURCE_UNAVAILABLE")

    def test_content_fingerprint_binds_metadata_and_source_hash(self) -> None:
        first = self.service.qualify(self.transaction, self.request)
        changed_class = self.service.qualify(
            self.transaction, dataclasses.replace(self.request, source_project_class="AUTO"))
        self.documents.proof = dataclasses.replace(self.documents.proof, content_sha256=b"x" * 32)
        changed_content = self.service.qualify(self.transaction, self.request)
        self.assertNotEqual(first.content_fingerprint, changed_class.content_fingerprint)
        self.assertNotEqual(first.content_fingerprint, changed_content.content_fingerprint)

    def _reject(self, request: ReferenceSourceRequest, code: str = "RESOURCE_NOT_FOUND") -> None:
        with self.assertRaises(ReferenceSourceError) as caught:
            self.service.qualify(self.transaction, request)
        self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
