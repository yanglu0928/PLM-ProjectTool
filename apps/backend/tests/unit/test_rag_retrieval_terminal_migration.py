from __future__ import annotations

import importlib
import inspect
import unittest
from unittest.mock import patch


class RAGRetrievalTerminalMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.migration = importlib.import_module(
            "plm_assistant.migrations.versions."
            "20261004_0089_rag_retrieval_terminal"
        )

    def test_lifecycle_is_single_generation_and_has_bounded_failures(self) -> None:
        lifecycle = self.migration._RUN_STATE_CHECK
        for required in (
            "retrieval_state='RUNNING'",
            "retrieval_state='SUCCEEDED'",
            "retrieval_state='FAILED'",
            "CANDIDATE_SHORTFALL",
            "RAG_NO_AUTHORIZED_CANDIDATES",
            "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE",
            "RAG_RETRIEVAL_LEASE_EXPIRED",
            "lock_version=1",
        ):
            with self.subTest(required=required):
                self.assertIn(required, lifecycle)
        self.assertNotIn("CANCELLED", lifecycle)

    def test_run_guard_preserves_identity_and_only_opens_one_transition(self) -> None:
        sql = self.migration._RUN_GUARD
        for required in (
            "OLD.retrieval_state<>'RUNNING'",
            "NEW.retrieval_state NOT IN ('SUCCEEDED','FAILED')",
            "NEW.lock_version<>1",
            "NEW.retrieval_policy_ref<>'fts.project.v1'",
            "NEW.rerank_policy_ref<>'none.v1'",
            "project_index.index_state<>'ACTIVE'",
            "RAG RetrievalRun terminal transition is invalid",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_deferred_validator_covers_all_atomic_aggregate_members(self) -> None:
        sql = self.migration._TERMINAL_VALIDATOR
        for required in (
            "DEFERRABLE INITIALLY DEFERRED",
            "AFTER UPDATE ON plm.rag_retrieval_runs",
            "AFTER UPDATE ON plm.job_jobs",
            "AFTER INSERT ON plm.rag_retrieval_candidates",
            "AFTER INSERT ON plm.rag_retrieval_score_parts",
            "AFTER INSERT ON plm.rag_context_bundles",
            "AFTER INSERT ON plm.rag_context_items",
            "job_row.lock_version<>2",
            "lease_row.state<>'EXPIRED'",
            "lease_row.state<>'RELEASED'",
            "score_count<>candidate_count*2",
            "bundle_count<>1 OR item_count<>candidate_count",
            "bundle_row.context_policy_ref<>'project-documents.v1'",
            "candidate.authorization_snapshot_fingerprint",
        ):
            with self.subTest(required=required):
                self.assertIn(required, sql)

    def test_failure_cannot_publish_partial_candidate_or_context_history(self) -> None:
        sql = self.migration._TERMINAL_VALIDATOR
        self.assertIn(
            "candidate_count<>0 OR score_count<>0\n"
            "           OR bundle_count<>0 OR item_count<>0",
            sql,
        )
        self.assertIn(
            "RAG Retrieval result cannot commit before terminal state", sql,
        )

    def test_downgrade_refuses_terminal_history_and_offline_mode(self) -> None:
        source = inspect.getsource(self.migration.downgrade)
        self.assertIn("terminal RAG Retrieval history prevents downgrade", source)
        with patch.object(self.migration.context, "is_offline_mode",
                          return_value=True), \
                patch.object(self.migration.op, "execute") as execute:
            with self.assertRaisesRegex(RuntimeError, "offline RAG Retrieval"):
                self.migration.downgrade()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
