from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGEmbeddingIndexReadyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0086_rag_embedding_index_ready"
        )

    def test_success_is_bidirectionally_guarded_and_deferred(self):
        sql = self.migration._build_guard()
        sql += self.migration._index_guard()
        sql += self.migration._SUCCESS_VALIDATORS
        for required in (
            "OLD.build_state='RUNNING'",
            "NEW.build_state='SUCCEEDED'",
            "OLD.index_state='BUILDING' AND NEW.index_state='READY'",
            "validation.validation_state='PASSED'",
            "trg_rag_embedding_build_success",
            "trg_rag_embedding_job_success",
            "DEFERRABLE INITIALLY DEFERRED",
            "validated success transaction is incomplete",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_failed_validation_has_exact_terminal_error(self):
        sql = self.migration._build_guard()
        self.assertIn("RAG_INDEX_TECHNICAL_VALIDATION_FAILED", sql)
        self.assertIn("validation.validation_state='FAILED'", sql)
        self.assertIn("batch.batch_state<>'SUCCEEDED'", sql)

    def test_downgrade_refuses_ready_history(self):
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("build_state='SUCCEEDED'", source)
        self.assertIn("index_state='READY'", source)
        self.assertIn("RAG_INDEX_TECHNICAL_VALIDATION_FAILED", source)
        self.assertIn("validated RAG READY history prevents downgrade", source)

    def test_offline_downgrade_refuses_before_ddl(self):
        with patch.object(self.migration.context, "is_offline_mode",
                          return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG Embedding READY"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
