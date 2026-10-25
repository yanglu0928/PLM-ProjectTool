from __future__ import annotations

import importlib
import unittest
from unittest.mock import patch

from plm_assistant.modules.rag.infrastructure.orm import DocumentChunkRow


class RAGDocumentChunkSchemaTests(unittest.TestCase):
    def test_chunk_has_source_generation_scope_and_full_text_projection(self) -> None:
        table = DocumentChunkRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertEqual([column.name for column in table.primary_key.columns], ["chunk_id"])
        self.assertEqual(len(table.foreign_key_constraints), 5)
        self.assertTrue(any(
            constraint.name == "uq_rag_chunks__source_generation_ordinal"
            for constraint in table.constraints
        ))
        self.assertIsNotNone(table.c.search_vector.computed)
        self.assertIn("to_tsvector", str(table.c.search_vector.computed.sqltext))
        self.assertTrue(any(index.name == "ix_rag_chunks__search_gin"
                            for index in table.indexes))

    def test_guard_rechecks_source_hash_and_retains_history(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0076_rag_document_chunks"
        )
        for required in (
            "record.parse_state,record.result_ref,record.result_sha256",
            "sha256(convert_to(NEW.search_body,'UTF8'))",
            "immutable source or state transition is invalid",
            "source availability is invalid",
            "history cannot be truncated",
        ):
            self.assertIn(required, migration._GUARDS)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0076_rag_document_chunks"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG DocumentChunk"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
