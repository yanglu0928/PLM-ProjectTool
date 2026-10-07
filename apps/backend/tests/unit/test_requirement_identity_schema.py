from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.requirement.infrastructure.orm import (
    RequirementPackageMembershipRow,
    RequirementPackageRow,
    RequirementRow,
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


if __name__ == "__main__":
    unittest.main()
