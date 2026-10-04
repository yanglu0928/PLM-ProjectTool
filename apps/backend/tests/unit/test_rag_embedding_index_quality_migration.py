from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGEmbeddingIndexQualityMigrationTests(unittest.TestCase):
    def setUp(self):
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0087_rag_embedding_index_quality"
        )

    def test_quality_thresholds_and_safe_evidence_shape_are_fixed(self):
        source = inspect.getsource(self.migration.upgrade)
        for required in (
            "minimum_classification_basis_points=9000",
            "minimum_exact_citation_basis_points=9800",
            "dataset_fingerprint",
            "isolation_attestation_fingerprint",
            "evaluation_artifact_fingerprint",
            "out_of_scope_citation_count=0",
            "failure_closure_pass",
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in ("query_body", "golden_answer", "customer_body"):
            self.assertNotIn(forbidden, source)

    def test_active_and_retired_transitions_require_deferred_result(self):
        sql = self.migration._index_guard()
        sql += self.migration._ACTIVATION_VALIDATOR
        for required in (
            "OLD.index_state='READY' AND NEW.index_state='ACTIVE'",
            "OLD.index_state='ACTIVE' AND NEW.index_state='RETIRED'",
            "RAG Index activation transaction is incomplete",
            "RAG Index retirement transaction is incomplete",
            "DEFERRABLE INITIALLY DEFERRED",
            "authorization_state<>'AUTHORIZED'",
            "model_state IS DISTINCT FROM 'AVAILABLE'",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_history_is_immutable_and_downgrade_is_closed(self):
        guards = self.migration._EVIDENCE_GUARDS
        self.assertIn("quality history is retained", guards)
        self.assertIn("activation history is retained", guards)
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("quality history prevents downgrade", source)
        self.assertIn("index_state IN ('ACTIVE','RETIRED')", source)

    def test_offline_downgrade_refuses_before_ddl(self):
        with patch.object(self.migration.context, "is_offline_mode",
                          return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG Index quality"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
