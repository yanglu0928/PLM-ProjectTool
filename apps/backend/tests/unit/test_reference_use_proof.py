from __future__ import annotations

import uuid
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from plm_assistant.modules.solution.application.prove_reference_use import (
    CurrentGlobalConfirmationProof,
    CurrentReferenceSourceProof,
    CurrentReferenceUseSnapshot,
    EligibleReferenceUseProof,
    ReferenceUseProofError,
    ReferenceUseProofService,
    ReferenceUseQuery,
)


class ReferenceUseProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
        self.tx = object()
        self.project = uuid.uuid4()
        self.root = uuid.uuid4()
        self.version = uuid.uuid4()
        self.event = uuid.uuid4()
        self.document = uuid.uuid4()
        self.evidence = uuid.uuid4()
        self.confirmation = uuid.uuid4()
        self.digest = b"s" * 32
        self.query = ReferenceUseQuery(
            uuid.uuid4(), self.project, self.root, self.version, "GLOBAL")
        self.snapshot = CurrentReferenceUseSnapshot(
            self.root, self.version, "GLOBAL", None, "ELIGIBLE",
            self.event, self.version, "ELIGIBLE", (self.document,),
            (self.evidence,), self.digest, self.confirmation,
            "REFERENCE", "VERIFIED", {"products": ["PLM"]})
        self.source = CurrentReferenceSourceProof(
            "GLOBAL", None, (self.document,), (self.evidence,), self.digest)
        self.confirmed = CurrentGlobalConfirmationProof(
            self.confirmation, self.digest, "I_VERIFIED_DEIDENTIFICATION",
            self.now - timedelta(days=1), self.now + timedelta(days=1), None)
        self.references = Mock()
        self.references.current.return_value = self.snapshot
        self.sources = Mock()
        self.sources.prove.return_value = self.source
        self.confirmations = Mock()
        self.confirmations.current.return_value = self.confirmed
        self.service = ReferenceUseProofService(
            references=self.references, sources=self.sources,
            confirmations=self.confirmations, clock=lambda: self.now)

    def assert_rejected(self) -> None:
        with self.assertRaisesRegex(ReferenceUseProofError, "REFERENCE_UNAVAILABLE"):
            self.service.prove(self.tx, self.query)

    def test_global_project_use_is_opaque_and_requires_current_confirmation(self) -> None:
        proof = self.service.prove(self.tx, self.query)
        self.assertIs(type(proof), EligibleReferenceUseProof)
        self.assertEqual(proof.target_project_id, self.project)
        self.assertEqual(proof.reference_version_id, self.version)
        self.assertEqual(proof.eligibility_event_id, self.event)
        self.assertEqual(proof.deidentification_confirmation_id, self.confirmation)
        self.assertNotIn("document", repr(proof))
        self.assertNotIn("evidence", repr(proof))
        self.assertNotIn(self.digest.hex(), repr(proof))
        self.references.current.assert_called_once_with(
            self.tx, query=self.query, now=self.now)

    def test_project_requires_same_project_and_skips_global_confirmation(self) -> None:
        self.query = replace(self.query, scope="PROJECT")
        self.snapshot = replace(
            self.snapshot, scope="PROJECT", source_project_id=self.project,
            deidentification_confirmation_id=None)
        self.source = replace(self.source, scope="PROJECT", source_project_id=self.project)
        self.references.current.return_value = self.snapshot
        self.sources.prove.return_value = self.source
        self.service.prove(self.tx, self.query)
        self.confirmations.current.assert_not_called()
        self.references.current.return_value = replace(
            self.snapshot, source_project_id=uuid.uuid4())
        self.assert_rejected()

    def test_old_version_state_or_event_never_reaches_source_port(self) -> None:
        for altered in (
            replace(self.snapshot, reference_version_id=uuid.uuid4()),
            replace(self.snapshot, eligibility_state="RESTRICTED"),
            replace(self.snapshot, eligibility_state="REVOKED"),
            replace(self.snapshot, eligibility_event_version_id=uuid.uuid4()),
            replace(self.snapshot, eligibility_event_result_state="RESTRICTED"),
            replace(self.snapshot, eligibility_event_id=uuid.UUID(int=0)),
            replace(self.snapshot, document_version_ids=()),
            replace(self.snapshot, document_version_ids=(self.document, self.document)),
        ):
            with self.subTest(altered=altered):
                self.references.current.return_value = altered
                self.assert_rejected()
        self.sources.prove.assert_not_called()

    def test_source_set_and_digest_must_match_fixed_snapshot(self) -> None:
        for altered in (
            replace(self.source, document_version_ids=(uuid.uuid4(),)),
            replace(self.source, evidence_ids=()),
            replace(self.source, source_fingerprint=b"t" * 32),
            replace(self.source, scope="PROJECT"),
        ):
            with self.subTest(altered=altered):
                self.sources.prove.return_value = altered
                self.assert_rejected()
        self.confirmations.current.assert_not_called()

    def test_global_confirmation_identity_fingerprint_and_time(self) -> None:
        for altered in (
            replace(self.confirmed, confirmation_id=uuid.uuid4()),
            replace(self.confirmed, source_fingerprint=b"t" * 32),
            replace(self.confirmed, attestation_statement="UNKNOWN"),
            replace(self.confirmed, expires_at=self.now),
            replace(self.confirmed, revoked_at=self.now),
        ):
            with self.subTest(altered=altered):
                self.confirmations.current.return_value = altered
                self.assert_rejected()

    def test_invalid_input_and_port_failure_fail_closed(self) -> None:
        with self.assertRaisesRegex(ReferenceUseProofError, "VALIDATION_FAILED"):
            self.service.prove(self.tx, replace(self.query, target_project_id=uuid.UUID(int=0)))
        self.references.current.side_effect = RuntimeError("repository unavailable")
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
