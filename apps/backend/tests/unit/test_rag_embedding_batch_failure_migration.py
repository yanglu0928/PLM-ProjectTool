from __future__ import annotations

import importlib
import unittest


class RAGEmbeddingBatchFailureMigrationTests(unittest.TestCase):
    def test_revision_and_known_failure_guards(self):
        migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0084_rag_embedding_batch_failure"
        )
        self.assertEqual(migration.revision, "20261004_0084")
        self.assertEqual(migration.down_revision, "20261004_0083")
        build = migration._build_guard()
        batch = migration._batch_guard()
        for token in (
            "RAG_PROVIDER_REQUEST_REJECTED",
            "RAG_EMBEDDING_RESPONSE_INVALID",
            "lease_row.state='RELEASED'",
        ):
            self.assertIn(token, build)
            self.assertIn(token, batch)
        self.assertIn("RAG_BUILD_ABORTED_AFTER_BATCH_FAILURE", batch)
        self.assertIn("NEW.provider_request_ref !~ '^sha256:", batch)
        self.assertIn("OLD.batch_state='RUNNING' AND NEW.batch_state='SUCCEEDED'", batch)


if __name__ == "__main__":
    unittest.main()
