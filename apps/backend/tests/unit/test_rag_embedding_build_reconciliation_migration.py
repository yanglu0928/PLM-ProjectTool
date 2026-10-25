from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGEmbeddingBuildReconciliationMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0081_rag_embedding_build_reconciliation"
        )

    def test_reconciliation_requires_expired_job_and_closes_batches(self) -> None:
        for required in (
            "job_row.state<>'FAILED'",
            "lease_row.state<>'EXPIRED'",
            "RAG_BUILD_LEASE_EXPIRED",
            "RAG_PROVIDER_OUTCOME_UNKNOWN",
            "OLD.batch_state='PENDING'",
            "OLD.batch_state='RUNNING'",
            "batch.batch_state IN ('PENDING','RUNNING')",
            "DEFERRABLE INITIALLY DEFERRED",
        ):
            self.assertIn(required, self.migration._GUARDS)

    def test_downgrade_retains_reconciled_history(self) -> None:
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("build_state='FAILED'", source)
        self.assertIn("RAG_PROVIDER_OUTCOME_UNKNOWN", source)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        with patch.object(self.migration.context, "is_offline_mode", return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG EmbeddingBuild reconciliation"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
