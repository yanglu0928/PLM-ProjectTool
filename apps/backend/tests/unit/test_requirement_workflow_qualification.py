from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)
from plm_assistant.modules.requirement.application.create_version import (
    RequirementAcceptanceDraft,
    RequirementAssessmentEvidenceDraft,
    RequirementCapabilityAssessmentDraft,
    RequirementSourceDraft,
)
from plm_assistant.modules.requirement.application.human_decision_source_proof import (
    RequirementHumanDecisionSourceProof,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionValidationSnapshot,
)
from plm_assistant.modules.requirement.application.workflow_qualification import (
    RequirementWorkflowApprovedLock,
    RequirementWorkflowDecisionLock,
    RequirementWorkflowQualificationOwner,
    RequirementWorkflowScopeLock,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
    ReviewDecisionSnapshot,
    ReviewRoundProgress,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    ChecklistQualificationError,
    CurrentChecklistQualificationQuery,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


class Repo:
    def __init__(self, lock):
        self.lock, self.calls = lock, 0

    def lock_complete_scope(self, transaction, *, project_id):
        self.calls += 1
        return self.lock


class Current:
    issues = ()
    def current_issues(self, transaction, snapshot): return self.issues


class Evidence:
    def __init__(self, proofs): self.proofs = proofs
    def prove(self, transaction, *, project_id, evidence_id):
        return self.proofs.get(evidence_id)


class Decisions:
    def __init__(self, proofs): self.proofs = proofs
    def prove(self, transaction, *, project_id, decision_id):
        return self.proofs.get(decision_id)


class Reviews:
    def __init__(self, proofs): self.proofs = proofs
    def get_round(self, transaction, scope, project_id, review_id, round_id):
        return self.proofs.get((review_id, round_id))


class RequirementWorkflowQualificationTests(unittest.TestCase):
    def setUp(self):
        self.project = uuid.uuid4()
        self.trace = uuid.uuid4()
        self.actor = uuid.uuid4()
        self.reviewer = uuid.uuid4()
        self.current = Current()
        self.evidence_proofs = {}
        self.review_proofs = {}
        self.approved = [self._approved(), self._approved()]
        self.approved.sort(key=lambda value: value.snapshot.requirement_id.int)
        self.deferred_requirement = uuid.uuid4()
        self.decision_id = uuid.uuid4()
        self.decision_evidence = uuid.uuid4()
        self.decision_lock = RequirementWorkflowDecisionLock(
            self.deferred_requirement, "DEFERRED", self.decision_id, 2,
        )
        self.decision_proof = RequirementHumanDecisionSourceProof(
            self.decision_id, self.deferred_requirement, self.project,
            "DEFER", self.actor, NOW, 1, 2, (self.decision_evidence,),
        )
        self.evidence_proofs[self.decision_evidence] = self._evidence(
            self.decision_evidence,
        )
        self.lock = RequirementWorkflowScopeLock(
            self.project, 3, tuple(self.approved), (self.decision_lock,),
        )
        self.decisions = Decisions({self.decision_id: self.decision_proof})
        self.owner = self._owner()

    def _evidence(self, evidence_id):
        return EvidenceRequirementSourceProof(
            evidence_id, self.project, uuid.uuid4(), uuid.uuid4(), 3,
            evidence_id.bytes + evidence_id.bytes,
        )

    def _snapshot(self, requirement_id, version_id, project_evidence):
        baseline, capability, standard_evidence = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        return RequirementVersionValidationSnapshot(
            version_id, requirement_id, self.project, 1, "APPROVED", None,
            "Observable requirement", "Business rationale", "PLM", "HIGH",
            "MEDIUM", "STANDARD_FUNCTION", version_id.bytes + version_id.bytes,
            1, 1, 1, 0, 0, 0, 0,
            (RequirementSourceDraft(
                "PROJECT_EVIDENCE", project_evidence, None,
                (project_evidence,),
            ),),
            (RequirementAcceptanceDraft(
                "Result is observable", "Execute test", "Project dataset",
                "Windows 11", "Signed report",
            ),),
            (RequirementCapabilityAssessmentDraft(
                baseline, capability, "DIRECT", "Fully covered",
                "Use standard configuration", "HUMAN", "CONFIRMED",
                (RequirementAssessmentEvidenceDraft(
                    standard_evidence, "STANDARD",
                ), RequirementAssessmentEvidenceDraft(
                    project_evidence, "PROJECT",
                )),
            ),), (), (), (), (), True,
        )

    def _approved(self):
        requirement_id, version_id, evidence_id = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4(),
        )
        review_id, round_id = uuid.uuid4(), uuid.uuid4()
        snapshot = self._snapshot(requirement_id, version_id, evidence_id)
        self.evidence_proofs[evidence_id] = self._evidence(evidence_id)
        progress = ReviewRoundProgress(
            round_id, NOW, (self.reviewer,),
        ).record_decision(ReviewDecisionSnapshot(
            uuid.uuid4(), round_id, self.reviewer,
            ReviewDecisionKind.APPROVE, NOW,
        ))
        identity = ReviewIdentitySnapshot(
            review_id, "PROJECT", self.project, "REQ-03", requirement_id,
            "REQUIREMENT_ALL_V1", "APPROVED", None, 2,
        )
        self.review_proofs[(review_id, round_id)] = FixedReviewRoundSnapshot(
            identity, 1, version_id, self.actor, progress, (uuid.uuid4(),),
            1, uuid.uuid4(), snapshot.content_fingerprint, 1, NOW, (),
            uuid.uuid4(), NOW, NOW,
        )
        return RequirementWorkflowApprovedLock(
            snapshot, version_id, review_id, round_id,
        )

    def _owner(self, *, lock=None, evidence=None, decisions=None, reviews=None):
        return RequirementWorkflowQualificationOwner(
            repository=Repo(self.lock if lock is None else lock),
            current=self.current,
            evidence=Evidence(self.evidence_proofs) if evidence is None else evidence,
            decisions=self.decisions if decisions is None else decisions,
            reviews=Reviews(self.review_proofs) if reviews is None else reviews,
            clock=lambda: NOW,
        )

    def _query(self, item="REQUIREMENT_FORMAL_VERSIONS"):
        return CurrentChecklistQualificationQuery(
            b"s" * 32, self.trace, self.project, item,
        )

    def test_qualifies_complete_scope_with_stable_two_item_coherence(self):
        formal = self.owner.qualify_only_current_in_transaction(
            object(), self._query(),
        )
        acceptance = self.owner.qualify_only_current_in_transaction(
            object(), self._query("REQUIREMENT_ACCEPTANCE"),
        )

        self.assertEqual("REQUIREMENT", formal.stage_key)
        self.assertEqual(2, len(formal.subjects))
        self.assertEqual(3, self.lock.root_count)
        self.assertIn(self.decision_evidence, formal.evidence_refs)
        self.assertEqual(formal.coherence_key, acceptance.coherence_key)
        self.assertNotEqual(
            formal.qualification_fingerprint,
            acceptance.qualification_fingerprint,
        )

    def test_combined_owner_result_uses_one_locked_scope_scan(self):
        owner = self._owner()
        lock, result = owner.qualify_with_scope_in_transaction(
            object(), self._query("REQUIREMENT_ACCEPTANCE"),
        )
        self.assertIs(lock, self.lock)
        self.assertEqual("REQUIREMENT_ACCEPTANCE", result.item_key)
        self.assertEqual(1, owner._repo.calls)

    def test_checked_project_evidence_is_strictly_reused_and_decision_still_read(self):
        proofs = self.evidence_proofs

        class Checked:
            def current_issues_and_project_evidence(self, _tx, snapshot):
                evidence_id = snapshot.sources[0].evidence_refs[0]
                return (), (proofs[evidence_id],)

        self.current = Checked()
        only_decision = Evidence({
            self.decision_evidence: proofs[self.decision_evidence],
        })
        result = self._owner(evidence=only_decision).qualify_only_current_in_transaction(
            object(), self._query(),
        )
        self.assertEqual(len(result.subjects), 2)
        self.assertIn(self.decision_evidence, result.evidence_refs)

        first = self.approved[0].snapshot.sources[0].evidence_refs[0]
        bad = replace(proofs[first], project_id=uuid.uuid4())

        class Tampered:
            def current_issues_and_project_evidence(self, _tx, snapshot):
                evidence_id = snapshot.sources[0].evidence_refs[0]
                return (), (bad if evidence_id == first else proofs[evidence_id],)

        self.current = Tampered()
        with self.assertRaises(ChecklistQualificationError):
            self._owner(evidence=only_decision).qualify_only_current_in_transaction(
                object(), self._query(),
            )

    def test_rejects_current_issue_missing_scope_and_wrong_item(self):
        self.current.issues = ("PENDING_CONFIRMATION",)
        with self.assertRaises(ChecklistQualificationError):
            self.owner.qualify_only_current_in_transaction(object(), self._query())
        self.current.issues = ()
        with self.assertRaises(ChecklistQualificationError):
            self._owner(lock=False).qualify_only_current_in_transaction(
                object(), self._query(),
            )
        with self.assertRaises(ChecklistQualificationError):
            self.owner.qualify_only_current_in_transaction(
                object(), CurrentChecklistQualificationQuery(
                    b"s" * 32, self.trace, self.project, "SURVEY_CONCLUSION",
                ),
            )

    def test_rejects_evidence_and_review_drift(self):
        with self.assertRaises(ChecklistQualificationError):
            self._owner(evidence=Evidence({})).qualify_only_current_in_transaction(
                object(), self._query(),
            )
        first = self.approved[0]
        bad_review = replace(
            self.review_proofs[(first.review_id, first.review_round_id)],
            subject_fingerprint=b"z" * 32,
        )
        reviews = dict(self.review_proofs)
        reviews[(first.review_id, first.review_round_id)] = bad_review
        with self.assertRaises(ChecklistQualificationError):
            self._owner(reviews=Reviews(reviews)).qualify_only_current_in_transaction(
                object(), self._query(),
            )

    def test_rejects_wrong_or_missing_scope_decision(self):
        wrong = replace(self.decision_proof, decision_type="REJECT")
        with self.assertRaises(ChecklistQualificationError):
            self._owner(decisions=Decisions({self.decision_id: wrong})).qualify_only_current_in_transaction(
                object(), self._query(),
            )
        with self.assertRaises(ChecklistQualificationError):
            self._owner(decisions=Decisions({})).qualify_only_current_in_transaction(
                object(), self._query(),
            )

    def test_acceptance_item_rejects_incomplete_five_part_criterion(self):
        first = self.approved[0]
        broken_criterion = replace(
            first.snapshot.acceptance_criteria[0], required_environment="",
        )
        broken_snapshot = replace(
            first.snapshot, acceptance_criteria=(broken_criterion,),
        )
        broken = replace(first, snapshot=broken_snapshot)
        approved = tuple(sorted(
            (broken, self.approved[1]),
            key=lambda value: value.snapshot.requirement_id.int,
        ))
        lock = replace(self.lock, approved=approved)
        owner = self._owner(lock=lock)
        owner.qualify_only_current_in_transaction(object(), self._query())
        with self.assertRaises(ChecklistQualificationError):
            owner.qualify_only_current_in_transaction(
                object(), self._query("REQUIREMENT_ACCEPTANCE"),
            )

    def test_archived_requires_prior_decision_and_scope_is_canonical(self):
        archived = replace(self.decision_lock, requirement_state="ARCHIVED")
        lock = replace(self.lock, decisions=(archived,))
        result = self._owner(lock=lock).qualify_only_current_in_transaction(
            object(), self._query(),
        )
        self.assertEqual(2, len(result.subjects))
        with self.assertRaises(Exception):
            RequirementWorkflowScopeLock(
                self.project, 3, tuple(reversed(self.approved)),
                (self.decision_lock,),
            )


if __name__ == "__main__":
    unittest.main()
