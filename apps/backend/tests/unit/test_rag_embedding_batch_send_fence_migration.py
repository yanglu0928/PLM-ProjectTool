from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGEmbeddingBatchSendFenceMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions.20261004_0082_rag_embedding_batch_send_fence"
        )

    def test_send_fence_rechecks_every_mutable_authority(self) -> None:
        for required in (
            "OLD.batch_state='PENDING' AND NEW.batch_state='RUNNING'",
            "job_row.lease_expires_at<=now_at_db",
            "authz_row.authorization_state<>'AUTHORIZED'",
            "authz_row.valid_until<=now_at_db",
            "provider_row.provider_state<>'ACTIVE'",
            "provider_row.current_config_version_ref",
            "config_row.can_embedding IS DISTINCT FROM true",
            "model_row.model_state<>'AVAILABLE'",
            "source_is_current IS DISTINCT FROM true",
            "current_source_fingerprint IS DISTINCT FROM NEW.source_batch_fingerprint",
            "NEW.send_fencing_token<>1",
        ):
            self.assertIn(required, self.migration._BATCH_GUARD)

    def test_downgrade_refuses_fenced_history(self) -> None:
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("send_fencing_token IS NOT NULL", source)
        previous = self.migration._previous_batch_guard()
        self.assertIn("RAG_PROVIDER_OUTCOME_UNKNOWN", previous)
        self.assertNotIn("send fence proof", previous)

    def test_offline_downgrade_refuses_before_ddl(self) -> None:
        with patch.object(self.migration.context, "is_offline_mode", return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG EmbeddingBuildBatch"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
