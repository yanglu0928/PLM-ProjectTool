from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from plm_assistant.modules.capability.application.requirement_source_proof import (
    CapabilityRequirementSourceProof,
)
from plm_assistant.modules.capability.infrastructure.requirement_source_proof import (
    SqlAlchemyCapabilityRequirementSourceProof,
)
from plm_assistant.modules.evidence.application.fixed_source_record import (
    LockedEvidenceSource,
)
from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)
from plm_assistant.modules.evidence.infrastructure.requirement_source_proof import (
    SqlAlchemyEvidenceRequirementSourceProof,
)


class _EvidenceRepository:
    def __init__(self, source) -> None:
        self.source = source
        self.calls = []

    def get_for_trace(self, transaction, **values):
        self.calls.append((transaction, values))
        return self.source


class RequirementReferenceSourceProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ids = [uuid.uuid4() for _ in range(12)]
        (
            self.project, self.evidence, self.document, self.document_version,
            self.baseline_version, self.baseline, self.capability_item,
            self.capability_row, self.review, self.round, self.parse, _,
        ) = self.ids

    def test_evidence_proof_reuses_current_project_lock_without_locator(self) -> None:
        source = LockedEvidenceSource(
            self.evidence, "PROJECT", self.project, self.document,
            self.document_version, self.parse, {"locator_type": "DOCUMENT"},
            b"e" * 32, 4,
        )
        repository = _EvidenceRepository(source)
        proof = SqlAlchemyEvidenceRequirementSourceProof(repository)
        tx = object()
        result = proof.prove(
            tx, project_id=self.project, evidence_id=self.evidence,
        )
        self.assertEqual(result, EvidenceRequirementSourceProof(
            self.evidence, self.project, self.document,
            self.document_version, 4, b"e" * 32,
        ))
        self.assertEqual(repository.calls, [(tx, {
            "scope": "PROJECT", "project_id": self.project,
            "evidence_id": self.evidence,
        })])
        self.assertNotIn("locator", repr(result).lower())
        self.assertNotIn("eeee", repr(result))

    def test_evidence_rejects_mismatched_or_invalid_owner_facts(self) -> None:
        wrong = LockedEvidenceSource(
            self.evidence, "GLOBAL", None, self.document,
            self.document_version, None, {}, b"e" * 32, 0,
        )
        proof = SqlAlchemyEvidenceRequirementSourceProof(
            _EvidenceRepository(wrong),
        )
        self.assertIsNone(proof.prove(
            object(), project_id=self.project, evidence_id=self.evidence,
        ))
        repository = _EvidenceRepository(wrong)
        proof = SqlAlchemyEvidenceRequirementSourceProof(repository)
        self.assertIsNone(proof.prove(
            object(), project_id=uuid.UUID(int=0), evidence_id=self.evidence,
        ))
        self.assertEqual(repository.calls, [])

    def test_capability_proof_locks_current_item_and_global_review(self) -> None:
        proof = SqlAlchemyCapabilityRequirementSourceProof()
        values = (
            self.baseline_version, self.baseline, self.capability_item,
            self.capability_row, self.review, self.round, 2, b"c" * 32,
        )
        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            execute.return_value.one_or_none.return_value = values
            result = proof.prove(
                SimpleNamespace(session=session),
                baseline_version_id=self.baseline_version,
                capability_item_id=self.capability_item,
            )
            self.assertEqual(result, CapabilityRequirementSourceProof(*values))
            statement = execute.call_args.args[0]
            sql = str(statement.compile(dialect=postgresql.dialect()))
            for token in (
                "cap_baselines.baseline_state",
                "cap_baselines.current_approved_version_ref",
                "cap_baseline_versions.version_state",
                "cap_items.item_state", "rvw_reviews.subject_type",
                "rvw_reviews.policy_code", "rvw_review_rounds.round_state",
                "rvw_subject_snapshots.content_fingerprint",
                "FOR SHARE OF cap_baselines, cap_baseline_versions, cap_items, "
                "rvw_reviews, rvw_review_rounds, rvw_subject_snapshots",
            ):
                self.assertIn(token, sql)
            self.assertTrue(statement.get_execution_options()["populate_existing"])
            self.assertNotIn("cccc", repr(result))

    def test_capability_missing_and_invalid_identity_fail_closed(self) -> None:
        proof = SqlAlchemyCapabilityRequirementSourceProof()
        with Session() as session, session.begin(), patch.object(
            session, "execute",
        ) as execute:
            execute.return_value.one_or_none.return_value = None
            self.assertIsNone(proof.prove(
                SimpleNamespace(session=session),
                baseline_version_id=self.baseline_version,
                capability_item_id=self.capability_item,
            ))
            sql = str(execute.call_args.args[0].compile(
                dialect=postgresql.dialect(),
            )).lstrip().upper()
            self.assertTrue(sql.startswith("SELECT "))
            execute.reset_mock()
            self.assertIsNone(proof.prove(
                SimpleNamespace(session=session),
                baseline_version_id=self.baseline_version,
                capability_item_id=uuid.UUID(int=0),
            ))
            execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
