from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGRetrievalFoundationMigrationTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0088_rag_retrieval_foundation"
        )

    def test_schema_has_frozen_run_candidate_score_and_context_tables(self):
        source = inspect.getsource(self.migration.upgrade)
        for table in (
            "rag_retrieval_runs", "rag_retrieval_query_contents",
            "rag_retrieval_candidates", "rag_retrieval_score_parts",
            "rag_context_bundles", "rag_context_items",
        ):
            with self.subTest(table=table):
                self.assertIn(table, source)

    def test_query_is_ciphertext_only_and_job_payload_is_reference_only(self):
        source = inspect.getsource(self.migration.upgrade)
        guards = self.migration._GUARDS
        for required in (
            "encrypted_payload", "encryption_metadata", "key_provider_ref",
            "query_fingerprint", "plaintext_bytes", "retention_until",
            "jsonb_build_object(\n            'retrieval_run_id'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source + guards)
        for forbidden in ("query_body", "query_text", "golden_answer", "vector_payload"):
            self.assertNotIn(forbidden, source)

    def test_project_index_candidate_and_minimal_context_are_fail_closed(self):
        sql = self.migration._GUARDS
        for required in (
            "project_index.index_state<>'ACTIVE'",
            "run_row.project_id IS DISTINCT FROM NEW.candidate_project_id",
            "record.embedding_state='AVAILABLE'",
            "RAG ContextBundle Owner is not installed",
            "snippet_end-snippet_start<=8192",
            "RAG Retrieval and Context history cannot be truncated",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql + inspect.getsource(self.migration.upgrade))

    def test_filter_allowlist_rejects_arbitrary_keys(self):
        source = inspect.getsource(self.migration.upgrade)
        self.assertIn("metadata_filter - ARRAY", source)
        for key in (
            "document_category", "source_type", "document_version_ref",
            "effective_from", "effective_to", "business",
        ):
            self.assertIn(key, source)
        self.assertNotIn("jsonpath", source.lower())

    def test_downgrade_requires_empty_history_and_is_offline_closed(self):
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("RAG Retrieval history prevents downgrade", source)
        with patch.object(self.migration.context, "is_offline_mode",
                          return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG Retrieval"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
