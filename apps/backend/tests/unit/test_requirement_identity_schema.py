from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.requirement.infrastructure.orm import (
    RequirementCreateResultRow,
    RequirementPackageMembershipRow,
    RequirementPackageCommandResultRow,
    RequirementDecisionEvidenceRefRow,
    RequirementPackageCreateResultRow,
    RequirementPackageRow,
    RequirementRow,
    RequirementStateDecisionRow,
)


class RequirementIdentitySchemaTests(unittest.TestCase):
    def test_identity_and_membership_tables_are_project_scoped(self) -> None:
        tables = (
            RequirementPackageRow.__table__,
            RequirementRow.__table__,
            RequirementPackageMembershipRow.__table__,
        )
        self.assertEqual(
            [table.name for table in tables],
            ["req_packages", "req_requirements", "req_package_memberships"],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual(table.schema, "plm")
                self.assertIn("project_id", table.c)
        self.assertTrue(
            RequirementRow.__table__.c.current_approved_version_ref.nullable
        )
        self.assertEqual(
            [
                RequirementPackageCreateResultRow.__table__.name,
                RequirementCreateResultRow.__table__.name,
                RequirementPackageCommandResultRow.__table__.name,
            ],
            ["req_package_create_results", "req_requirement_create_results",
             "req_package_command_results"],
        )

    def test_same_project_code_and_membership_constraints_exist(self) -> None:
        names = {
            constraint.name
            for table in (
                RequirementPackageRow.__table__,
                RequirementRow.__table__,
                RequirementPackageMembershipRow.__table__,
            )
            for constraint in table.constraints
        }
        for required in (
            "uq_req_packages__id_project",
            "uq_req_requirements__project_code",
            "uq_req_package_memberships__package_requirement",
            "fk_req_package_memberships__package",
            "fk_req_package_memberships__requirement",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_foundation_guard_keeps_owner_and_version_pointer_closed(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0111_requirement_identity_foundation"
        )
        self.assertEqual(migration.down_revision, "20261007_0110")
        for required in (
            "Requirement identity Owner is not installed",
            "RequirementPackage initial state is invalid",
            "Requirement initial state is invalid",
            "NEW.current_approved_version_ref IS NOT NULL",
            "Requirement identity history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, migration._GUARDS)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0111_requirement_identity_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Requirement identity"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn(
            "Requirement identity history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )

    def test_create_result_delta_is_immutable_and_history_safe(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0112_requirement_create_results"
        )
        self.assertEqual(migration.down_revision, "20261007_0111")
        for required in (
            "Requirement create result history is immutable",
            "Requirement create result history cannot be truncated",
            "Requirement create result does not match initial identity",
        ):
            self.assertIn(required, migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement create"):
                migration.downgrade()
        self.assertIn(
            "Requirement create result history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )

    def test_package_mutation_delta_opens_only_package_and_membership_owner(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261007_0113_requirement_package_mutations"
        )
        self.assertEqual(migration.down_revision, "20261007_0112")
        for required in (
            "RequirementPackage mutation is invalid",
            "Requirement identity Owner is not installed",
            "RequirementPackage membership history cannot be rewritten",
            "RequirementPackage command result history is immutable",
            "RequirementPackage command result does not match current root",
        ):
            self.assertIn(required, migration._MUTATION_GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement Package"):
                migration.downgrade()
        self.assertIn("mutation history prevents downgrade", inspect.getsource(migration.downgrade))

    def test_state_decision_foundation_is_evidence_backed_and_owner_closed(self) -> None:
        self.assertEqual(RequirementStateDecisionRow.__table__.schema, "plm")
        self.assertEqual(RequirementDecisionEvidenceRefRow.__table__.schema, "plm")
        names = {constraint.name for table in (
            RequirementStateDecisionRow.__table__,
            RequirementDecisionEvidenceRefRow.__table__,
        ) for constraint in table.constraints}
        for required in (
            "uq_req_state_decisions__requirement_version",
            "fk_req_state_decisions__requirement",
            "fk_req_decision_evidence_refs__decision",
            "fk_req_decision_evidence_refs__evidence",
        ):
            self.assertIn(required, names)
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261007_0114_requirement_state_decisions"
        )
        self.assertEqual(migration.down_revision, "20261007_0113")
        self.assertIn("Owner is not installed", migration._GUARDS)
        self.assertIn("history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Requirement state-decision"):
                migration.downgrade()
        self.assertIn("history prevents downgrade", inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
