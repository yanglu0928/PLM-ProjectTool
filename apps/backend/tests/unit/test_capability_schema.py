from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.capability.infrastructure.orm import (
    CapabilityBaselineRow,
    CapabilityBaselineVersionRow,
    CapabilityItemDocumentRefRow,
    CapabilityItemEvidenceRefRow,
    CapabilityItemRow,
)


class CapabilityFoundationSchemaTests(unittest.TestCase):
    def test_two_roots_and_three_owned_tables_are_global_and_bounded(self) -> None:
        tables = (
            CapabilityBaselineRow.__table__, CapabilityBaselineVersionRow.__table__,
            CapabilityItemRow.__table__, CapabilityItemDocumentRefRow.__table__,
            CapabilityItemEvidenceRefRow.__table__,
        )
        self.assertEqual(
            [table.name for table in tables],
            ["cap_baselines", "cap_baseline_versions", "cap_items",
             "cap_item_document_refs", "cap_item_evidence_refs"],
        )
        for table in tables:
            with self.subTest(table=table.name):
                self.assertEqual(table.schema, "plm")
                self.assertNotIn("project_id", table.c)
        self.assertEqual(
            CapabilityBaselineRow.__table__.c.current_approved_version_ref.nullable,
            True,
        )
        self.assertIn("ARRAY", str(CapabilityItemRow.__table__.c.prerequisites.type))

    def test_frozen_identity_version_item_and_source_constraints_exist(self) -> None:
        names = {
            constraint.name
            for table in (
                CapabilityBaselineRow.__table__, CapabilityBaselineVersionRow.__table__,
                CapabilityItemRow.__table__, CapabilityItemDocumentRefRow.__table__,
                CapabilityItemEvidenceRefRow.__table__,
            )
            for constraint in table.constraints
        }
        for required in (
            "uq_cap_baselines__code", "fk_cap_baselines__approved_version",
            "uq_cap_versions__baseline_no", "fk_cap_versions__supersedes",
            "uq_cap_items__version_stable", "uq_cap_items__version_code",
            "fk_cap_item_docs__document_version", "fk_cap_item_evidence__evidence",
        ):
            with self.subTest(required=required):
                self.assertIn(required, names)

    def test_migration_closes_owner_and_requires_complete_global_sources(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0091_capability_foundation"
        )
        self.assertEqual(migration.down_revision, "20261004_0090")
        sql = migration._GUARDS
        for required in (
            "Capability Owner is not installed",
            "Capability BaselineVersion declared counts are incomplete",
            "capability-source-set.v1",
            "Capability source collection fingerprint is invalid",
            "CapabilityItem requires document and evidence",
            "document_category<>'STANDARD_CAPABILITY'",
            "e.eligibility_state<>'ELIGIBLE'",
            "Capability history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_downgrade_is_offline_closed_and_preserves_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261005_0091_capability_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline Capability"):
                migration.downgrade()
        execute.assert_not_called()
        self.assertIn("Capability history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
