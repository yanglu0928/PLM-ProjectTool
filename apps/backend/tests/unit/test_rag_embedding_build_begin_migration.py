from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGEmbeddingBuildBeginMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0080_rag_embedding_build_begin"
        )

    def test_upgrade_requires_current_single_attempt_lease_and_atomic_states(self) -> None:
        for required in (
            "job_row.owner_module<>'rag'",
            "job_row.job_type<>'RAG_INDEX_BUILD'",
            "job_row.max_attempts<>1",
            "job_row.attempt_count<>1",
            "job_row.fencing_token<>1",
            "lease_row.state<>'ACTIVE'",
            "index_row.index_state<>'BUILDING'",
            "DEFERRABLE INITIALLY DEFERRED",
            "batch_row.batch_state<>'SUCCEEDED'",
            "batch_row.egress_authorization_ref<>NEW.egress_authorization_ref",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.migration._GUARDS)

    def test_downgrade_refuses_started_or_vector_history(self) -> None:
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("build_state<>'PLANNED'", source)
        self.assertIn("index_state<>'PLANNED'", source)
        self.assertIn("rag_embedding_records", source)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        with patch.object(self.migration.context, "is_offline_mode", return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG EmbeddingBuild begin"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
