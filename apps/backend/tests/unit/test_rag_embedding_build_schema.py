from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingBuildBatchRow,
    EmbeddingBuildRow,
)


class RAGEmbeddingBuildSchemaTests(unittest.TestCase):
    def test_build_has_unique_index_and_job_owner(self) -> None:
        table = EmbeddingBuildRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(len(table.foreign_key_constraints), 4)
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("uq_rag_builds__index", names)
        self.assertIn("uq_rag_builds__job", names)
        self.assertIn("ck_rag_builds__fingerprints", names)

    def test_each_batch_has_one_authorization_and_contiguous_source_shape(self) -> None:
        table = EmbeddingBuildBatchRow.__table__
        self.assertEqual(len(table.foreign_key_constraints), 2)
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("uq_rag_build_batches__ordinal", names)
        self.assertIn("uq_rag_build_batches__source_start", names)
        self.assertIn("uq_rag_build_batches__authorization", names)
        self.assertIn("ck_rag_build_batches__lifecycle", names)

    def test_guards_seal_plan_job_and_per_batch_authorization(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0079_rag_embedding_build_plan"
        )
        for required in (
            "job_row.owner_module<>'rag'",
            "job_row.job_type<>'RAG_INDEX_BUILD'",
            "job_row.max_attempts<>1",
            "batch partition is incomplete",
            "batch source fingerprint is invalid",
            "authz.max_retry_attempts<>1",
            "authz.payload_fingerprint<>batch.payload_fingerprint",
            "authz.allowed_data_categories ? chunk.source_type",
            "authorization set fingerprint is invalid",
            "DEFERRABLE INITIALLY DEFERRED",
        ):
            self.assertIn(required, migration._GUARDS)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0079_rag_embedding_build_plan"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG EmbeddingBuild"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
