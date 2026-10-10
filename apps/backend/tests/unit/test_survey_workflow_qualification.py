from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace

from plm_assistant.modules.evidence.application.fixed_project_source import (
    VerifiedProjectEvidence,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.survey.application.conclusion_sources import (
    ConclusionProjectRecordProof, ConclusionResponseEvidenceProof,
    ConclusionResponseProof,
)
from plm_assistant.modules.survey.application.create_conclusion import (
    DepartmentConclusionInput,
)
from plm_assistant.modules.survey.application.validate_conclusion import (
    ConclusionValidationSnapshot,
)
from plm_assistant.modules.survey.application.workflow_qualification import (
    SurveyWorkflowQualificationError, SurveyWorkflowQualificationLock,
    SurveyWorkflowQualificationOwner, SurveyWorkflowQualificationPolicy,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationError, CurrentChecklistQualificationQuery,
)


NOW = datetime(2026, 10, 7, tzinfo=timezone.utc)


class Repo:
    def __init__(self, lock): self.lock = lock
    def lock_only_current_approved(self, transaction, *, project_id):
        return self.lock


class Current:
    issues = ()
    def current_facts(self, transaction, command, snapshot):
        return SimpleNamespace(issues=self.issues)


class Responses:
    def __init__(self, proof): self.proof = proof
    def prove(self, transaction, **kwargs): return self.proof


class Evidence:
    def __init__(self, proof): self.proof = proof
    def prove(self, transaction, query, evidence_id): return self.proof


class Reviews:
    def __init__(self, proof): self.proof = proof
    def get_round(self, transaction, scope, project_id, review_id, round_id):
        return self.proof


class SurveyWorkflowQualificationTests(unittest.TestCase):
    def setUp(self):
        ids = [uuid.uuid4() for _ in range(18)]
        (self.project, self.survey, self.round, self.series,
         self.conclusion, self.department, self.response, self.answer,
         self.assignment, self.question, self.evidence_id, self.document,
         self.document_version, self.actor, self.review_id, self.round_id,
         self.reviewer, self.trace_id) = ids
        self.stored_evidence = ConclusionProjectRecordProof(
            self.evidence_id, self.project, self.document,
            self.document_version, 4, b"e" * 32, self.actor,
        )
        self.response_proof = ConclusionResponseProof(
            self.response, self.answer, self.assignment, self.round,
            self.survey, uuid.uuid4(), self.project, self.department,
            self.question, "FACILITATED_RECORD", b"r" * 32,
            (self.evidence_id,),
            (ConclusionResponseEvidenceProof(
                self.evidence_id, self.document, self.document_version,
                4, b"e" * 32,
            ),),
        )
        self.snapshot = ConclusionValidationSnapshot(
            self.conclusion, self.series, self.project, self.survey,
            (self.round,), (), 1, "APPROVED", b"c" * 32,
            1, 0, 1, 0, None,
            (DepartmentConclusionInput(
                self.department, "Department", "Finding", (self.response,),
            ),),
            (), (self.stored_evidence,), ("SUPPORT",), (), (),
            True, True, 0,
        )
        self.lock = SurveyWorkflowQualificationLock(
            self.snapshot, "ACTIVE", self.review_id, self.round_id,
        )
        progress = ReviewRoundProgress(
            self.round_id, NOW, (self.reviewer,),
        ).record_decision(ReviewDecisionSnapshot(
            uuid.uuid4(), self.round_id, self.reviewer,
            ReviewDecisionKind.APPROVE, NOW,
        ))
        identity = ReviewIdentitySnapshot(
            self.review_id, "PROJECT", self.project, "SRV-05",
            self.series, "SURVEY_CONCLUSION_ALL_V1",
            "APPROVED", None, 2,
        )
        self.review = FixedReviewRoundSnapshot(
            identity, 1, self.conclusion, self.actor, progress,
            (uuid.uuid4(),), 1, uuid.uuid4(), b"c" * 32, 1, NOW,
            (), uuid.uuid4(), NOW, NOW,
        )
        self.evidence = VerifiedProjectEvidence(
            self.evidence_id, self.project, self.document,
            self.document_version, None, 4, b"e" * 32,
            verified_by=self.actor, verified_project_role="PROJECT_MANAGER",
            document_category="PROJECT_RECORD",
        )
        self.current = Current()
        self.responses = Responses(self.response_proof)
        self.evidence_owner = Evidence(self.evidence)
        self.reviews = Reviews(self.review)
        self.owner = SurveyWorkflowQualificationOwner(
            repository=Repo(self.lock), current=self.current,
            responses=self.responses, evidence=self.evidence_owner,
            reviews=self.reviews, clock=lambda: NOW,
        )

    def query(self, item="SURVEY_ACTUAL_SOURCES"):
        return CurrentChecklistQualificationQuery(
            b"s" * 32, self.trace_id, self.project, item,
        )

    def test_qualifies_both_items_from_one_approved_conclusion(self):
        actual = self.owner.qualify_only_current_in_transaction(
            object(), self.query(),
        )
        conclusion = self.owner.qualify_only_current_in_transaction(
            object(), self.query("SURVEY_CONCLUSION"),
        )

        self.assertEqual("SURVEY", actual.stage_key)
        self.assertEqual("SRV-05", actual.subject_type)
        self.assertEqual(self.conclusion, actual.subject_version_id)
        self.assertEqual(actual.coherence_key, conclusion.coherence_key)
        self.assertNotEqual(actual.content_fingerprint,
                            conclusion.content_fingerprint)
        self.assertEqual((self.evidence_id,), tuple(
            value.evidence_id for value in actual.evidence))

    def test_rejects_current_issue_ambiguous_owner_and_wrong_item(self):
        self.current.issues = ("BLOCKING_OPEN_ISSUE",)
        with self.assertRaises(ChecklistQualificationError):
            self.owner.qualify_only_current_in_transaction(
                object(), self.query(),
            )
        self.current.issues = ()
        missing = SurveyWorkflowQualificationOwner(
            repository=Repo(None), current=self.current,
            responses=self.responses, evidence=self.evidence_owner,
            reviews=self.reviews,
        )
        with self.assertRaises(ChecklistQualificationError):
            missing.qualify_only_current_in_transaction(object(), self.query())
        with self.assertRaises(ChecklistQualificationError):
            self.owner.qualify_only_current_in_transaction(
                object(), CurrentChecklistQualificationQuery(
                    b"s" * 32, self.trace_id, self.project,
                    "HANDOVER_BASELINE",
                ),
            )

    def test_rejects_evidence_drift_template_and_review_drift(self):
        for proof in (
            replace(self.evidence, observed_lock_version=5),
            replace(self.evidence, content_fingerprint=b"z" * 32),
            replace(self.evidence, document_category="TEMPLATE"),
        ):
            with self.subTest(proof=proof), self.assertRaises(
                ChecklistQualificationError,
            ):
                SurveyWorkflowQualificationOwner(
                    repository=Repo(self.lock), current=self.current,
                    responses=self.responses, evidence=Evidence(proof),
                    reviews=self.reviews, clock=lambda: NOW,
                ).qualify_only_current_in_transaction(object(), self.query())
        wrong_review = replace(self.review, subject_fingerprint=b"z" * 32)
        with self.assertRaises(ChecklistQualificationError):
            SurveyWorkflowQualificationOwner(
                repository=Repo(self.lock), current=self.current,
                responses=self.responses, evidence=self.evidence_owner,
                reviews=Reviews(wrong_review), clock=lambda: NOW,
            ).qualify_only_current_in_transaction(object(), self.query())

    def test_rejects_response_evidence_snapshot_mismatch(self):
        broken = replace(self.response_proof, evidence=(
            replace(self.response_proof.evidence[0],
                    observed_evidence_lock_version=8),
        ))
        with self.assertRaises(ChecklistQualificationError):
            SurveyWorkflowQualificationOwner(
                repository=Repo(self.lock), current=self.current,
                responses=Responses(broken), evidence=self.evidence_owner,
                reviews=self.reviews, clock=lambda: NOW,
            ).qualify_only_current_in_transaction(object(), self.query())

    def test_policy_rejects_empty_actual_source(self):
        with self.assertRaises(SurveyWorkflowQualificationError):
            SurveyWorkflowQualificationPolicy().qualify(
                item_key="SURVEY_ACTUAL_SOURCES", lock=self.lock,
                evidence=(), review=None, response_ids=(),
                project_record_ids=(),
            )


if __name__ == "__main__":
    unittest.main()
