"""Prototype-owned complete current-fact Workflow qualification.

This Owner is only useful after the Workflow registry explicitly installs it.
Every call re-proves the complete scope inside the caller's transaction; no
stored PASS, candidate DTO, or historic review alone authorizes qualification.
"""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.prototype_scope_proof import (
    PrototypeScopeDecisionAuditProof,
    PrototypeScopeDecisionAuditProofPort,
)
from plm_assistant.modules.document.application.prototype_workflow_integrity import (
    PrototypeWorkflowArtifactIntegrityProof,
    PrototypeWorkflowArtifactIntegrityPort,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.requirement.application.prototype_workflow_proof import (
    RequirementAcceptanceRefsProof,
    RequirementAcceptanceRefsProofPort,
)
from plm_assistant.modules.requirement.application.workflow_qualification import (
    RequirementWorkflowScopeLock,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState
from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification,
    ChecklistQualificationError,
    ChecklistQualificationReview,
    ChecklistQualificationSubject,
    CurrentChecklistQualificationQuery,
)

from ..domain.workflow_scope import (
    ApprovedPrototypeCandidate,
    CoverageLinkCandidate,
    CurrentRequirementCandidate,
    NotRequiredDecisionCandidate,
    partition_current_scope,
    require_complete_coverage,
)
from .current_version import PrototypeVersionCurrentFacts, PrototypeVersionCurrentValidator
from .workflow_scope_lock import PrototypeRootLock
from .workflow_version_links import PrototypeWorkflowVersionLinksLock


_ITEMS = frozenset({"PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"})


class RequirementScopePort(Protocol):
    def lock_complete_scope(self, transaction: object, *, project_id: uuid.UUID
                            ) -> RequirementWorkflowScopeLock | None: ...


class RequirementQualificationPort(Protocol):
    def qualify_only_current_in_transaction(
        self, transaction: object, query: CurrentChecklistQualificationQuery,
    ) -> AggregateChecklistQualification: ...


class PrototypeRootsPort(Protocol):
    def lock_current_roots(self, transaction: object, *, project_id: uuid.UUID
                           ) -> tuple[PrototypeRootLock, ...] | None: ...


class PrototypeVersionsPort(Protocol):
    def lock_current_versions_and_links(
        self, transaction: object, *, project_id: uuid.UUID,
        roots: tuple[PrototypeRootLock, ...],
    ) -> PrototypeWorkflowVersionLinksLock | None: ...


class ReviewRoundPort(Protocol):
    def get_round(self, transaction: object, scope: str,
                  project_id: uuid.UUID | None, review_id: uuid.UUID,
                  round_id: uuid.UUID) -> FixedReviewRoundSnapshot | None: ...


class PrototypeWorkflowQualificationOwner:
    def __init__(
        self, *, requirement_scope: RequirementScopePort,
        requirement_owner: RequirementQualificationPort,
        acceptance_refs: RequirementAcceptanceRefsProofPort,
        roots: PrototypeRootsPort, versions: PrototypeVersionsPort,
        current: PrototypeVersionCurrentValidator,
        artifact_integrity: PrototypeWorkflowArtifactIntegrityPort,
        decision_audit: PrototypeScopeDecisionAuditProofPort,
        reviews: ReviewRoundPort, clock=None,
    ) -> None:
        if any(value is None for value in (
                requirement_scope, requirement_owner, acceptance_refs,
                roots, versions, current, artifact_integrity,
                decision_audit, reviews)):
            raise ValueError("Prototype Workflow proof dependencies required")
        self._req_scope = requirement_scope
        self._req_owner = requirement_owner
        self._acceptance = acceptance_refs
        self._roots = roots
        self._versions = versions
        self._current = current
        self._integrity = artifact_integrity
        self._audit = decision_audit
        self._reviews = reviews
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def qualify_only_current_in_transaction(
        self, transaction: object, query: CurrentChecklistQualificationQuery,
    ) -> AggregateChecklistQualification:
        if (transaction is None or type(query) is not CurrentChecklistQualificationQuery
                or query.item_key not in _ITEMS):
            raise ChecklistQualificationError()
        query.__post_init__()
        try:
            now = self._now()
            root_locks = self._roots.lock_current_roots(
                transaction, project_id=query.project_id)
            if type(root_locks) is not tuple or any(
                    type(root) is not PrototypeRootLock for root in root_locks):
                raise ValueError("Prototype root scope unavailable")
            requirement_lock = self._req_scope.lock_complete_scope(
                transaction, project_id=query.project_id)
            if type(requirement_lock) is not RequirementWorkflowScopeLock:
                raise ValueError("Requirement scope unavailable")
            requirement_lock.__post_init__()
            requirement_qualification = (
                self._req_owner.qualify_only_current_in_transaction(
                    transaction, CurrentChecklistQualificationQuery(
                        query.session_token, query.trace_id,
                        query.project_id, "REQUIREMENT_ACCEPTANCE",
                    ),
                )
            )
            if (type(requirement_qualification) is not AggregateChecklistQualification
                    or requirement_qualification.project_id != query.project_id
                    or requirement_qualification.item_key != "REQUIREMENT_ACCEPTANCE"):
                raise ValueError("Requirement qualification unavailable")
            requirement_qualification.__post_init__()
            requirements = self._requirements(
                transaction, query.project_id, requirement_lock,
                requirement_qualification,
            )
            version_links = self._versions.lock_current_versions_and_links(
                transaction, project_id=query.project_id, roots=root_locks,
            )
            if type(version_links) is not PrototypeWorkflowVersionLinksLock:
                raise ValueError("Prototype versions unavailable")
            decisions, audit_ids = self._decisions(
                transaction, query.project_id, root_locks,
            )
            prototypes, subjects, physical = self._prototypes(
                transaction, query.project_id, version_links, now,
            )
            partition = partition_current_scope(
                project_id=query.project_id,
                requirements=requirements, decisions=decisions,
                prototypes=prototypes,
            )
            links = tuple(CoverageLinkCandidate(
                link.project_id, link.requirement_version_id,
                link.prototype_version_id, link.purpose,
                link.coverage.covered_acceptance_criterion_refs,
                tuple(item.acceptance_criterion_ref for item in
                      link.coverage.uncovered_acceptance_criteria),
                link.link_state,
            ) for link in version_links.active_links)
            if query.item_key == "PROTOTYPE_COVERAGE":
                require_complete_coverage(partition, links)
            all_subjects = tuple(sorted(
                (*requirement_qualification.subjects, *subjects),
                key=lambda value: (value.subject_type, value.subject_id.int,
                                   value.subject_version_id.int),
            ))
            scope = canonical_payload_fingerprint({
                "schema": "prototype-workflow-scope.v1",
                "project_id": str(query.project_id),
                "requirement_scope": requirement_qualification.scope_fingerprint.hex(),
                "roots": [self._root_payload(root) for root in root_locks],
                "approved_versions": [self._version_payload(value) for value in
                                      version_links.versions],
                "physical_artifacts": [
                    (str(value.document_version_id), value.content_sha256,
                     value.size_bytes) for value in physical
                ],
                "audit_events": [str(value) for value in audit_ids],
                "links": [self._link_payload(value) for value in
                          version_links.active_links],
            })
            qualification = AggregateChecklistQualification(
                query.project_id, "PROTOTYPE", query.item_key,
                all_subjects, requirement_qualification.scope_evidence,
                scope, canonical_payload_fingerprint({
                    "schema": "prototype-workflow-qualification.v1",
                    "item_key": query.item_key,
                    "scope_fingerprint": scope.hex(),
                    "complete_coverage": query.item_key == "PROTOTYPE_COVERAGE",
                }),
            )
            qualification.__post_init__()
            return qualification
        except ChecklistQualificationError:
            raise
        except Exception:
            raise ChecklistQualificationError() from None

    def _requirements(self, tx, project_id, lock, qualified):
        by_id = {value.subject_id: value for value in qualified.subjects}
        if (len(by_id) != len(lock.approved)
                or any(value.subject_type != "REQ-03"
                       for value in qualified.subjects)):
            raise ValueError("incomplete Requirement subjects")
        candidates = []
        for approved in lock.approved:
            snapshot = approved.snapshot
            subject = by_id.get(snapshot.requirement_id)
            if (subject is None
                    or subject.subject_version_id != snapshot.requirement_version_id
                    or not hmac.compare_digest(subject.content_fingerprint,
                                               snapshot.content_fingerprint)
                    or subject.review.review_id != approved.review_id
                    or subject.review.review_round_id != approved.review_round_id):
                raise ValueError("Requirement subject drift")
            refs = self._acceptance.prove_current_acceptance_refs(
                tx, project_id=project_id,
                requirement_id=snapshot.requirement_id,
                requirement_version_id=snapshot.requirement_version_id,
            )
            if (type(refs) is not RequirementAcceptanceRefsProof
                    or refs.project_id != project_id
                    or refs.requirement_id != snapshot.requirement_id
                    or refs.requirement_version_id != snapshot.requirement_version_id
                    or len(refs.criterion_refs) != snapshot.declared_acceptance_count):
                raise ValueError("Requirement acceptance refs unavailable")
            refs.__post_init__()
            candidates.append(CurrentRequirementCandidate(
                project_id, snapshot.requirement_id,
                snapshot.requirement_version_id, refs.criterion_refs,
            ))
        return tuple(candidates)

    def _decisions(self, tx, project_id, roots):
        candidates = []
        audit_ids = []
        for root in roots:
            if root.project_id != project_id:
                raise ValueError("cross-project Prototype root")
            if root.state != "NOT_REQUIRED":
                continue
            decision = root.decision
            if decision is None:
                raise ValueError("unexplained NOT_REQUIRED")
            audit = self._audit.prove_user_action(
                tx, project_id=project_id, prototype_id=root.prototype_id,
                confirmed_by=decision.confirmed_by,
                decided_at=decision.decided_at,
            )
            if (type(audit) is not PrototypeScopeDecisionAuditProof
                    or audit.project_id != project_id
                    or audit.prototype_id != root.prototype_id
                    or audit.actor_id != decision.confirmed_by):
                raise ValueError("decision Audit unavailable")
            if decision.review_id is not None:
                self._review(
                    tx, project_id=project_id,
                    subject_type="PRT_SCOPE_DECISION",
                    subject_id=root.prototype_id,
                    version_id=root.prototype_id,
                    fingerprint=decision.decision_fingerprint,
                    review_id=decision.review_id,
                    round_id=decision.review_round_id,
                    policy_code=None, now=None,
                )
            candidates.append(NotRequiredDecisionCandidate(
                project_id, root.prototype_id, decision.decision_id,
                decision.requirement_version_refs,
                decision.confirmed_by, decision.reason, decision.impact,
            ))
            audit_ids.append(audit.audit_event_id)
        return tuple(candidates), tuple(audit_ids)

    def _prototypes(self, tx, project_id, lock, now):
        candidates = []
        subjects = []
        physical = []
        for value in lock.versions:
            snapshot = value.snapshot
            if snapshot.project_id != project_id or snapshot.version_state != "APPROVED":
                raise ValueError("Prototype Version drift")
            facts = self._current.current_facts(tx, snapshot)
            if (type(facts) is not PrototypeVersionCurrentFacts
                    or len(facts.documents) != len(snapshot.artifact_refs)
                    or len(facts.requirements) != len(snapshot.requirement_refs)):
                raise ValueError("Prototype current facts unavailable")
            for document in facts.documents:
                proof = self._integrity.prove_actual_content(
                    tx, project_id=project_id, metadata=document,
                )
                if (type(proof) is not PrototypeWorkflowArtifactIntegrityProof
                        or proof.document_version_id != document.document_version_id
                        or proof.content_sha256 != document.content_sha256
                        or proof.size_bytes != document.size_bytes):
                    raise ValueError("Prototype artifact bytes unavailable")
                physical.append(proof)
            review = self._review(
                tx, project_id=project_id, subject_type="PRT-03",
                subject_id=snapshot.prototype_id,
                version_id=snapshot.prototype_version_id,
                fingerprint=bytes.fromhex(snapshot.content_fingerprint),
                review_id=value.review_id, round_id=value.review_round_id,
                policy_code="PROTOTYPE_ALL_V1", now=now,
            )
            subjects.append(ChecklistQualificationSubject(
                "PRT-03", snapshot.prototype_id,
                snapshot.prototype_version_id,
                bytes.fromhex(snapshot.content_fingerprint), (), review,
            ))
            candidates.append(ApprovedPrototypeCandidate(
                project_id, snapshot.prototype_id,
                snapshot.prototype_version_id,
                snapshot.prototype_version_id,
                tuple(ref.requirement_version_id for ref in
                      snapshot.requirement_refs), "ACTIVE", "APPROVED",
            ))
        return tuple(candidates), tuple(subjects), tuple(physical)

    def _review(self, tx, *, project_id, subject_type, subject_id, version_id,
                fingerprint, review_id, round_id, policy_code, now):
        fixed = self._reviews.get_round(
            tx, "PROJECT", project_id, review_id, round_id,
        )
        if type(fixed) is not FixedReviewRoundSnapshot:
            raise ValueError("Review unavailable")
        fixed.__post_init__()
        identity = fixed.review
        if (identity.review_id != review_id or identity.project_id != project_id
                or identity.scope != "PROJECT"
                or identity.subject_type != subject_type
                or identity.subject_id != subject_id
                or policy_code is not None and identity.policy_code != policy_code
                or identity.state != "APPROVED"
                or fixed.progress.round_id != round_id
                or fixed.progress.state is not ReviewRoundState.APPROVED
                or fixed.subject_version_id != version_id
                or not hmac.compare_digest(fixed.subject_fingerprint,
                                           fingerprint)):
            raise ValueError("Review fact mismatch")
        if now is None:
            return None  # optional NOT_REQUIRED Review was proved but is not a subject
        return ChecklistQualificationReview(
            review_id, round_id, project_id, subject_id, version_id,
            fixed.round_lock_version, fixed.subject_fingerprint, now,
            identity.subject_type, identity.policy_code,
        )

    def _now(self) -> datetime:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise ValueError("invalid Workflow clock")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _root_payload(value: PrototypeRootLock):
        decision = value.decision
        return {
            "prototype_id": str(value.prototype_id),
            "state": value.state,
            "lock_version": value.lock_version,
            "current_version": (None if value.current_approved_version_ref is None
                                else str(value.current_approved_version_ref)),
            "decision": None if decision is None else {
                "id": str(decision.decision_id),
                "fingerprint": decision.decision_fingerprint.hex(),
                "review_round_id": (None if decision.review_round_id is None
                                    else str(decision.review_round_id)),
                "requirement_versions": [str(ref) for ref in
                                         decision.requirement_version_refs],
            },
        }

    @staticmethod
    def _version_payload(value):
        return {
            "version_id": str(value.snapshot.prototype_version_id),
            "fingerprint": value.snapshot.content_fingerprint,
            "review_round_id": str(value.review_round_id),
            "approval_result_id": str(value.approval_result_id),
        }

    @staticmethod
    def _link_payload(value):
        return {
            "link_id": str(value.requirement_prototype_link_id),
            "requirement_version_id": str(value.requirement_version_id),
            "prototype_version_id": str(value.prototype_version_id),
            "purpose": value.purpose,
            "coverage": {
                "covered": [str(ref) for ref in
                            value.coverage.covered_acceptance_criterion_refs],
                "uncovered": [(str(item.acceptance_criterion_ref), item.reason)
                              for item in value.coverage.uncovered_acceptance_criteria],
            },
        }
