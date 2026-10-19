from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.evidence.infrastructure.orm import EvidenceRow
from plm_assistant.modules.plan.infrastructure.orm import PlanWbsEvidenceRefRow


class PlanWbsEvidenceRefSchemaTests(unittest.TestCase):
    def test_fixed_evidence_scope_project_constraints(self) -> None:
        table = PlanWbsEvidenceRefRow.__table__
        self.assertEqual((table.schema, table.name), ("plm", "pln_item_evidence_refs"))
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"fk_pln_item_evidence__wbs", "fk_pln_item_evidence__scope",
                         "fk_pln_item_evidence__project",
                         "uq_pln_item_evidence__item_evidence",
                         "uq_pln_item_evidence__item_ordinal",
                         "ck_pln_item_evidence__scope_project",
                         "ck_pln_item_evidence__ordinal"} <= names)
        evidence_keys = {constraint.name for constraint in EvidenceRow.__table__.constraints}
        self.assertTrue({"uq_evd_evidence__id_scope",
                         "uq_evd_evidence__id_project"} <= evidence_keys)

    def test_migration_closed_and_history_preserving(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261019_0176_wbs_evidence_ref_foundation")
        self.assertEqual(migration.down_revision, "20261019_0175")
        self.assertIn("WbsEvidenceRef Owner is not installed", migration._GUARDS)
        self.assertIn("WbsEvidenceRef history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline WbsEvidenceRef downgrade"):
                migration.downgrade()
        self.assertIn("WbsEvidenceRef history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
