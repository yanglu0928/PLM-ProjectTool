from __future__ import annotations

import unittest
import uuid
from dataclasses import replace

from plm_assistant.modules.solution.application.prove_structured_spec_sources import (
    ProvenStructuredSpecSources,
)
from plm_assistant.modules.solution.application.structured_spec_input import (
    SpecRequirementRef, SpecSectionRef, StructuredSpecDraftInput,
    validate_structured_spec_draft,
)
from plm_assistant.modules.solution.application.structured_spec_result import (
    StructuredSpecRevisionBase,
)
from plm_assistant.modules.solution.infrastructure.structured_spec_create_repository import (
    SqlAlchemyStructuredSpecCreateRepository,
)


class StructuredSpecRevisionRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project, self.series, self.current = (
            uuid.uuid4() for _ in range(3))
        value = StructuredSpecDraftInput(
            self.project, self.series, self.current, "MIGRATION_SPEC", {
                "assumptions": ["synthetic"], "exclusions": [],
                "source_system": "old", "target_system": "new",
                "scope": "parts", "cleansing_rules": ["deduplicate"],
                "field_mappings": [{"source": "old_id", "target": "part_id"}],
                "trial_plan": "trial", "reconciliation_plan": "compare",
                "rollback_plan": "restore", "acceptance_criteria": "zero difference",
            }, (SpecRequirementRef(uuid.uuid4(), uuid.uuid4()),),
            (SpecSectionRef(uuid.uuid4(), uuid.uuid4()),), (), ())
        self.draft = validate_structured_spec_draft(value)
        self.proof = ProvenStructuredSpecSources(
            self.draft, (), (), (), b"p" * 32)
        self.base = StructuredSpecRevisionBase(
            self.current, self.current, self.series, self.project,
            "MIGRATION_SPEC", 1, 1, "DRAFT")
        self.repository = SqlAlchemyStructuredSpecCreateRepository()

    def test_rejects_stale_or_ineligible_base_before_database_access(self) -> None:
        variants = (
            replace(self.base, latest_version_ref=uuid.uuid4(),
                    latest_version_no=2),
            replace(self.base, version_state="IN_REVIEW"),
            replace(self.base, version_state="RESTRICTED"),
            replace(self.base, version_state="SUPERSEDED"),
        )
        for base in variants:
            with self.subTest(state=base.version_state), self.assertRaises(RuntimeError):
                self.repository.revise(
                    object(), base=base, version_id=uuid.uuid4(),
                    actor_id=uuid.uuid4(), proof=self.proof)

    def test_rejects_client_binding_drift_before_database_access(self) -> None:
        variants = (
            replace(self.draft, project_id=uuid.uuid4()),
            replace(self.draft, spec_series_id=uuid.uuid4()),
            replace(self.draft, supersedes_version_ref=uuid.uuid4()),
            replace(self.draft, spec_type="INTERFACE_SPEC"),
        )
        for draft in variants:
            proof = replace(self.proof, draft=draft)
            with self.subTest(draft=draft), self.assertRaises(ValueError):
                self.repository.revise(
                    object(), base=self.base, version_id=uuid.uuid4(),
                    actor_id=uuid.uuid4(), proof=proof)

    def test_revision_base_rejects_invalid_identity_without_database_access(self) -> None:
        self.assertIsNone(self.repository.revision_base(
            object(), project_id=uuid.UUID(int=0), spec_id=self.current))
        self.assertIsNone(self.repository.revision_base(
            object(), project_id=self.project, spec_id=uuid.UUID(int=0)))


if __name__ == "__main__":
    unittest.main()
