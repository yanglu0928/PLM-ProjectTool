from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingIndexRow,
    IndexSourceChunkRow,
)


class RAGEmbeddingIndexSchemaTests(unittest.TestCase):
    def test_index_identity_model_dimension_and_active_uniqueness_are_registered(self) -> None:
        table = EmbeddingIndexRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(
            [column.name for column in table.primary_key.columns],
            ["embedding_index_id"],
        )
        self.assertEqual(len(table.foreign_key_constraints), 3)
        self.assertTrue(any(
            constraint.name == "uq_rag_indexes__purpose_version"
            for constraint in table.constraints
        ))
        active = next(index for index in table.indexes
                      if index.name == "uq_rag_indexes__active_purpose")
        self.assertTrue(active.unique)
        self.assertIn("ACTIVE", str(active.dialect_options["postgresql"]["where"]))

    def test_exact_source_membership_is_owned_and_unique(self) -> None:
        table = IndexSourceChunkRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual(len(table.foreign_key_constraints), 3)
        names = {constraint.name for constraint in table.constraints}
        self.assertIn("uq_rag_index_sources__ordinal", names)
        self.assertIn("uq_rag_index_sources__chunk", names)

    def test_guard_seals_creation_transaction_and_closes_state_changes(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0077_rag_embedding_index_foundation"
        )
        for required in (
            "state changes are closed until build ownership is installed",
            "model_kind IS DISTINCT FROM 'EMBEDDING'",
            "index_row.created_xid<>txid_current()",
            "chunk_row.chunk_state<>'ACTIVE'",
            "source snapshot count or fingerprint is invalid",
            "DEFERRABLE INITIALLY DEFERRED",
        ):
            self.assertIn(required, migration._GUARDS)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0077_rag_embedding_index_foundation"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG EmbeddingIndex"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
