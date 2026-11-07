from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch

from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextSnapshotRow,
    OutputRequestRow,
)


class OutputRequestContextSchemaTests(unittest.TestCase):
    def test_context_is_project_scoped_minimal_and_immutable_by_contract(self) -> None:
        context = OutputContextSnapshotRow.__table__
        names = {constraint.name for constraint in context.constraints}
        self.assertEqual((context.schema, context.name), ("plm", "out_context_snapshots"))
        self.assertTrue({
            "uq_out_context_snapshots__id_project",
            "fk_out_context_snapshots__project",
            "fk_out_context_snapshots__creator",
            "ck_out_context_snapshots__sources",
            "ck_out_context_snapshots__payload",
            "ck_out_context_snapshots__fingerprint",
        } <= names)
        self.assertEqual(context.c.context_fingerprint.type.length, None)

    def test_request_binds_project_context_versions_and_generation_idempotency(self) -> None:
        request = OutputRequestRow.__table__
        names = {constraint.name for constraint in request.constraints}
        self.assertEqual((request.schema, request.name), ("plm", "out_output_requests"))
        self.assertTrue({
            "uq_out_output_requests__id_project",
            "uq_out_output_requests__project_idempotency",
            "uq_out_output_requests__generation_identity",
            "fk_out_output_requests__project",
            "fk_out_output_requests__requester",
            "fk_out_output_requests__context_project",
            "ck_out_output_requests__type",
            "ck_out_output_requests__state",
            "ck_out_output_requests__sources",
            "ck_out_output_requests__fingerprint",
        } <= names)
        self.assertTrue({
            "template_version_ref",
            "source_version_refs",
            "output_policy_ref",
            "plugin_operation",
            "context_snapshot_id",
            "input_fingerprint",
            "generation_no",
            "job_ref",
            "current_execution_ref",
        } <= set(request.c.keys()))

    def test_migration_is_additive_closed_and_refuses_history_loss(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261102_0220_output_request_context")
        self.assertEqual(migration.down_revision, "20261026_0210")
        self.assertIn("OutputRequest Owner is not installed", migration._GUARDS)
        self.assertIn("Output foundation history cannot be truncated", migration._GUARDS)
        with patch.object(migration.context, "is_offline_mode", return_value=True):
            with self.assertRaisesRegex(RuntimeError, "offline Output foundation downgrade"):
                migration.downgrade()
        self.assertIn(
            "Output foundation history prevents downgrade",
            inspect.getsource(migration.downgrade),
        )


if __name__ == "__main__":
    unittest.main()
