from __future__ import annotations

import importlib
import inspect
import io
import unittest
from contextlib import redirect_stdout

from alembic import command
from sqlalchemy.engine import URL

from plm_assistant.modules.output.infrastructure.orm import (
    OutputContextEvidenceRefRow,
    OutputContextSnapshotRow,
    OutputContextSourceRefRow,
    OutputRequestRow,
)
from plm_assistant.modules.platform.infrastructure.migration import (
    create_migration_config,
)


class OutputRequestSchemaMigrationTests(unittest.TestCase):
    def test_orm_maps_frozen_out01_aggregate_and_owned_context_rows(self) -> None:
        expected = {
            "plm.out_requests": OutputRequestRow,
            "plm.out_context_snapshots": OutputContextSnapshotRow,
            "plm.out_context_source_refs": OutputContextSourceRefRow,
            "plm.out_context_evidence_refs": OutputContextEvidenceRefRow,
        }
        for table_name, row_type in expected.items():
            self.assertEqual(table_name, row_type.__table__.fullname)
            self.assertIn("project_id", row_type.__table__.c)

        request_columns = set(OutputRequestRow.__table__.c.keys())
        self.assertTrue({
            "output_request_id", "project_id", "requested_by", "output_type",
            "template_version_id", "input_fingerprint", "policy_version",
            "context_snapshot_ref", "request_state", "job_ref",
            "current_execution_ref", "idempotency_key", "trace_id",
            "generation_no", "lock_version", "retention_due_at",
        }.issubset(request_columns))
        self.assertFalse({"api_key", "absolute_path", "source_text", "output_bytes"}
                         & request_columns)

    def test_request_has_project_scope_and_live_generation_guard(self) -> None:
        table = OutputRequestRow.__table__
        generation_index = next(
            index for index in table.indexes
            if index.name == "uq_out_requests__generation_live"
        )
        self.assertTrue(generation_index.unique)
        self.assertEqual(
            ["project_id", "output_type", "input_fingerprint", "template_version_id",
             "policy_version", "generation_no"],
            [column.name for column in generation_index.columns],
        )
        self.assertIn("SUCCEEDED", str(generation_index.dialect_options["postgresql"]["where"]))
        self.assertTrue(any(
            {"project_id", "requested_by", "idempotency_key"}
            == {column.name for column in constraint.columns}
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        ))

    def test_context_is_immutable_shaped_and_fixed_version_references_are_ordered(self) -> None:
        snapshot = OutputContextSnapshotRow.__table__
        self.assertTrue({
            "context_snapshot_id", "output_request_id", "project_id",
            "context_schema_version", "context_payload", "context_fingerprint",
        }.issubset(snapshot.c.keys()))
        for row_type in (OutputContextSourceRefRow, OutputContextEvidenceRefRow):
            table = row_type.__table__
            self.assertTrue({
                "context_snapshot_id", "output_request_id", "project_id",
                "ref_ordinal", "scope", "owner_module", "object_type",
                "object_id", "version_id",
            }.issubset(table.c.keys()))
            self.assertTrue(any(
                {"context_snapshot_id", "ref_ordinal"}
                == {column.name for column in constraint.columns}
                for constraint in table.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            ))

    def test_migration_is_append_only_and_refuses_data_loss_downgrade(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261026_0220_output_request_context"
        )
        self.assertEqual(migration.revision, "20261026_0220")
        self.assertEqual(migration.down_revision, "20261026_0210")
        upgrade = inspect.getsource(migration.upgrade)
        self.assertIn("uq_out_requests__generation_live", upgrade)
        self.assertIn("deferrable=True", upgrade)
        self.assertIn("out_context_source_refs", upgrade)
        self.assertIn("out_context_evidence_refs", upgrade)
        self.assertIn("guard_output_context_immutable", upgrade)
        self.assertIn("BEFORE UPDATE OR DELETE", upgrade)
        self.assertIn("fk_out_requests__template_version", upgrade)
        downgrade = inspect.getsource(migration.downgrade)
        self.assertIn("SELECT EXISTS", downgrade)
        self.assertIn("OutputRequest data prevents safe downgrade", downgrade)
        self.assertIn("offline OutputRequest downgrade is disabled", downgrade)

    def test_alembic_offline_upgrade_renders_all_out01_tables_and_guards(self) -> None:
        config = create_migration_config(URL.create(
            "postgresql+psycopg", username="offline", password="offline",
            host="127.0.0.1", database="offline",
        ))
        sql = io.StringIO()
        with redirect_stdout(sql):
            command.upgrade(
                config, "20261026_0210:20261026_0220", sql=True
            )
        rendered = sql.getvalue()
        for expected in (
            "CREATE TABLE plm.out_requests",
            "CREATE TABLE plm.out_context_snapshots",
            "CREATE TABLE plm.out_context_source_refs",
            "CREATE TABLE plm.out_context_evidence_refs",
            "uq_out_requests__generation_live",
            "fk_out_requests__context_snapshot",
            "BEFORE UPDATE OR DELETE",
            "UPDATE plm.alembic_version",
        ):
            self.assertIn(expected, rendered)


if __name__ == "__main__":
    unittest.main()
