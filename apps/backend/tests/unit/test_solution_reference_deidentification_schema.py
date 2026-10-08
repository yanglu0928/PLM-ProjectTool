from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.solution.infrastructure.orm import (
    ReferenceDeidentificationConfirmationRow,
)


class ReferenceDeidentificationSchemaTests(unittest.TestCase):
    def test_record_has_closed_global_proof_fields(self):
        table = ReferenceDeidentificationConfirmationRow.__table__
        self.assertEqual((table.schema, table.name),
                         ("plm", "sol_reference_deidentification_confirmations"))
        for name in ("source_fingerprint", "source_project_class", "deidentification_class",
                     "applicability", "attestation_statement", "confirmed_by",
                     "confirmed_at", "expires_at", "trace_id"):
            self.assertFalse(table.c[name].nullable)
        self.assertTrue(table.c.revoked_at.nullable)
        names = {constraint.name for constraint in table.constraints}
        self.assertTrue({"fk_sol_reference_deidentification__actor",
                         "ck_sol_reference_deidentification__fingerprint",
                         "ck_sol_reference_deidentification__statement",
                         "ck_sol_reference_deidentification__time"} <= names)

    def test_migration_is_sequential_and_retains_history(self):
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261008_0140_reference_deidentification_confirmation")
        self.assertEqual(migration.down_revision, "20261008_0139")
        self.assertIn("Reference deidentification Owner is not installed", migration.GUARDS)
        self.assertIn("Reference deidentification history cannot be truncated", migration.GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Reference deidentification downgrade"):
                migration.downgrade()
        self.assertIn("Reference deidentification history prevents downgrade",
                      inspect.getsource(migration.downgrade))


if __name__ == "__main__":
    unittest.main()
