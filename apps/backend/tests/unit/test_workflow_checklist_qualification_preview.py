from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

from plm_assistant.modules.license.application.runtime_guard import (
    RuntimeLicenseError,
)
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
)
from plm_assistant.modules.workflow.application.preview_checklist_qualification import (
    WorkflowChecklistQualificationPreviewError,
    WorkflowChecklistQualificationPreviewQuery,
    WorkflowChecklistQualificationPreviewService,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationError, ChecklistQualificationEvidence,
    ChecklistQualificationReview, CurrentChecklistQualification,
)
from plm_assistant.modules.workflow.application.read_workflow import (
    ChecklistView, StageView, WorkflowView,
)
from plm_assistant.modules.workflow.domain.catalog_v1 import six_stage_definition


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
        self.transactions: list[_Transaction] = []

    def __call__(self) -> _Transaction:
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


class WorkflowChecklistQualificationPreviewTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 6, tzinfo=timezone.utc)
        self.actor, self.project, self.workflow = uuid4(), uuid4(), uuid4()
        self.analysis_version, self.review, self.round = (
            uuid4(), uuid4(), uuid4(),
        )
        self.evidence = (uuid4(), uuid4())
        self.uow = _UnitOfWork()
        self.sessions, self.projects = Mock(), Mock()
        self.guard, self.workflows, self.qualification = Mock(), Mock(), Mock()
        self.sessions.authenticated_user.return_value = self.actor
        self.projects.require_in_transaction.return_value = AuthorizedProjectAction(
            self.actor, self.project,
            "WORKFLOW_CHECKLIST_RECORD", "PROJECT_MANAGER",
        )
        self.view = self._view()
        self.workflows.get.return_value = self.view
        observations = tuple(ChecklistQualificationEvidence(
            value, self.project, index + 1, bytes([index + 1]) * 32,
            self.now,
        ) for index, value in enumerate(self.evidence))
        subject_id = uuid4()
        review = ChecklistQualificationReview(
            self.review, self.round, self.project, subject_id,
            self.analysis_version, 3, b"r" * 32, self.now,
            "HND-05", "HANDOVER_APPROVAL_V1",
        )
        self.qualification.get = None
        self.qualification.qualify_only_current_in_transaction.return_value = (
            CurrentChecklistQualification(
                self.project, "HANDOVER", "HANDOVER_BASELINE", "HND-05",
                subject_id, self.analysis_version, b"q" * 32,
                observations, review,
            )
        )
        self.service = WorkflowChecklistQualificationPreviewService(
            unit_of_work=self.uow, sessions=self.sessions,
            projects=self.projects, license_guard=self.guard,
            workflows=self.workflows, qualification=self.qualification,
            clock=lambda: self.now,
        )

    def _view(self, *, state="ACTIVE", current="HANDOVER", lock=4):
        definition = six_stage_definition()
        current_index = next((
            index for index, stage in enumerate(definition.stages)
            if stage.stage_key == current
        ), None)
        stages = tuple(StageView(
            stage.stage_key, stage.order,
            ("COMPLETED" if state == "ACTIVE" and current_index is not None
             and index < current_index else
             "ACTIVE" if stage.stage_key == current and state == "ACTIVE"
             else "NOT_STARTED"),
            tuple(ChecklistView(
                item.item_key, item.required,
                "PASS" if state == "ACTIVE" and current_index is not None
                and index < current_index else "PENDING",
            )
                  for item in stage.checklist_items),
        ) for index, stage in enumerate(definition.stages))
        return WorkflowView(
            self.workflow, self.project, 1, state, current, stages, lock,
        )

    def _query(self, **changes):
        values = dict(
            session_token=b"s" * 32, trace_id=uuid4(),
            project_id=self.project, item_key="HANDOVER_BASELINE",
        )
        values.update(changes)
        return WorkflowChecklistQualificationPreviewQuery(**values)

    def test_returns_minimal_current_exact_set_without_commit(self):
        result = self.service.get(self._query())
        self.assertEqual(self.workflow, result.workflow_id)
        self.assertEqual(self.evidence, result.evidence_refs)
        self.assertEqual(self.analysis_version,
                         result.handover_analysis_version_id)
        self.assertEqual(self.round, result.review_round_ref)
        self.assertEqual('"v4"', result.workflow_etag)
        self.assertEqual("PENDING", result.current_item_state)
        self.assertFalse(self.uow.transactions[0].committed)
        self.assertEqual(2, self.workflows.get.call_count)
        qualification_query = (
            self.qualification.qualify_only_current_in_transaction
            .call_args.args[1]
        )
        self.assertEqual(self.project, qualification_query.project_id)
        self.assertEqual("HANDOVER_BASELINE", qualification_query.item_key)
        self.projects.require_in_transaction.assert_called_once_with(
            self.uow.transactions[0], user_id=self.actor,
            project_id=self.project,
            operation="WORKFLOW_CHECKLIST_RECORD",
        )

    def test_survey_current_stage_returns_strict_subject_variant(self):
        conclusion_series, conclusion_version = uuid4(), uuid4()
        observations = tuple(ChecklistQualificationEvidence(
            value, self.project, index + 1, bytes([index + 1]) * 32,
            self.now,
        ) for index, value in enumerate(self.evidence))
        review = ChecklistQualificationReview(
            self.review, self.round, self.project, conclusion_series,
            conclusion_version, 3, b"r" * 32, self.now,
            "SRV-05", "SURVEY_CONCLUSION_ALL_V1",
        )
        self.workflows.get.return_value = self._view(current="SURVEY", lock=5)
        self.qualification.qualify_only_current_in_transaction.return_value = (
            CurrentChecklistQualification(
                self.project, "SURVEY", "SURVEY_CONCLUSION", "SRV-05",
                conclusion_series, conclusion_version, b"q" * 32,
                observations, review,
            )
        )

        result = self.service.get(self._query(item_key="SURVEY_CONCLUSION"))

        self.assertEqual("SURVEY", result.stage_key)
        self.assertIsNone(result.handover_analysis_version_id)
        self.assertEqual(conclusion_version, result.survey_conclusion_id)
        self.assertEqual(self.evidence, result.evidence_refs)

    def test_invalid_query_and_non_current_stage_fail_before_owner(self):
        for query in (
            self._query(session_token=b"short"),
            self._query(item_key="REQUIREMENT_ACCEPTANCE"),
        ):
            with self.subTest(query=query), self.assertRaisesRegex(
                    WorkflowChecklistQualificationPreviewError,
                    "VALIDATION_FAILED"):
                self.service.get(query)
        self.workflows.get.return_value = self._view(
            state="NOT_STARTED", current=None, lock=0,
        )
        with self.assertRaisesRegex(
                WorkflowChecklistQualificationPreviewError,
                "CONFLICT_STATE"):
            self.service.get(self._query())
        self.qualification.qualify_only_current_in_transaction.assert_not_called()

    def test_missing_or_inconsistent_workflow_fails_closed(self):
        self.workflows.get.return_value = None
        with self.assertRaisesRegex(
                WorkflowChecklistQualificationPreviewError,
                "RESOURCE_NOT_FOUND"):
            self.service.get(self._query())
        self.workflows.get.side_effect = [self.view, self._view(lock=5)]
        with self.assertRaisesRegex(
                WorkflowChecklistQualificationPreviewError,
                "CONFLICT_VERSION"):
            self.service.get(self._query())

    def test_owner_license_session_and_project_failures_are_safe(self):
        cases = (
            (self.qualification.qualify_only_current_in_transaction,
             ChecklistQualificationError(),
             "WORKFLOW_GATE_NOT_SATISFIED"),
            (self.guard.require_valid, RuntimeLicenseError("invalid"),
             "LICENSE_OPERATION_DENIED"),
            (self.projects.require_in_transaction,
             ProjectAuthorizationError("PROJECT_ARCHIVED"),
             "PROJECT_ARCHIVED"),
        )
        for target, error, code in cases:
            with self.subTest(code=code):
                target.side_effect = error
                with self.assertRaisesRegex(
                        WorkflowChecklistQualificationPreviewError, code):
                    self.service.get(self._query())
                target.side_effect = None
        self.sessions.authenticated_user.return_value = None
        with self.assertRaisesRegex(
                WorkflowChecklistQualificationPreviewError,
                "AUTH_ACCESS_DENIED"):
            self.service.get(self._query())

    def test_wrong_role_or_owner_identity_is_hidden(self):
        for proof in (
            AuthorizedProjectAction(
                self.actor, self.project,
                "WORKFLOW_CHECKLIST_RECORD", "CUSTOMER_MANAGER",
            ),
            AuthorizedProjectAction(
                uuid4(), self.project,
                "WORKFLOW_CHECKLIST_RECORD", "PROJECT_MANAGER",
            ),
        ):
            self.projects.require_in_transaction.return_value = proof
            with self.subTest(proof=proof), self.assertRaisesRegex(
                    WorkflowChecklistQualificationPreviewError,
                    "RESOURCE_NOT_FOUND"):
                self.service.get(self._query())


if __name__ == "__main__":
    unittest.main()
