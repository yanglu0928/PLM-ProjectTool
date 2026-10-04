from __future__ import annotations

import importlib
import unittest
from pathlib import Path
from unittest.mock import patch

from pgvector.sqlalchemy import Vector

from plm_assistant.modules.rag.infrastructure.orm import (
    EmbeddingIndexRow,
    EmbeddingRecordRow,
    IndexSourceChunkRow,
)


class RAGEmbeddingRecordSchemaTests(unittest.TestCase):
    def test_dependency_is_pinned_for_production(self) -> None:
        pyproject = Path(__file__).parents[2] / "pyproject.toml"
        self.assertIn('"pgvector==0.5.0"', pyproject.read_text(encoding="utf-8"))

    def test_record_binds_exact_source_model_dimension_and_authorization(self) -> None:
        table = EmbeddingRecordRow.__table__
        self.assertEqual(table.schema, "plm")
        self.assertIsInstance(table.c.embedding_vector.type, Vector)
        self.assertIsNone(table.c.embedding_vector.type.dim)
        self.assertEqual(len(table.foreign_key_constraints), 4)
        names = {constraint.name for constraint in table.foreign_key_constraints}
        self.assertEqual(names, {
            "fk_rag_embeddings__project",
            "fk_rag_embeddings__index_model_dimension",
            "fk_rag_embeddings__source_chunk",
            "fk_rag_embeddings__egress_authorization",
        })
        checks = {constraint.name: str(constraint.sqltext)
                  for constraint in table.constraints
                  if getattr(constraint, "sqltext", None) is not None}
        self.assertIn("embedding_dimension IN (768,1024)", checks["ck_rag_embeddings__dimension"])
        self.assertIn("vector_dims", checks["ck_rag_embeddings__dimension"])

    def test_controlled_hnsw_families_and_available_uniqueness_are_registered(self) -> None:
        indexes = {index.name: index for index in EmbeddingRecordRow.__table__.indexes}
        self.assertEqual(
            {name for name in indexes if name.endswith("_hnsw")},
            {"ix_rag_embeddings__v768_hnsw", "ix_rag_embeddings__v1024_hnsw"},
        )
        for dimension in (768, 1024):
            index = indexes[f"ix_rag_embeddings__v{dimension}_hnsw"]
            self.assertEqual(index.dialect_options["postgresql"]["using"], "hnsw")
            self.assertEqual(index.dialect_options["postgresql"]["with"], {
                "m": 32,
                "ef_construction": 200,
            })
            self.assertIn(str(dimension), str(index.expressions[0]))
        self.assertTrue(indexes["uq_rag_embeddings__index_chunk_available"].unique)

    def test_parent_tables_publish_composite_reference_keys(self) -> None:
        index_names = {constraint.name for constraint in EmbeddingIndexRow.__table__.constraints}
        source_names = {constraint.name for constraint in IndexSourceChunkRow.__table__.constraints}
        self.assertIn("uq_rag_indexes__id_model_dimension", index_names)
        self.assertIn("uq_rag_index_sources__chunk_fingerprint", source_names)

    def test_guard_requires_build_owner_and_build_authorization(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0078_rag_embedding_record_hnsw"
        )
        for required in (
            "index_row.index_state<>'BUILDING'",
            "Build Owner is absent",
            "authorization_row.ai_model_id<>NEW.embedding_model_ref",
            "('INDEX_BUILD','INDEX_REBUILD')",
            "EmbeddingRecord history cannot be truncated",
        ):
            self.assertIn(required, migration._GUARDS)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0078_rag_embedding_record_hnsw"
        )
        with patch.object(migration.context, "is_offline_mode", return_value=True), \
                patch.object(migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG EmbeddingRecord"):
                migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
