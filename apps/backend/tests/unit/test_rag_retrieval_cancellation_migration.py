from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGRetrievalCancellationMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0090_rag_retrieval_cancellation"
        )

    def test_lifecycle_adds_only_bounded_cancelled_terminal(self) -> None:
        sql = self.migration._RUN_STATE_CHECK
        self.assertIn("retrieval_state='CANCELLED'", sql)
        self.assertIn("error_code IS NULL", sql)
        self.assertIn("quality_flags='[]'::jsonb", sql)
        self.assertIn("lock_version=1", sql)

    def test_guard_opens_cancelled_without_weakening_identity(self) -> None:
        sql = self.migration._RUN_GUARD
        self.assertIn(
            "NEW.retrieval_state NOT IN ('SUCCEEDED','FAILED','CANCELLED')", sql,
        )
        self.assertIn("OLD.retrieval_state<>'RUNNING'", sql)
        self.assertIn("NEW.scope<>'PROJECT'", sql)
        self.assertIn("job_row.payload_refs", sql)

    def test_validator_distinguishes_pending_and_claimed_cancel(self) -> None:
        sql = self.migration._TERMINAL_VALIDATOR
        for required in (
            "NEW.state NOT IN ('SUCCEEDED','FAILED','CANCELLED')",
            "job_row.attempt_count=0 AND job_row.fencing_token=0",
            "job_row.lock_version=2",
            "lease_row.lease_id IS NULL AND attempt_row.attempt_id IS NULL",
            "job_row.attempt_count=1 AND job_row.fencing_token=1",
            "job_row.lock_version=3",
            "attempt_row.error_code='JOB_CANCELLED'",
            "lease_row.state IN ('RELEASED','EXPIRED')",
            "NEW.state IN ('SUCCEEDED','FAILED','CANCELLED')",
            "RAG Retrieval cancelled terminal transaction is invalid",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_cancelled_terminal_forbids_result_artifacts(self) -> None:
        sql = self.migration._TERMINAL_VALIDATOR
        for table in (
            "rag_retrieval_candidates", "rag_retrieval_score_parts",
            "rag_context_bundles", "rag_context_items",
        ):
            self.assertIn(
                f"EXISTS (SELECT 1 FROM plm.{table}", sql,
            )

    def test_downgrade_refuses_cancel_history_and_offline_mode(self) -> None:
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn(
            "cancelled RAG Retrieval history prevents downgrade", source,
        )
        with patch.object(self.migration.context, "is_offline_mode",
                          return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG Retrieval"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
