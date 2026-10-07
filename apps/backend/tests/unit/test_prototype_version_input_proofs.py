from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.document.infrastructure.prototype_artifact_proof import (
    SqlAlchemyPrototypeDocumentArtifactProof,
)
from plm_assistant.modules.prototype.application.version_input_proofs import (
    PrototypeVersionTemplateProof,
)
from plm_assistant.modules.prototype.infrastructure.version_input_proofs import (
    SqlAlchemyPrototypeVersionTemplateProof,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.requirement.infrastructure.prototype_version_proof import (
    SqlAlchemyPrototypeApprovedRequirementVersionProof,
)


class PrototypeVersionInputProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = uuid.uuid4()
        self.root = uuid.uuid4()
        self.version = uuid.uuid4()

    @staticmethod
    def transaction(row: object) -> object:
        session = MagicMock(spec=Session)
        session.in_transaction.return_value = True
        session.execute.return_value.one_or_none.return_value = row
        return SimpleNamespace(session=session)

    def test_approved_requirement_proof_is_strict_and_owner_backed(self) -> None:
        review, round_id = uuid.uuid4(), uuid.uuid4()
        row = SimpleNamespace(
            project_id=self.project, requirement_id=self.root,
            requirement_version_id=self.version, version_no=3,
            content_fingerprint=b"r" * 32, review_ref=review,
            review_round_ref=round_id,
        )
        proof = SqlAlchemyPrototypeApprovedRequirementVersionProof().prove(
            self.transaction(row), project_id=self.project,
            requirement_id=self.root, requirement_version_id=self.version,
        )
        self.assertEqual(proof, PrototypeApprovedRequirementVersionProof(
            self.project, self.root, self.version, 3, (b"r" * 32).hex(),
            review, round_id,
        ))
        self.assertIsNone(SqlAlchemyPrototypeApprovedRequirementVersionProof().prove(
            self.transaction(row), project_id=uuid.UUID(int=0),
            requirement_id=self.root, requirement_version_id=self.version,
        ))

    def test_template_proof_accepts_fixed_global_or_same_project_version(self) -> None:
        row = SimpleNamespace(
            prototype_template_id=self.root,
            prototype_template_version_id=self.version, scope="GLOBAL",
            project_id=None, version_no=2, content_fingerprint=b"t" * 32,
        )
        proof = SqlAlchemyPrototypeVersionTemplateProof().prove(
            self.transaction(row), project_id=self.project,
            prototype_template_id=self.root,
            prototype_template_version_id=self.version,
        )
        self.assertEqual(proof, PrototypeVersionTemplateProof(
            self.root, self.version, "GLOBAL", None, 2, (b"t" * 32).hex(),
        ))

    def test_document_proof_returns_fixed_content_and_rejects_bad_identity(self) -> None:
        row = SimpleNamespace(
            document_version_id=self.version, document_id=self.root,
            scope="PROJECT", project_id=self.project,
            content_sha256=b"d" * 32, size_bytes=12,
            detected_mime="application/pdf",
        )
        adapter = SqlAlchemyPrototypeDocumentArtifactProof()
        proof = adapter.prove_for_prototype_version(
            self.transaction(row), project_id=self.project,
            document_version_id=self.version,
        )
        self.assertEqual(proof, PrototypeVersionDocumentArtifactProof(
            self.version, self.root, "PROJECT", self.project,
            (b"d" * 32).hex(), 12, "application/pdf",
        ))
        self.assertIsNone(adapter.prove_for_prototype_version(
            self.transaction(row), project_id=self.project,
            document_version_id=uuid.UUID(int=0),
        ))

    def test_proof_values_reject_invalid_shapes(self) -> None:
        with self.assertRaises(ValueError):
            PrototypeVersionTemplateProof(
                self.root, self.version, "PROJECT", None, 1, "0" * 64,
            )
        with self.assertRaises(ValueError):
            PrototypeVersionDocumentArtifactProof(
                self.version, self.root, "GLOBAL", None, "x" * 64, 1,
                "application/pdf",
            )
        with self.assertRaises(ValueError):
            PrototypeApprovedRequirementVersionProof(
                self.project, self.root, self.version, 0, "0" * 64,
                uuid.uuid4(), uuid.uuid4(),
            )

    def test_all_sql_proofs_require_an_active_owner_transaction(self) -> None:
        for adapter, kwargs in (
            (SqlAlchemyPrototypeApprovedRequirementVersionProof(), {
                "project_id": self.project, "requirement_id": self.root,
                "requirement_version_id": self.version,
            }),
            (SqlAlchemyPrototypeVersionTemplateProof(), {
                "project_id": self.project, "prototype_template_id": self.root,
                "prototype_template_version_id": self.version,
            }),
        ):
            with self.assertRaises(RuntimeError):
                adapter.prove(object(), **kwargs)
        with self.assertRaises(RuntimeError):
            SqlAlchemyPrototypeDocumentArtifactProof().prove_for_prototype_version(
                object(), project_id=self.project,
                document_version_id=self.version,
            )


if __name__ == "__main__":
    unittest.main()
