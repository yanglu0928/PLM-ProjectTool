from __future__ import annotations

import unittest
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.project.application.reviewers import (
    ProjectReviewerFacts,
    ReviewReviewerEligibilityError,
)
from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView,
    VersionArtifactRef,
    VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.approval_trace import (
    PrototypeApprovalTraceError,
)
from plm_assistant.modules.prototype.application.current_version import (
    PrototypeVersionCurrentValidator,
)
from plm_assistant.modules.prototype.application.review_subject import (
    PrototypeReviewLock,
    PrototypeReviewSubjectOwner,
)
from plm_assistant.modules.prototype.application.version_input_proofs import (
    PrototypeVersionTemplateProof,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.review.application.create_review import CreatedReviewRef
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
    ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.application.subject_start import (
    ReviewSubjectAccessDenied,
    ReviewSubjectStartRequest,
)
from plm_assistant.modules.review.application.subject_transition import (
    ReviewSubjectTransition,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind,
    ReviewDecisionSnapshot,
    ReviewRoundProgress,
    ReviewRoundState,
    ReviewWithdrawalSnapshot,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


class PrototypeReviewSubjectTests(unittest.TestCase):
    def setUp(self):
        self.actor, self.reviewer = uuid.uuid4(), uuid.uuid4()
        self.project, self.prototype, self.version = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.template, self.template_version = uuid.uuid4(), uuid.uuid4()
        self.requirement, self.requirement_version = uuid.uuid4(), uuid.uuid4()
        self.document, self.review, self.round = (
            uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
        self.snapshot = PrototypeVersionInitialView(
            self.version, self.prototype, self.project, 1, None,
            self.template, self.template_version,
            (VersionArtifactRef("DOCUMENT_VERSION", self.document),),
            (VersionRequirementRef(
                self.requirement, self.requirement_version),),
            {"interactions": []}, {"covered": 1}, "1" * 64, NOW,
        )
        self.lock = PrototypeReviewLock(
            self.snapshot, "ACTIVE", 0, None, self.version, None, None,
        )
        self.identity = ReviewIdentitySnapshot(
            self.review, "PROJECT", self.project, "PRT-03", self.prototype,
            "PROTOTYPE_ALL_V1", "DRAFT", None, 0,
        )
        self.request = ReviewSubjectStartRequest(
            self.actor, self.identity, self.round, self.version,
            (self.reviewer,),
        )
        self.repository, self.reviewers, self.current, self.audit, self.trace = (
            Mock() for _ in range(5))
        self.repository.lock_subject.return_value = self.lock
        self.repository.active_prototype_exists.return_value = True
        self.repository.assert_terminal_consumed = Mock()
        self.trace.assert_recorded_in_transaction = Mock()
        self.terminal_result = uuid.uuid4()
        self.repository.consume_terminal.return_value = self.terminal_result
        self.repository.assert_terminal_consumed.return_value = (
            self.terminal_result)
        self.repository.approval_result_id.return_value = self.terminal_result
        self.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(
                self.reviewer, self.project, "CUSTOMER_MANAGER"),
        )
        self.current.current_issues.return_value = ()
        self.owner = PrototypeReviewSubjectOwner(
            repository=self.repository, reviewers=self.reviewers,
            current=self.current, audit=self.audit,
            approval_trace=self.trace, clock=lambda: NOW,
        )
        self.tx = object()

    def test_create_owner_binds_latest_draft_and_policy(self):
        proof = self.owner.authorize_create(
            self.tx, user_id=self.actor, project_id=self.project,
            subject_type="PRT-03", subject_id=self.prototype,
            subject_version_id=self.version,
        )
        self.assertEqual(proof.policy_code, "PROTOTYPE_ALL_V1")
        created = CreatedReviewRef(
            self.review, self.project, "PRT-03", self.prototype,
            "PROTOTYPE_ALL_V1", self.actor, NOW,
        )
        self.assertTrue(self.owner.authorize_replay(
            self.tx, user_id=self.actor, review=created,
        ))
        self.repository.lock_subject.return_value = replace(
            self.lock, latest_version_id=uuid.uuid4(),
        )
        self.assertIsNone(self.owner.authorize_create(
            self.tx, user_id=self.actor, project_id=self.project,
            subject_type="PRT-03", subject_id=self.prototype,
            subject_version_id=self.version,
        ))

    def test_prepare_revalidates_and_finalizes_exact_binding(self):
        prepared = self.owner.prepare_start_in_transaction(
            self.tx, self.request,
        )
        self.assertEqual(
            prepared.content_fingerprint,
            bytes.fromhex(self.snapshot.content_fingerprint),
        )
        self.current.current_issues.assert_called_once_with(
            self.tx, self.snapshot,
        )
        self.owner.finalize_start_in_transaction(self.tx, self.request)
        self.repository.bind_start.assert_called_once_with(
            self.tx, before=self.lock, review_id=self.review,
            round_id=self.round, actor_id=self.actor,
        )

    def test_reviewer_or_current_issue_fails_closed(self):
        self.reviewers.qualify_in_transaction.side_effect = (
            ReviewReviewerEligibilityError())
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)
        self.reviewers.qualify_in_transaction.side_effect = None
        self.reviewers.qualify_in_transaction.return_value = (
            ProjectReviewerFacts(
                self.reviewer, self.project, "CUSTOMER_MANAGER"),
        )
        self.current.current_issues.return_value = (
            "REQUIREMENT_UNAVAILABLE",)
        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.prepare_start_in_transaction(self.tx, self.request)

    def test_terminal_approval_revalidates_and_consumes(self):
        transition, active = self._terminal("APPROVE")
        self.owner.require_transition_access_in_transaction(
            self.tx, transition,
        )
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="APPROVED",
        )
        self.trace.record_in_transaction.assert_called_once_with(
            self.tx, snapshot=active.snapshot,
            review_state_result_id=self.terminal_result,
            review_id=self.review, review_round_id=self.round,
            actor_id=self.reviewer,
            trace_id=transition.trace_id,
        )
        self.owner.assert_terminal_consumed_in_transaction(
            self.tx, transition,
        )
        self.repository.assert_terminal_consumed.assert_called_once_with(
            self.tx, transition=transition, version_state="APPROVED",
        )
        self.trace.assert_recorded_in_transaction.assert_called_once_with(
            self.tx, prototype_version_id=self.version,
            prototype_id=self.prototype, project_id=self.project,
            review_state_result_id=self.terminal_result,
            review_id=self.review, review_round_id=self.round,
            actor_id=self.reviewer,
        )
        event = self.audit.append.call_args.args[1]
        self.assertEqual(event.action, "PROTOTYPE_VERSION_APPROVED")
        self.assertEqual(event.after_state, "APPROVED")

    def test_terminal_approval_trace_failure_fails_before_audit(self):
        transition, _ = self._terminal("APPROVE")
        self.trace.record_in_transaction.side_effect = (
            PrototypeApprovalTraceError())

        with self.assertRaises(ReviewSubjectAccessDenied):
            self.owner.consume_terminal_in_transaction(self.tx, transition)

        self.repository.consume_terminal.assert_called_once()
        self.audit.append.assert_not_called()

    def test_approved_transition_replay_rechecks_trace_manifest(self):
        approved = replace(self.lock, snapshot=replace(
            self.snapshot, version_state="APPROVED"),
            prototype_lock_version=2, current_approved_version_ref=self.version,
            review_ref=self.review, review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = approved
        result = SimpleNamespace(
            subject_version_id=self.version, review_id=self.review,
            round_id=self.round, state=ReviewRoundState.APPROVED,
        )

        self.owner.require_transition_replay_access_in_transaction(
            self.tx, actor_id=self.reviewer, review=self.identity,
            result=result,
        )

        self.repository.approval_result_id.assert_called_once_with(
            self.tx, prototype_version_id=self.version,
            prototype_id=self.prototype, project_id=self.project,
            review_id=self.review, review_round_id=self.round,
            approved_by=self.reviewer,
        )
        self.trace.assert_recorded_in_transaction.assert_called_once_with(
            self.tx, prototype_version_id=self.version,
            prototype_id=self.prototype, project_id=self.project,
            review_state_result_id=self.terminal_result,
            review_id=self.review, review_round_id=self.round,
            actor_id=self.reviewer,
        )

    def test_withdrawal_does_not_require_stale_inputs(self):
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            prototype_lock_version=1, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        other = uuid.uuid4()
        progress = ReviewRoundProgress(
            self.round, NOW, (self.reviewer, other),
        )
        transition = ReviewSubjectTransition(
            self.actor, uuid.uuid4(), self._fixed(progress),
            progress.withdraw(ReviewWithdrawalSnapshot(
                self.actor, NOW, "Input changed")), NOW,
        )
        self.current.current_issues.return_value = ("ARTIFACT_UNAVAILABLE",)
        self.owner.require_transition_access_in_transaction(
            self.tx, transition,
        )
        self.owner.consume_terminal_in_transaction(self.tx, transition)
        self.repository.consume_terminal.assert_called_once_with(
            self.tx, before=active, transition=transition,
            version_state="RETURNED",
        )
        self.current.current_issues.assert_not_called()
        self.trace.record_in_transaction.assert_not_called()

    def _terminal(self, decision_name):
        active = replace(
            self.lock,
            snapshot=replace(self.snapshot, version_state="IN_REVIEW"),
            prototype_lock_version=1, review_ref=self.review,
            review_round_ref=self.round,
        )
        self.repository.lock_subject.return_value = active
        progress = ReviewRoundProgress(self.round, NOW, (self.reviewer,))
        decision = ReviewDecisionSnapshot(
            uuid.uuid4(), self.round, self.reviewer,
            ReviewDecisionKind[decision_name], NOW,
        )
        return ReviewSubjectTransition(
            self.reviewer, uuid.uuid4(), self._fixed(progress),
            progress.record_decision(decision), NOW,
        ), active

    def _fixed(self, progress):
        review = replace(
            self.identity, state="IN_REVIEW", active_round_id=self.round,
            lock_version=1,
        )
        return FixedReviewRoundSnapshot(
            review, 1, self.version, self.actor, progress,
            tuple(uuid.uuid4() for _ in progress.reviewer_ids), 0,
            uuid.uuid4(), bytes.fromhex(self.snapshot.content_fingerprint), 1,
            NOW, (), uuid.uuid4(), NOW, None,
        )


class PrototypeVersionCurrentValidatorTests(unittest.TestCase):
    def setUp(self):
        self.project, self.prototype = uuid.uuid4(), uuid.uuid4()
        self.template, self.template_version = uuid.uuid4(), uuid.uuid4()
        self.requirement, self.requirement_version = uuid.uuid4(), uuid.uuid4()
        self.document = uuid.uuid4()
        self.templates, self.requirements, self.documents = (
            Mock() for _ in range(3))
        self.templates.prove.return_value = PrototypeVersionTemplateProof(
            self.template, self.template_version, "PROJECT", self.project,
            1, "2" * 64,
        )
        self.requirements.prove.return_value = (
            PrototypeApprovedRequirementVersionProof(
                self.project, self.requirement, self.requirement_version, 1,
                "3" * 64, uuid.uuid4(), uuid.uuid4(),
            )
        )
        self.documents.prove_for_prototype_version.return_value = (
            PrototypeVersionDocumentArtifactProof(
                self.document, uuid.uuid4(), "PROJECT", self.project,
                "4" * 64, 10, "application/pdf",
            )
        )
        self.validator = PrototypeVersionCurrentValidator(
            templates=self.templates, requirements=self.requirements,
            documents=self.documents,
        )
        self.snapshot = self._snapshot()

    def _snapshot(self):
        artifacts = (VersionArtifactRef("DOCUMENT_VERSION", self.document),)
        requirements = (VersionRequirementRef(
            self.requirement, self.requirement_version),)
        payload = {
            "project_id": str(self.project),
            "prototype_id": str(self.prototype),
            "expected_lock_version": 0,
            "template_id": str(self.template),
            "template_version_id": str(self.template_version),
            "artifact_refs": [("DOCUMENT_VERSION", str(self.document))],
            "requirement_refs": [(
                str(self.requirement), str(self.requirement_version))],
            "interaction_spec": {"interactions": []},
            "coverage_summary": {"covered": 1},
            "template_fingerprint": "2" * 64,
            "artifact_proofs": [(
                "DOCUMENT_VERSION", str(self.document), "4" * 64)],
            "requirement_proofs": [(
                str(self.requirement), str(self.requirement_version),
                "3" * 64)],
        }
        return PrototypeVersionInitialView(
            uuid.uuid4(), self.prototype, self.project, 1, None,
            self.template, self.template_version, artifacts, requirements,
            {"interactions": []}, {"covered": 1},
            canonical_payload_fingerprint(payload).hex(), NOW,
            expected_lock_version=0,
        )

    def test_reproves_inputs_and_content_fingerprint(self):
        self.assertEqual(
            self.validator.current_issues(object(), self.snapshot), (),
        )
        self.requirements.prove.return_value = None
        self.assertEqual(
            self.validator.current_issues(object(), self.snapshot),
            ("REQUIREMENT_UNAVAILABLE",),
        )

    def test_content_drift_and_noncanonical_structure_fail_closed(self):
        drift = replace(self.snapshot, coverage_summary={"covered": 2})
        self.assertEqual(
            self.validator.current_issues(object(), drift),
            ("CONTENT_FINGERPRINT_MISMATCH",),
        )
        invalid = replace(self.snapshot, artifact_refs=())
        self.assertEqual(
            self.validator.current_issues(object(), invalid),
            ("STRUCTURE_INVALID",),
        )


if __name__ == "__main__":
    unittest.main()
