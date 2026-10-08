"""Requirement-owned aggregate current-fact qualification for Workflow."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from plm_assistant.modules.evidence.application.requirement_source_proof import (
    EvidenceRequirementSourceProof,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState
from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification,
    ChecklistQualificationError,
    ChecklistQualificationEvidence,
    ChecklistQualificationReview,
    ChecklistQualificationSubject,
    CurrentChecklistQualificationQuery,
)

from .human_decision_source_proof import RequirementHumanDecisionSourceProof
from .validate_version import (
    RequirementVersionCurrentValidator,
    RequirementVersionValidationSnapshot,
)


_ITEMS = frozenset({"REQUIREMENT_FORMAL_VERSIONS", "REQUIREMENT_ACCEPTANCE"})


class RequirementWorkflowQualificationError(RuntimeError):
    def __init__(self) -> None:
        super().__init__("REQUIREMENT_WORKFLOW_NOT_QUALIFIED")


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _version(value: object) -> bool:
    return type(value) is int and 0 <= value < 2**63


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


@dataclass(frozen=True, slots=True)
class RequirementWorkflowApprovedLock:
    """One ACTIVE root and its current, latest APPROVED immutable version."""

    snapshot: RequirementVersionValidationSnapshot
    latest_version_id: uuid.UUID
    review_id: uuid.UUID
    review_round_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not RequirementVersionValidationSnapshot
                or not all(_id(value) for value in (
                    self.latest_version_id, self.review_id,
                    self.review_round_id,
                ))
                or self.snapshot.version_state != "APPROVED"
                or self.latest_version_id != self.snapshot.requirement_version_id):
            raise RequirementWorkflowQualificationError()


@dataclass(frozen=True, slots=True)
class RequirementWorkflowDecisionLock:
    """A non-active root whose exclusion is explained by a formal decision."""

    requirement_id: uuid.UUID
    requirement_state: str
    decision_id: uuid.UUID
    requirement_lock_version: int

    def __post_init__(self) -> None:
        if (not _id(self.requirement_id) or not _id(self.decision_id)
                or self.requirement_state not in {
                    "DEFERRED", "REJECTED", "ARCHIVED",
                }
                or not _version(self.requirement_lock_version)):
            raise RequirementWorkflowQualificationError()


@dataclass(frozen=True, slots=True)
class RequirementWorkflowScopeLock:
    """Complete project Requirement scope observed under database locks."""

    project_id: uuid.UUID
    root_count: int
    approved: tuple[RequirementWorkflowApprovedLock, ...]
    decisions: tuple[RequirementWorkflowDecisionLock, ...]

    def __post_init__(self) -> None:
        if (not _id(self.project_id)
                or type(self.root_count) is not int or self.root_count <= 0
                or type(self.approved) is not tuple or not self.approved
                or type(self.decisions) is not tuple
                or self.root_count != len(self.approved) + len(self.decisions)
                or any(type(value) is not RequirementWorkflowApprovedLock
                       for value in self.approved)
                or any(type(value) is not RequirementWorkflowDecisionLock
                       for value in self.decisions)):
            raise RequirementWorkflowQualificationError()
        for value in self.approved:
            value.__post_init__()
        for value in self.decisions:
            value.__post_init__()
        approved_order = tuple(
            value.snapshot.requirement_id.int for value in self.approved
        )
        decision_order = tuple(value.requirement_id.int for value in self.decisions)
        identities = tuple(
            value.snapshot.requirement_id for value in self.approved
        ) + tuple(value.requirement_id for value in self.decisions)
        if (approved_order != tuple(sorted(approved_order))
                or decision_order != tuple(sorted(decision_order))
                or len(set(identities)) != self.root_count
                or any(value.snapshot.project_id != self.project_id
                       for value in self.approved)):
            raise RequirementWorkflowQualificationError()


class RequirementWorkflowQualificationRepositoryPort(Protocol):
    def lock_complete_scope(
        self, transaction: object, *, project_id: uuid.UUID,
    ) -> RequirementWorkflowScopeLock | None: ...


class RequirementWorkflowEvidencePort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        evidence_id: uuid.UUID,
    ) -> EvidenceRequirementSourceProof | None: ...


class RequirementWorkflowDecisionPort(Protocol):
    def prove(
        self, transaction: object, *, project_id: uuid.UUID,
        decision_id: uuid.UUID,
    ) -> RequirementHumanDecisionSourceProof | None: ...


class RequirementWorkflowReviewPort(Protocol):
    def get_round(
        self, transaction: object, scope: str,
        project_id: uuid.UUID | None, review_id: uuid.UUID,
        round_id: uuid.UUID,
    ) -> FixedReviewRoundSnapshot | None: ...


class RequirementWorkflowQualificationPolicy:
    def qualify(
        self, *, item_key: str, lock: RequirementWorkflowScopeLock,
        subjects: tuple[ChecklistQualificationSubject, ...],
        scope_evidence: tuple[ChecklistQualificationEvidence, ...],
        decisions: tuple[RequirementHumanDecisionSourceProof, ...],
    ) -> AggregateChecklistQualification:
        if (item_key not in _ITEMS
                or type(lock) is not RequirementWorkflowScopeLock
                or type(subjects) is not tuple or not subjects
                or type(scope_evidence) is not tuple
                or type(decisions) is not tuple
                or any(type(value) is not RequirementHumanDecisionSourceProof
                       for value in decisions)):
            raise RequirementWorkflowQualificationError()
        lock.__post_init__()
        scope_payload = {
            "schema": "requirement-workflow-scope.v1",
            "project_id": str(lock.project_id),
            "root_count": lock.root_count,
            "subjects": [self._subject_payload(value) for value in subjects],
            "decisions": [{
                "decision_id": str(value.decision_id),
                "requirement_id": str(value.requirement_id),
                "decision_type": value.decision_type,
                "before_version": value.before_version,
                "after_version": value.after_version,
                "evidence_refs": [str(ref) for ref in value.evidence_refs],
            } for value in decisions],
            "scope_evidence": [self._evidence_payload(value)
                               for value in scope_evidence],
        }
        scope_fingerprint = canonical_payload_fingerprint(scope_payload)
        qualification_fingerprint = canonical_payload_fingerprint({
            "schema": "requirement-workflow-qualification.v1",
            "item_key": item_key,
            "scope_fingerprint": scope_fingerprint.hex(),
            "acceptance_counts": [
                value.snapshot.declared_acceptance_count
                for value in lock.approved
            ],
        })
        return AggregateChecklistQualification(
            lock.project_id, "REQUIREMENT", item_key, subjects,
            scope_evidence, scope_fingerprint, qualification_fingerprint,
        )

    @staticmethod
    def _evidence_payload(value: ChecklistQualificationEvidence) -> dict[str, object]:
        return {
            "evidence_id": str(value.evidence_id),
            "lock_version": value.observed_lock_version,
            "content_fingerprint": value.content_fingerprint.hex(),
        }

    @classmethod
    def _subject_payload(cls, value: ChecklistQualificationSubject) -> dict[str, object]:
        return {
            "subject_type": value.subject_type,
            "subject_id": str(value.subject_id),
            "subject_version_id": str(value.subject_version_id),
            "content_fingerprint": value.content_fingerprint.hex(),
            "review_id": str(value.review.review_id),
            "review_round_id": str(value.review.review_round_id),
            "review_lock_version": value.review.observed_lock_version,
            "evidence": [cls._evidence_payload(item) for item in value.evidence],
        }


class RequirementWorkflowQualificationOwner:
    def __init__(
        self, *, repository: RequirementWorkflowQualificationRepositoryPort,
        current: RequirementVersionCurrentValidator,
        evidence: RequirementWorkflowEvidencePort,
        decisions: RequirementWorkflowDecisionPort,
        reviews: RequirementWorkflowReviewPort,
        policy: RequirementWorkflowQualificationPolicy | None = None,
        clock=None,
    ) -> None:
        if any(value is None for value in (
                repository, current, evidence, decisions, reviews)):
            raise ValueError("Requirement Workflow qualification dependencies required")
        self._repo, self._current = repository, current
        self._evidence, self._decisions, self._reviews = (
            evidence, decisions, reviews,
        )
        self._policy = policy or RequirementWorkflowQualificationPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> AggregateChecklistQualification:
        return self.qualify_with_scope_in_transaction(transaction, query)[1]

    def qualify_with_scope_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> tuple[RequirementWorkflowScopeLock, AggregateChecklistQualification]:
        """Return Owner-locked complete scope and qualification in one scan."""
        if (transaction is None
                or type(query) is not CurrentChecklistQualificationQuery
                or query.item_key not in _ITEMS):
            raise ChecklistQualificationError()
        query.__post_init__()
        try:
            lock = self._repo.lock_complete_scope(
                transaction, project_id=query.project_id,
            )
            if type(lock) is not RequirementWorkflowScopeLock:
                raise RequirementWorkflowQualificationError()
            lock.__post_init__()
            if lock.project_id != query.project_id:
                raise RequirementWorkflowQualificationError()
            now = self._now()
            subjects = tuple(
                self._subject(transaction, query, approved, now)
                for approved in lock.approved
            )
            decision_proofs, scope_evidence = self._scope_decisions(
                transaction, query, lock.decisions, now,
            )
            result = self._policy.qualify(
                item_key=query.item_key, lock=lock, subjects=subjects,
                scope_evidence=scope_evidence, decisions=decision_proofs,
            )
            result.__post_init__()
            return lock, result
        except ChecklistQualificationError:
            raise
        except Exception:
            raise ChecklistQualificationError() from None

    def _subject(self, tx, query, approved, now):
        snapshot = approved.snapshot
        issues = self._current.current_issues(tx, snapshot)
        if type(issues) is not tuple or issues:
            raise RequirementWorkflowQualificationError()
        if (query.item_key == "REQUIREMENT_ACCEPTANCE"
                and (not snapshot.acceptance_criteria
                     or any(
                         type(value) is not str or not value
                         or value.strip() != value
                         for criterion in snapshot.acceptance_criteria
                         for value in (
                             criterion.observable_result,
                             criterion.verification_method,
                             criterion.required_data,
                             criterion.required_environment,
                             criterion.evidence_requirement,
                         )
                     ))):
            raise RequirementWorkflowQualificationError()
        evidence_ids = {
            evidence_id
            for source in snapshot.sources
            for evidence_id in source.evidence_refs
        } | {
            ref.evidence_id
            for assessment in snapshot.capability_assessments
            for ref in assessment.evidence_refs
            if ref.evidence_role == "PROJECT"
        }
        evidence = self._prove_evidence(tx, query.project_id, evidence_ids, now)
        review = self._prove_review(tx, approved, now)
        return ChecklistQualificationSubject(
            "REQ-03", snapshot.requirement_id,
            snapshot.requirement_version_id, snapshot.content_fingerprint,
            evidence, review,
        )

    def _scope_decisions(self, tx, query, locks, now):
        proofs = []
        evidence_ids: set[uuid.UUID] = set()
        for locked in locks:
            proof = self._decisions.prove(
                tx, project_id=query.project_id,
                decision_id=locked.decision_id,
            )
            if (type(proof) is not RequirementHumanDecisionSourceProof
                    or proof.decision_id != locked.decision_id
                    or proof.requirement_id != locked.requirement_id
                    or proof.project_id != query.project_id
                    or proof.decision_type not in {"DEFER", "REJECT"}
                    or not _id(proof.decided_by)
                    or locked.requirement_state == "DEFERRED"
                       and proof.decision_type != "DEFER"
                    or locked.requirement_state == "REJECTED"
                       and proof.decision_type != "REJECT"
                    or not _utc(proof.decided_at)
                    or not _version(proof.before_version)
                    or proof.after_version != proof.before_version + 1
                    or type(proof.evidence_refs) is not tuple
                    or not proof.evidence_refs
                    or len(set(proof.evidence_refs)) != len(proof.evidence_refs)
                    or proof.evidence_refs != tuple(sorted(
                        proof.evidence_refs, key=lambda value: value.int,
                    ))
                    or any(not _id(value) for value in proof.evidence_refs)):
                raise RequirementWorkflowQualificationError()
            proofs.append(proof)
            evidence_ids.update(proof.evidence_refs)
        return (
            tuple(proofs),
            self._prove_evidence(tx, query.project_id, evidence_ids, now)
            if evidence_ids else (),
        )

    def _prove_evidence(self, tx, project_id, evidence_ids, now):
        if not evidence_ids:
            raise RequirementWorkflowQualificationError()
        values = []
        for evidence_id in sorted(evidence_ids, key=lambda value: value.int):
            proof = self._evidence.prove(
                tx, project_id=project_id, evidence_id=evidence_id,
            )
            if (type(proof) is not EvidenceRequirementSourceProof
                    or proof.evidence_id != evidence_id
                    or proof.project_id != project_id
                    or not _id(proof.document_id)
                    or not _id(proof.document_version_id)
                    or not _version(proof.observed_lock_version)
                    or type(proof.content_fingerprint) is not bytes
                    or len(proof.content_fingerprint) != 32):
                raise RequirementWorkflowQualificationError()
            values.append(ChecklistQualificationEvidence(
                proof.evidence_id, proof.project_id,
                proof.observed_lock_version, proof.content_fingerprint, now,
            ))
        return tuple(values)

    def _prove_review(self, tx, approved, now):
        snapshot = approved.snapshot
        fixed = self._reviews.get_round(
            tx, "PROJECT", snapshot.project_id,
            approved.review_id, approved.review_round_id,
        )
        if type(fixed) is not FixedReviewRoundSnapshot:
            raise RequirementWorkflowQualificationError()
        fixed.__post_init__()
        identity = fixed.review
        if (identity.review_id != approved.review_id
                or identity.scope != "PROJECT"
                or identity.project_id != snapshot.project_id
                or identity.subject_type != "REQ-03"
                or identity.subject_id != snapshot.requirement_id
                or identity.policy_code != "REQUIREMENT_ALL_V1"
                or identity.state != "APPROVED"
                or fixed.progress.round_id != approved.review_round_id
                or fixed.progress.state is not ReviewRoundState.APPROVED
                or fixed.subject_version_id != snapshot.requirement_version_id
                or not hmac.compare_digest(
                    fixed.subject_fingerprint, snapshot.content_fingerprint,
                )):
            raise RequirementWorkflowQualificationError()
        return ChecklistQualificationReview(
            identity.review_id, fixed.progress.round_id,
            snapshot.project_id, snapshot.requirement_id,
            snapshot.requirement_version_id, fixed.round_lock_version,
            fixed.subject_fingerprint, now, identity.subject_type,
            identity.policy_code,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise RequirementWorkflowQualificationError()
        return now.astimezone(timezone.utc)
