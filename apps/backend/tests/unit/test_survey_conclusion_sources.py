from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.evidence.application.fixed_project_source import (
    VerifiedProjectEvidence,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordQuery,
    SurveyConclusionProjectRecordProofService,
    SurveyConclusionSourceError,
)


class _Evidence:
    def __init__(self, proof: VerifiedProjectEvidence) -> None:
        self.proof = proof
        self.calls: list[tuple[object, object, uuid.UUID]] = []

    def prove(self, transaction, query, evidence_id):
        self.calls.append((transaction, query, evidence_id))
        return self.proof


class SurveyConclusionProjectRecordProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transaction = object()
        self.actor = uuid.uuid4()
        self.project = uuid.uuid4()
        self.evidence_id = uuid.uuid4()
        self.proof = VerifiedProjectEvidence(
            evidence_id=self.evidence_id,
            project_id=self.project,
            document_id=uuid.uuid4(),
            document_version_id=uuid.uuid4(),
            source_parse_record_id=None,
            observed_lock_version=7,
            content_fingerprint=b"p" * 32,
            verified_by=self.actor,
            verified_project_role="PROJECT_MANAGER",
            document_category="PROJECT_RECORD",
        )
        self.owner = _Evidence(self.proof)
        self.service = SurveyConclusionProjectRecordProofService(
            evidence=self.owner,
        )
        self.query = ConclusionProjectRecordQuery(
            b"s" * 32, uuid.uuid4(), self.project, self.evidence_id,
        )

    def test_exact_project_record_proof_is_minimized(self) -> None:
        result = self.service.prove(self.transaction, self.query)
        self.assertEqual(
            (
                result.evidence_id,
                result.project_id,
                result.document_id,
                result.document_version_id,
                result.observed_evidence_lock_version,
                result.verified_by,
            ),
            (
                self.evidence_id,
                self.project,
                self.proof.document_id,
                self.proof.document_version_id,
                7,
                self.actor,
            ),
        )
        self.assertEqual(result.content_fingerprint, b"p" * 32)
        self.assertNotIn((b"p" * 32).hex(), repr(result))
        self.assertIs(self.owner.calls[0][0], self.transaction)
        self.assertEqual(self.owner.calls[0][2], self.evidence_id)

    def test_category_role_scope_state_identity_and_shape_fail_closed(self) -> None:
        invalid = (
            replace(self.proof, document_category="CONTRACTUAL"),
            replace(self.proof, verified_project_role="CUSTOMER_MANAGER"),
            replace(self.proof, scope="GLOBAL"),
            replace(self.proof, observed_state="REVOKED"),
            replace(self.proof, project_id=uuid.uuid4()),
            replace(self.proof, evidence_id=uuid.uuid4()),
            replace(self.proof, observed_lock_version=-1),
            replace(self.proof, content_fingerprint=b"short"),
            replace(self.proof, verified_by=None),
        )
        for proof in invalid:
            with self.subTest(proof=proof):
                self.owner.proof = proof
                with self.assertRaisesRegex(
                    SurveyConclusionSourceError,
                    "SURVEY_CONCLUSION_SOURCE_INVALID",
                ):
                    self.service.prove(self.transaction, self.query)

    def test_owner_failure_and_invalid_query_are_normalized(self) -> None:
        class _Broken:
            def prove(self, transaction, query, evidence_id):
                raise RuntimeError("private table and database detail")

        service = SurveyConclusionProjectRecordProofService(evidence=_Broken())
        with self.assertRaisesRegex(
            SurveyConclusionSourceError,
            "SURVEY_CONCLUSION_SOURCE_INVALID",
        ):
            service.prove(self.transaction, self.query)
        with self.assertRaisesRegex(
            SurveyConclusionSourceError,
            "SURVEY_CONCLUSION_SOURCE_INVALID",
        ):
            self.service.prove(
                self.transaction,
                replace(self.query, session_token=b"short"),
            )
        self.assertEqual(len(self.owner.calls), 0)


if __name__ == "__main__":
    unittest.main()
