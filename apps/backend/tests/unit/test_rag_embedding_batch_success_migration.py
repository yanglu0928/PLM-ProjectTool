from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGEmbeddingBatchSuccessMigrationTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0083_rag_embedding_batch_success"
        )

    def test_success_requires_current_lease_and_deferred_exact_records(self):
        sql = self.migration._batch_guard() + self.migration._RECORD_GUARD
        sql += self.migration._SUCCESS_VALIDATOR
        for required in (
            "OLD.batch_state='RUNNING' AND NEW.batch_state='SUCCEEDED'",
            "job_row.lease_expires_at<=now_at_db",
            "lease_row.state<>'ACTIVE'",
            "NEW.provider_request_ref IS NULL",
            "NEW.provider_request_ref<>batch_row.provider_request_ref",
            "DEFERRABLE INITIALLY DEFERRED",
            "valid_count<>NEW.source_record_count",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_downgrade_refuses_success_or_record_history(self):
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("batch_state IN ('SUCCEEDED','FAILED')", source)
        self.assertIn("rag_embedding_records", source)

    def test_offline_downgrade_refuses_before_ddl(self):
        with patch.object(self.migration.context, "is_offline_mode", return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG Embedding success"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
