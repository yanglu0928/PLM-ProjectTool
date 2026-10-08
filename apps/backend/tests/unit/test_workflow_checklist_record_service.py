from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
)
from plm_assistant.modules.workflow.application.append_checklist_record import (
    ChecklistRecordWriteLock,
)
from plm_assistant.modules.workflow.application.current_checklist_record import (
    ChecklistBasisObservation, CurrentChecklistRecord,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification, ChecklistQualificationError,
    ChecklistQualificationEvidence, ChecklistQualificationReview,
    ChecklistQualificationSubject, CurrentChecklistQualification,
)
from plm_assistant.modules.workflow.application.record_checklist import (
    RecordWorkflowChecklist, WorkflowChecklistRecordError,
    WorkflowChecklistRecordService,
)
from plm_assistant.modules.workflow.domain.checklist_record import (
    ChecklistRecordSnapshot,
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


class WorkflowChecklistRecordServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime.now(timezone.utc)
        self.actor, self.project, self.workflow = uuid4(), uuid4(), uuid4()
        self.record_id, self.evidence_id = uuid4(), uuid4()
        self.review_id, self.round_id, self.version_id = (
            uuid4(), uuid4(), uuid4(),
        )
        self.uow = _UnitOfWork()
        self.sessions, self.projects = Mock(), Mock()
        self.guard, self.qualification = Mock(), Mock()
        self.appender, self.replay = Mock(), Mock()
        self.receipts, self.audit = Mock(), Mock()
        self.receipts.reserve.return_value = None
        self.sessions.authenticated_user.return_value = self.actor
        self.projects.require_in_transaction.return_value = (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_CHECKLIST_RECORD", "PROJECT_MANAGER",
            )
        )
        evidence = ChecklistQualificationEvidence(
            self.evidence_id, self.project, 2, b"e" * 32, self.now,
        )
        subject_id = uuid4()
        review = ChecklistQualificationReview(
            self.review_id, self.round_id, self.project, subject_id,
            self.version_id, 3, b"v" * 32, self.now,
            "HND-05", "HANDOVER_APPROVAL_V1",
        )
        self.qualification_result = CurrentChecklistQualification(
            self.project, "HANDOVER", "HANDOVER_BASELINE", "HND-05",
            subject_id, self.version_id, b"q" * 32, (evidence,), review,
        )
        self.qualification.qualify_only_current_in_transaction.return_value = (
            self.qualification_result
        )
        self.lock = ChecklistRecordWriteLock(
            self.workflow, self.project, 1, "HANDOVER", "ACTIVE",
            "HANDOVER_BASELINE", ChecklistState.PENDING, 0, 1, None,
        )
        self.appender.lock_current.return_value = self.lock
        self.current = self._current(ChecklistState.PASS)
        self.appender.append.return_value = self.current
        self.replay.get_record.return_value = self.current
        self.service = WorkflowChecklistRecordService(
            unit_of_work=self.uow, sessions=self.sessions,
            projects=self.projects, license_guard=self.guard,
            qualification=self.qualification, appender=self.appender,
            replay=self.replay, receipts=self.receipts,
            audit=self.audit, clock=lambda: self.now,
        )

    def _current(self, result: ChecklistState) -> CurrentChecklistRecord:
        basis = ()
        evidence_refs, review_refs = (), ()
        if result is ChecklistState.PASS:
            basis = (
                ChecklistBasisObservation(
                    "EVIDENCE", self.evidence_id, "PROJECT", self.project,
                    "ELIGIBLE", 2, b"e" * 32, self.now, 1,
                ),
                ChecklistBasisObservation(
                    "REVIEW_ROUND", self.round_id, "PROJECT", self.project,
                    "APPROVED", 3, b"q" * 32, self.now, 1,
                ),
            )
            evidence_refs, review_refs = (
                (self.evidence_id,), (self.round_id,),
            )
        snapshot = ChecklistRecordSnapshot(
            self.record_id, self.workflow, self.project,
            self.actor, uuid4(), 1, "HANDOVER", "HANDOVER_BASELINE",
            ChecklistState.PENDING, result, 0, 1, 1, 2, self.now,
            evidence_refs=evidence_refs,
            review_round_refs=review_refs,
        )
        return CurrentChecklistRecord(
            snapshot, basis, b"c" * 32, "ACTIVE", 2,
        )

    def _command(
        self, result: ChecklistState = ChecklistState.PASS, **changes,
    ) -> RecordWorkflowChecklist:
        values = dict(
            session_token=b"s" * 32, csrf_token=b"c" * 32,
            trace_id=uuid4(), project_id=self.project,
            item_key="HANDOVER_BASELINE", result=result,
            evidence_refs=(self.evidence_id,) if result is ChecklistState.PASS
            else (), exception_refs=(), expected_workflow_version=1,
        )
        values.update(changes)
        return RecordWorkflowChecklist(**values)

    def test_pass_uses_exact_owner_observations_and_commits(self):
        result = self.service.record(
            self._command(), idempotency_key="checklist-pass-001",
        )
        self.assertIs(result, self.current)
        append = self.appender.append.call_args.kwargs["command"]
        self.assertEqual(
            {value.ref_kind for value in append.basis},
            {"EVIDENCE", "REVIEW_ROUND"},
        )
        review = next(value for value in append.basis
                      if value.ref_kind == "REVIEW_ROUND")
        self.assertEqual(review.content_fingerprint, b"q" * 32)
        self.assertTrue(self.uow.values[-1].committed)
        self.audit.append.assert_called_once()
        self.receipts.complete.assert_called_once()

    def test_fail_skips_business_owner_but_keeps_write_controls(self):
        failed = self._current(ChecklistState.FAIL)
        self.appender.append.return_value = failed
        result = self.service.record(
            self._command(ChecklistState.FAIL),
            idempotency_key="checklist-fail-001",
        )
        self.assertIs(result, failed)
        self.qualification.qualify_only_current_in_transaction.assert_not_called()
        self.assertEqual(
            self.appender.append.call_args.kwargs["command"].basis, (),
        )
        self.guard.require_valid.assert_called_once()

    def test_survey_pass_uses_registered_current_fact_owner(self):
        conclusion_series, conclusion_version = uuid4(), uuid4()
        review = ChecklistQualificationReview(
            self.review_id, self.round_id, self.project, conclusion_series,
            conclusion_version, 4, b"s" * 32, self.now,
            "SRV-05", "SURVEY_CONCLUSION_ALL_V1",
        )
        self.qualification.qualify_only_current_in_transaction.return_value = (
            CurrentChecklistQualification(
                self.project, "SURVEY", "SURVEY_CONCLUSION", "SRV-05",
                conclusion_series, conclusion_version, b"q" * 32,
                self.qualification_result.evidence, review,
            )
        )
        survey_record = replace(
            self.current.record,
            stage_key="SURVEY", item_key="SURVEY_CONCLUSION",
        )
        survey_current = CurrentChecklistRecord(
            survey_record, self.current.basis,
            self.current.content_fingerprint,
            self.current.observed_stage_state,
            self.current.current_workflow_version,
        )
        self.appender.append.return_value = survey_current

        result = self.service.record(
            self._command(item_key="SURVEY_CONCLUSION"),
            idempotency_key="checklist-survey-pass-001",
        )

        self.assertIs(result, survey_current)
        query = self.qualification.qualify_only_current_in_transaction.call_args.args[1]
        self.assertEqual("SURVEY_CONCLUSION", query.item_key)

    def test_requirement_pass_persists_all_subject_reviews_and_evidence(self):
        subjects = []
        for index in range(2):
            subject_id, version_id = uuid4(), uuid4()
            evidence = ChecklistQualificationEvidence(
                uuid4(), self.project, index + 4,
                bytes([index + 4]) * 32, self.now,
            )
            review = ChecklistQualificationReview(
                uuid4(), uuid4(), self.project, subject_id, version_id,
                index + 6, bytes([index + 10]) * 32, self.now,
                "REQ-03", "REQUIREMENT_ALL_V1",
            )
            subjects.append(ChecklistQualificationSubject(
                "REQ-03", subject_id, version_id,
                bytes([index + 10]) * 32, (evidence,), review,
            ))
        subjects.sort(key=lambda value: value.subject_id.int)
        decision_evidence = ChecklistQualificationEvidence(
            uuid4(), self.project, 8, b"d" * 32, self.now,
        )
        aggregate = AggregateChecklistQualification(
            self.project, "REQUIREMENT", "REQUIREMENT_ACCEPTANCE",
            tuple(subjects), (decision_evidence,), b"s" * 32, b"q" * 32,
        )
        self.qualification.qualify_only_current_in_transaction.return_value = aggregate

        self.service.record(self._command(
            item_key="REQUIREMENT_ACCEPTANCE",
            evidence_refs=aggregate.evidence_refs,
        ), idempotency_key="checklist-requirement-pass-001")

        basis = self.appender.append.call_args.kwargs["command"].basis
        self.assertEqual(3, sum(
            value.ref_kind == "EVIDENCE" for value in basis
        ))
        self.assertEqual(2, sum(
            value.ref_kind == "REVIEW_ROUND" for value in basis
        ))
        self.assertEqual(
            set(aggregate.review_round_refs),
            {value.ref_id for value in basis
             if value.ref_kind == "REVIEW_ROUND"},
        )

    def test_prototype_pass_reproves_mixed_subjects_without_fake_artifact_evidence(self):
        req, req_version, prt, prt_version = (uuid4() for _ in range(4))
        evidence = ChecklistQualificationEvidence(
            uuid4(), self.project, 4, b"e" * 32, self.now,
        )
        req_review = ChecklistQualificationReview(
            uuid4(), uuid4(), self.project, req, req_version, 3,
            b"r" * 32, self.now, "REQ-03", "REQUIREMENT_ALL_V1",
        )
        prt_review = ChecklistQualificationReview(
            uuid4(), uuid4(), self.project, prt, prt_version, 3,
            b"p" * 32, self.now, "PRT-03", "PROTOTYPE_ALL_V1",
        )
        aggregate = AggregateChecklistQualification(
            self.project, "PROTOTYPE", "PROTOTYPE_COVERAGE", (
                ChecklistQualificationSubject(
                    "PRT-03", prt, prt_version, b"p" * 32, (), prt_review,
                ),
                ChecklistQualificationSubject(
                    "REQ-03", req, req_version, b"r" * 32,
                    (evidence,), req_review,
                ),
            ), (), b"s" * 32, b"q" * 32,
        )
        self.qualification.qualify_only_current_in_transaction.return_value = aggregate
        command = self._command(
            item_key="PROTOTYPE_COVERAGE",
            evidence_refs=aggregate.evidence_refs,
        )
        with self.assertRaisesRegex(
                WorkflowChecklistRecordError, "VALIDATION_FAILED"):
            self.service.record(
                command, idempotency_key="checklist-prototype-closed-001",
            )
        prototype_service = WorkflowChecklistRecordService(
            unit_of_work=self.uow, sessions=self.sessions,
            projects=self.projects, license_guard=self.guard,
            qualification=self.qualification, appender=self.appender,
            replay=self.replay, receipts=self.receipts,
            audit=self.audit, clock=lambda: self.now,
            enable_prototype=True,
        )
        prototype_service.record(
            command, idempotency_key="checklist-prototype-pass-001",
        )
        basis = self.appender.append.call_args.kwargs["command"].basis
        self.assertEqual(1, sum(value.ref_kind == "EVIDENCE" for value in basis))
        self.assertEqual(2, sum(value.ref_kind == "REVIEW_ROUND" for value in basis))
        self.assertEqual((evidence.evidence_id,), aggregate.evidence_refs)

    def test_replay_returns_original_record_without_new_business_write(self):
        self.receipts.reserve.return_value = IdempotencyResult(
            "V1_WORKFLOW_CHECKLIST_RECORD", self.record_id, 200,
        )
        result = self.service.record(
            self._command(), idempotency_key="checklist-replay-01",
        )
        self.assertIs(result, self.current)
        self.replay.get_record.assert_called_once()
        self.appender.append.assert_not_called()
        self.audit.append.assert_not_called()
        self.receipts.complete.assert_not_called()
        self.assertFalse(self.uow.values[-1].committed)

    def test_mismatched_evidence_and_owner_failure_close_gate(self):
        commands = (
            self._command(evidence_refs=(uuid4(),)),
            self._command(),
        )
        for index, command in enumerate(commands):
            with self.subTest(index=index):
                if index:
                    self.qualification.qualify_only_current_in_transaction.side_effect = (
                        ChecklistQualificationError()
                    )
                with self.assertRaisesRegex(
                    WorkflowChecklistRecordError,
                    "WORKFLOW_GATE_NOT_SATISFIED",
                ):
                    self.service.record(
                        command, idempotency_key=f"checklist-denied-{index}",
                    )
                self.appender.append.assert_not_called()

    def test_waived_unregistered_and_arbitrary_fail_refs_are_closed(self):
        cases = (
            self._command(ChecklistState.WAIVED,
                          exception_refs=(uuid4(),),
                          reason="Approved exception", impact="Bounded"),
            self._command(item_key="PROTOTYPE_GATE"),
            self._command(ChecklistState.FAIL,
                          evidence_refs=(self.evidence_id,)),
        )
        expected = (
            "WORKFLOW_GATE_NOT_SATISFIED",
            "VALIDATION_FAILED", "VALIDATION_FAILED",
        )
        for command, code in zip(cases, expected):
            with self.subTest(code=code), self.assertRaisesRegex(
                    WorkflowChecklistRecordError, code):
                self.service.record(
                    command, idempotency_key="checklist-shape-001",
                )

    def test_non_manager_and_audit_failure_do_not_commit(self):
        self.projects.require_in_transaction.return_value = (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_CHECKLIST_RECORD", "CUSTOMER_MANAGER",
            )
        )
        with self.assertRaisesRegex(
                WorkflowChecklistRecordError, "RESOURCE_NOT_FOUND"):
            self.service.record(
                self._command(), idempotency_key="checklist-role-0001",
            )
        self.projects.require_in_transaction.return_value = (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_CHECKLIST_RECORD", "PROJECT_MANAGER",
            )
        )
        self.audit.append.side_effect = RuntimeError("synthetic audit failure")
        with self.assertRaisesRegex(
                WorkflowChecklistRecordError, "WORKFLOW_UNAVAILABLE"):
            self.service.record(
                self._command(), idempotency_key="checklist-audit-001",
            )
        self.assertFalse(self.uow.values[-1].committed)


if __name__ == "__main__":
    unittest.main()
