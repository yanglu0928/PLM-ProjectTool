from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingIndexValidationRow,
)


class RAGEmbeddingIndexValidationSchemaTests(unittest.TestCase):
    def test_validation_has_one_index_and_build_owner(self) -> None:
        table = EmbeddingIndexValidationRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(len(table.foreign_key_constraints), 4)
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("uq_rag_index_validations__index", names)
        self.assertIn("uq_rag_index_validations__build", names)
        self.assertIn("ck_rag_index_validations__counts", names)
        self.assertIn("ck_rag_index_validations__result", names)

    def test_guard_recomputes_complete_records_batches_catalog_and_recall(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0085_rag_embedding_index_validation"
        )
        for required in (
            "index_row.index_state<>'BUILDING'",
            "build_row.build_state<>'RUNNING'",
            "job_row.job_type<>'RAG_INDEX_BUILD'",
            "actual_missing_count",
            "actual_duplicate_count",
            "actual_record_set_fingerprint",
            "pg_indexes",
            "actual_hnsw_catalog_fingerprint",
            "expected_observed_recall",
            "expected_validation_fingerprint",
            "lease_row.lease_expires_at<=clock_timestamp()",
            "NEW.completed_at := statement_timestamp()",
            "cannot pass incomplete history",
            "history is immutable",
            "history cannot be truncated",
        ):
            self.assertIn(required, migration._GUARDS)
        columns = str(EmbeddingIndexValidationRow.__table__.c)
        self.assertIn("hnsw_ef_search", columns)
        self.assertIn("hnsw_iterative_scan", columns)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0085_rag_embedding_index_validation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(
                RuntimeError, "offline RAG EmbeddingIndexValidation",
            ):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
