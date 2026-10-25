from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

from plm_assistant.modules.plan.application.plan_review_readiness import (
    PlanReviewReadinessDenied, PlanVersionReviewLock,
    PlanVersionReviewReadinessQuery, PlanVersionReviewReadinessService,
    PlanVersionReviewTerminalQuery,
)
from plm_assistant.modules.plan.application.read_plan_version import PlanVersionSnapshotView
from plm_assistant.modules.plan.application.validate_plan_version_contract import (
    PlanVersionCoverageSummary, PlanVersionValidationReport,
)


def _snapshot(*, state: str = "DRAFT", review_ref=None, round_ref=None) -> PlanVersionSnapshotView:
    return PlanVersionSnapshotView(
        plan_version_id=uuid.uuid4(), plan_id=uuid.uuid4(), project_id=uuid.uuid4(),
        version_no=2, version_state=state, created_by=uuid.uuid4(),
        created_at=datetime.now(timezone.utc), supersedes_version_ref=None,
        review_ref=review_ref, review_round_ref=round_ref, snapshot={"wbs_items": []},
    )


class PlanVersionReviewReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tx = object()
        self.snapshot = _snapshot()
        self.query = PlanVersionReviewReadinessQuery(
            b"s" * 32, uuid.uuid4(), self.snapshot.project_id,
            self.snapshot.plan_id, self.snapshot.plan_version_id,
        )
        self.repository = Mock()
        self.repository.lock_current.return_value = PlanVersionReviewLock(
            self.snapshot, self.snapshot.plan_version_id)
        self.evaluator = Mock()
        self.report = PlanVersionValidationReport(
            valid=True, blocking_issues=(), warnings=(),
            coverage_summary=PlanVersionCoverageSummary(0, 0, 0, 0, 0, 0, 0, 0),
            checked_at=datetime.now(timezone.utc),
        )
        self.evaluator.evaluate_snapshot_in_transaction.return_value = (b"f" * 32, self.report)
        self.service = PlanVersionReviewReadinessService(
            repository=self.repository, evaluator=self.evaluator)

    def test_returns_fixed_current_proof_without_committing_or_changing_transaction(self) -> None:
        proof = self.service.prove_in_transaction(self.tx, query=self.query)
        self.assertEqual(proof.plan_version_id, self.snapshot.plan_version_id)
        self.assertEqual(proof.project_id, self.snapshot.project_id)
        self.assertEqual(proof.plan_id, self.snapshot.plan_id)
        self.assertEqual(proof.version_no, self.snapshot.version_no)
        self.assertEqual(proof.content_fingerprint, b"f" * 32)
        self.repository.lock_current.assert_called_once_with(
            self.tx, project_id=self.query.project_id, plan_id=self.query.plan_id,
            plan_version_id=self.query.plan_version_id)
        self.evaluator.evaluate_snapshot_in_transaction.assert_called_once_with(
            self.tx, snapshot=self.snapshot, session_token=self.query.session_token,
            trace_id=self.query.trace_id)

    def test_nonlatest_wrong_state_wrong_binding_or_invalid_report_fails_closed(self) -> None:
        self.repository.lock_current.return_value = PlanVersionReviewLock(
            self.snapshot, uuid.uuid4())
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_in_transaction(self.tx, query=self.query)
        self.evaluator.evaluate_snapshot_in_transaction.assert_not_called()

        self.repository.lock_current.return_value = PlanVersionReviewLock(
            _snapshot(state="IN_REVIEW"), self.query.plan_version_id)
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_in_transaction(self.tx, query=self.query)

        self.repository.lock_current.return_value = PlanVersionReviewLock(
            self.snapshot, self.query.plan_version_id)
        blocked = PlanVersionValidationReport(
            valid=False, blocking_issues=("WBS_EMPTY",), warnings=(),
            coverage_summary=self.report.coverage_summary,
            checked_at=self.report.checked_at,
        )
        self.evaluator.evaluate_snapshot_in_transaction.return_value = (b"f" * 32, blocked)
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_in_transaction(self.tx, query=self.query)

    def test_invalid_context_and_validation_dependencies_fail_closed(self) -> None:
        invalid = PlanVersionReviewReadinessQuery(
            b"x", self.query.trace_id, self.query.project_id,
            self.query.plan_id, self.query.plan_version_id)
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_in_transaction(self.tx, query=invalid)
        self.evaluator.evaluate_snapshot_in_transaction.return_value = (b"short", self.report)
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_in_transaction(self.tx, query=self.query)
        self.evaluator.evaluate_snapshot_in_transaction.side_effect = RuntimeError("private detail")
        with self.assertRaises(PlanReviewReadinessDenied) as error:
            self.service.prove_in_transaction(self.tx, query=self.query)
        self.assertNotIn("private detail", str(error.exception))

    def test_terminal_proof_requires_exact_in_review_binding_and_same_snapshot_digest(self) -> None:
        review_id, round_id = uuid.uuid4(), uuid.uuid4()
        snapshot = _snapshot(state="IN_REVIEW", review_ref=review_id,
                             round_ref=round_id)
        query = PlanVersionReviewTerminalQuery(
            b"s" * 32, uuid.uuid4(), snapshot.project_id, snapshot.plan_id,
            snapshot.plan_version_id, review_id, round_id, b"f" * 32)
        self.repository.lock_current.return_value = PlanVersionReviewLock(
            snapshot, snapshot.plan_version_id)
        proof = self.service.prove_terminal_in_transaction(self.tx, query=query)
        self.assertEqual(proof.content_fingerprint, b"f" * 32)
        self.evaluator.evaluate_snapshot_in_transaction.assert_called_once_with(
            self.tx, snapshot=snapshot, session_token=query.session_token,
            trace_id=query.trace_id)

        self.evaluator.evaluate_snapshot_in_transaction.reset_mock()
        self.repository.lock_current.return_value = PlanVersionReviewLock(
            _snapshot(state="IN_REVIEW", review_ref=uuid.uuid4(),
                      round_ref=round_id), snapshot.plan_version_id)
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_terminal_in_transaction(self.tx, query=query)
        self.evaluator.evaluate_snapshot_in_transaction.assert_not_called()

        self.repository.lock_current.return_value = PlanVersionReviewLock(
            snapshot, snapshot.plan_version_id)
        self.evaluator.evaluate_snapshot_in_transaction.return_value = (b"x" * 32, self.report)
        with self.assertRaises(PlanReviewReadinessDenied):
            self.service.prove_terminal_in_transaction(self.tx, query=query)


if __name__ == "__main__":
    unittest.main()
