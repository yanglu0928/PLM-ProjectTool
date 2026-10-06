from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.handover.application.workflow_qualification import (
    HandoverChecklistQualification,
    HandoverWorkflowEvidenceObservation,
    HandoverWorkflowReviewObservation,
)
from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.workflow.application.append_stage_transition import (
    PersistedStageTransition, PersistedTransitionGate,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation,
)
from plm_assistant.modules.workflow.application.transition_stage import (
    TransitionWorkflowStage, WorkflowStageTransitionError,
    WorkflowStageTransitionService,
)
from plm_assistant.modules.workflow.domain.history import (
    ForwardTransitionSnapshot, GateItemSnapshot,
)
from plm_assistant.modules.workflow.domain.transition import ChecklistState


class _Transaction:
    def __init__(self) -> None:
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def commit(self) -> None:
        self.committed = True


class _UnitOfWork:
    def __init__(self) -> None:
        self.values: list[_Transaction] = []

    def __call__(self) -> _Transaction:
        value = _Transaction()
        self.values.append(value)
        return value


class WorkflowStageTransitionServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.project, self.workflow = uuid4(), uuid4(), uuid4()
        self.trace, self.analysis, self.version = uuid4(), uuid4(), uuid4()
        self.review, self.round = uuid4(), uuid4()
        self.uow = _UnitOfWork()
        self.sessions, self.projects, self.guard = Mock(), Mock(), Mock()
        self.qualification, self.transitions = Mock(), Mock()
        self.receipts, self.audit = Mock(), Mock()
        self.sessions.authenticated_user.return_value = self.actor
        self.projects.require_in_transaction.return_value = (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_TRANSITION", "PROJECT_MANAGER",
            )
        )
        self.receipts.reserve.return_value = None
        self.qualifications = tuple(
            self._qualification(item_key, index)
            for index, item_key in enumerate((
                "HANDOVER_BASELINE", "HANDOVER_ISSUES",
            ))
        )
        self.qualification.qualify_only_current_in_transaction.side_effect = (
            self.qualifications
        )
        self.result = self._result()
        self.transitions.append.return_value = self.result
        self.transitions.get_transition.return_value = self.result
        self.service = WorkflowStageTransitionService(
            unit_of_work=self.uow, sessions=self.sessions,
            projects=self.projects, license_guard=self.guard,
            qualification=self.qualification,
            transitions=self.transitions, receipts=self.receipts,
            audit=self.audit, clock=lambda: self.now,
        )

    def _qualification(
        self, item_key: str, index: int,
    ) -> HandoverChecklistQualification:
        evidence = HandoverWorkflowEvidenceObservation(
            uuid4(), self.project, index + 2,
            bytes([index + 1]) * 32, self.now,
        )
        review = HandoverWorkflowReviewObservation(
            self.review, self.round, self.project, self.analysis,
            self.version, 3, b"v" * 32, self.now,
        )
        return HandoverChecklistQualification(
            item_key, self.project, self.version,
            bytes([index + 10]) * 32, (evidence,), review,
        )

    def _result(self) -> PersistedStageTransition:
        gates = []
        snapshots = []
        for index, value in enumerate(self.qualifications):
            basis = (
                ChecklistBasisObservation(
                    "EVIDENCE", value.evidence[0].evidence_id,
                    "PROJECT", self.project, "ELIGIBLE",
                    value.evidence[0].observed_lock_version,
                    value.evidence[0].content_fingerprint, self.now, 1,
                ),
                ChecklistBasisObservation(
                    "REVIEW_ROUND", self.round, "PROJECT", self.project,
                    "APPROVED", 3, value.content_fingerprint, self.now, 1,
                ),
            )
            basis = tuple(sorted(
                basis, key=lambda item: (item.ref_kind, str(item.ref_id)),
            ))
            snapshot = GateItemSnapshot(
                value.item_key, ChecklistState.PASS,
                tuple(item.ref_id for item in basis
                      if item.ref_kind == "EVIDENCE"),
                tuple(item.ref_id for item in basis
                      if item.ref_kind == "REVIEW_ROUND"),
            )
            snapshots.append(snapshot)
            gates.append(PersistedTransitionGate(
                uuid4(), uuid4(), 1, bytes([index + 20]) * 32,
                snapshot, basis,
            ))
        root = ForwardTransitionSnapshot(
            self.workflow, self.project, self.actor, self.trace, 1,
            "HANDOVER", "SURVEY", 3, 4,
            "Handover accepted", self.now, tuple(snapshots),
        )
        return PersistedStageTransition(
            uuid4(), root, tuple(gates), b"t" * 32, 4,
        )

    def _command(self, **changes) -> TransitionWorkflowStage:
        values = dict(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            trace_id=self.trace, project_id=self.project,
            target_stage_key="SURVEY", expected_workflow_version=3,
            reason="Handover accepted",
        )
        values.update(changes)
        return TransitionWorkflowStage(**values)

    def test_success_reproves_both_gates_then_audits_and_commits(self):
        result = self.service.transition(
            self._command(), idempotency_key="workflow-transition-001",
        )
        self.assertIs(result, self.result)
        queries = [call.args[1] for call in
                   self.qualification.qualify_only_current_in_transaction.call_args_list]
        self.assertEqual(
            tuple(query.item_key for query in queries),
            ("HANDOVER_BASELINE", "HANDOVER_ISSUES"),
        )
        appended = self.transitions.append.call_args.kwargs["command"]
        self.assertEqual(
            tuple(gate.item_key for gate in appended.gates),
            ("HANDOVER_BASELINE", "HANDOVER_ISSUES"),
        )
        self.assertEqual(appended.occurred_at, self.now)
        event = self.audit.append.call_args.args[1]
        self.assertEqual(event.action, "WORKFLOW_STAGE_TRANSITIONED")
        self.assertEqual(event.before_state, "HANDOVER")
        self.assertEqual(event.after_state, "SURVEY")
        completed = self.receipts.complete.call_args.kwargs["result"]
        self.assertEqual(completed, IdempotencyResult(
            "V1_WORKFLOW_TRANSITION",
            self.result.stage_transition_id, 200,
        ))
        self.assertTrue(self.uow.values[-1].committed)

    def test_replay_rechecks_access_and_returns_original_without_owner_write(self):
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_WORKFLOW_TRANSITION", self.result.stage_transition_id, 200,
        )
        result = self.service.transition(
            self._command(), idempotency_key="workflow-transition-replay",
        )
        self.assertIs(result, self.result)
        self.projects.require_in_transaction.assert_called_once()
        self.transitions.get_transition.assert_called_once()
        self.qualification.qualify_only_current_in_transaction.assert_not_called()
        self.transitions.append.assert_not_called()
        self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called()
        self.assertFalse(self.uow.values[-1].committed)

    def test_two_gate_proofs_must_share_version_and_review(self):
        changed_version = uuid4()
        changed_review = replace(
            self.qualifications[1].review,
            review_round_id=uuid4(), subject_id=uuid4(),
            subject_version_id=changed_version,
        )
        changed = replace(
            self.qualifications[1],
            handover_analysis_version_id=changed_version,
            review=changed_review,
        )
        self.qualification.qualify_only_current_in_transaction.side_effect = (
            self.qualifications[0], changed,
        )
        with self.assertRaisesRegex(
                WorkflowStageTransitionError,
                "WORKFLOW_GATE_NOT_SATISFIED"):
            self.service.transition(
                self._command(), idempotency_key="workflow-transition-drift",
            )
        self.transitions.append.assert_not_called()
        self.assertFalse(self.uow.values[-1].committed)

    def test_non_manager_license_and_audit_failure_close_without_commit(self):
        self.projects.require_in_transaction.return_value = (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_TRANSITION", "CUSTOMER_MANAGER",
            )
        )
        with self.assertRaisesRegex(
                WorkflowStageTransitionError, "RESOURCE_NOT_FOUND"):
            self.service.transition(
                self._command(), idempotency_key="workflow-transition-role",
            )
        self.projects.require_in_transaction.return_value = (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_TRANSITION", "PROJECT_MANAGER",
            )
        )
        self.guard.require_valid.side_effect = RuntimeLicenseError("EXPIRED")
        with self.assertRaisesRegex(
                WorkflowStageTransitionError, "LICENSE_OPERATION_DENIED"):
            self.service.transition(
                self._command(), idempotency_key="workflow-transition-license",
            )
        self.guard.require_valid.side_effect = None
        self.audit.append.side_effect = RuntimeError("synthetic audit failure")
        with self.assertRaisesRegex(
                WorkflowStageTransitionError, "WORKFLOW_UNAVAILABLE"):
            self.service.transition(
                self._command(), idempotency_key="workflow-transition-audit",
            )
        self.assertFalse(self.uow.values[-1].committed)

    def test_invalid_command_and_repository_error_are_safe(self):
        for command in (
            self._command(target_stage_key="REQUIREMENT"),
            self._command(reason=" "),
            self._command(expected_workflow_version=-1),
        ):
            with self.subTest(command=command), self.assertRaisesRegex(
                    WorkflowStageTransitionError, "VALIDATION_FAILED"):
                self.service.transition(
                    command, idempotency_key="workflow-transition-invalid",
                )
        self.transitions.append.side_effect = Exception("database detail")
        with self.assertRaisesRegex(
                WorkflowStageTransitionError, "WORKFLOW_UNAVAILABLE"):
            self.service.transition(
                self._command(), idempotency_key="workflow-transition-db",
            )


if __name__ == "__main__":
    unittest.main()
