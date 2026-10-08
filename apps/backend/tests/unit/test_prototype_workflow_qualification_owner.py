"""Prototype Owner must prove full Requirement scope, decisions and artifacts."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from plm_assistant.modules.audit.application.prototype_scope_proof import (
    PrototypeScopeDecisionAuditProof,
)
from plm_assistant.modules.document.application.prototype_artifact_proof import (
    PrototypeVersionDocumentArtifactProof,
)
from plm_assistant.modules.document.application.prototype_workflow_integrity import (
    PrototypeWorkflowArtifactIntegrityProof,
)
from plm_assistant.modules.prototype.application.create_version import (
    PrototypeVersionInitialView, VersionArtifactRef, VersionRequirementRef,
)
from plm_assistant.modules.prototype.application.current_version import (
    PrototypeVersionCurrentFacts,
)
from plm_assistant.modules.prototype.application.requirement_links import (
    RequirementPrototypeCoverage, RequirementPrototypeLinkView,
)
from plm_assistant.modules.prototype.application.version_input_proofs import (
    PrototypeVersionTemplateProof,
)
from plm_assistant.modules.prototype.application.workflow_qualification import (
    PrototypeWorkflowQualificationOwner,
)
from plm_assistant.modules.prototype.application.workflow_scope_lock import (
    PrototypeDecisionLock, PrototypeRootLock,
)
from plm_assistant.modules.prototype.application.workflow_version_links import (
    PrototypeWorkflowVersionLinksLock, PrototypeWorkflowVersionLock,
)
from plm_assistant.modules.requirement.application.create_version import (
    RequirementAcceptanceDraft,
)
from plm_assistant.modules.requirement.application.prototype_version_proof import (
    PrototypeApprovedRequirementVersionProof,
)
from plm_assistant.modules.requirement.application.prototype_workflow_proof import (
    RequirementAcceptanceRefsProof,
)
from plm_assistant.modules.requirement.application.validate_version import (
    RequirementVersionValidationSnapshot,
)
from plm_assistant.modules.requirement.application.workflow_qualification import (
    RequirementWorkflowApprovedLock, RequirementWorkflowScopeLock,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import (
    ReviewDecisionKind, ReviewDecisionSnapshot, ReviewRoundProgress,
)
from plm_assistant.modules.workflow.application.checklist_qualification import (
    AggregateChecklistQualification, ChecklistQualificationError,
    ChecklistQualificationEvidence, ChecklistQualificationReview,
    ChecklistQualificationSubject, CurrentChecklistQualificationQuery,
)


NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


class _RequirementOwner:
    def __init__(self, lock, qualification):
        self.lock, self.qualification = lock, qualification

    def qualify_with_scope_in_transaction(self, *_a):
        return self.lock, self.qualification


class _Acceptance:
    def __init__(self, proof): self.proof = proof
    def prove_current_acceptance_refs(self, *_a, **_k): return self.proof


class _Roots:
    def __init__(self, value): self.value = value
    def lock_current_roots(self, *_a, **_k): return self.value


class _Versions:
    def __init__(self, value): self.value = value
    def lock_current_versions_and_links(self, *_a, **_k): return self.value


class _Current:
    def __init__(self, value): self.value = value
    def current_facts(self, *_a): return self.value


class _Integrity:
    def __init__(self, value): self.value = value
    def prove_actual_content(self, *_a, **_k): return self.value


class _Audit:
    def __init__(self, value): self.value = value
    def prove_user_action(self, *_a, **_k): return self.value


class _Reviews:
    def __init__(self, value=None): self.value = value
    def get_round(self, *_a): return self.value


def _review(project, subject, version, fingerprint, subject_type, policy):
    reviewer, actor = uuid.uuid4(), uuid.uuid4()
    review_id, round_id = uuid.uuid4(), uuid.uuid4()
    progress = ReviewRoundProgress(round_id, NOW, (reviewer,)).record_decision(
        ReviewDecisionSnapshot(uuid.uuid4(), round_id, reviewer,
                               ReviewDecisionKind.APPROVE, NOW))
    identity = ReviewIdentitySnapshot(
        review_id, "PROJECT", project, subject_type, subject, policy,
        "APPROVED", None, 2,
    )
    fixed = FixedReviewRoundSnapshot(
        identity, 1, version, actor, progress, (uuid.uuid4(),),
        1, uuid.uuid4(), fingerprint, 1, NOW, (), uuid.uuid4(), NOW, NOW,
    )
    basis = ChecklistQualificationReview(
        review_id, round_id, project, subject, version, 1,
        fingerprint, NOW, subject_type, policy,
    )
    return fixed, basis


def _base():
    project, req, req_version, criterion = (uuid.uuid4() for _ in range(4))
    fingerprint = b"r" * 32
    snapshot = RequirementVersionValidationSnapshot(
        req_version, req, project, 1, "APPROVED", None,
        "Observable requirement", "Rationale", "PLM", "HIGH", "MEDIUM",
        "STANDARD_FUNCTION", fingerprint, 0, 1, 0, 0, 0, 0, 0,
        (), (RequirementAcceptanceDraft("Result", "Method", "Data",
                                        "Environment", "Evidence"),),
        (), (), (), (), (), True,
    )
    fixed, review = _review(project, req, req_version, fingerprint,
                            "REQ-03", "REQUIREMENT_ALL_V1")
    approved = RequirementWorkflowApprovedLock(
        snapshot, req_version, review.review_id, review.review_round_id,
    )
    lock = RequirementWorkflowScopeLock(project, 1, (approved,), ())
    evidence = ChecklistQualificationEvidence(
        uuid.uuid4(), project, 1, b"e" * 32, NOW,
    )
    subject = ChecklistQualificationSubject(
        "REQ-03", req, req_version, fingerprint, (evidence,), review,
    )
    qualified = AggregateChecklistQualification(
        project, "REQUIREMENT", "REQUIREMENT_ACCEPTANCE",
        (subject,), (), b"s" * 32, b"q" * 32,
    )
    acceptance = RequirementAcceptanceRefsProof(
        project, req, req_version, (criterion,),
    )
    return project, req, req_version, criterion, lock, qualified, acceptance


def _owner(base, roots, versions, *, current=None, integrity=None,
           audit=None, review=None, acceptance=None):
    project, _req, _version, _criterion, lock, qualified, refs = base
    return PrototypeWorkflowQualificationOwner(
        requirement_owner=_RequirementOwner(lock, qualified),
        acceptance_refs=_Acceptance(refs if acceptance is None else acceptance),
        roots=_Roots(roots), versions=_Versions(versions),
        current=_Current(current), artifact_integrity=_Integrity(integrity),
        decision_audit=_Audit(audit), reviews=_Reviews(review), clock=lambda: NOW,
    )


def _query(project, item):
    return CurrentChecklistQualificationQuery(
        b"s" * 32, uuid.uuid4(), project, item,
    )


def test_all_not_required_needs_user_action_and_requirement_evidence():
    base = _base()
    project, _req, req_version, *_ = base
    prototype, decision_id, actor = (uuid.uuid4() for _ in range(3))
    decision = PrototypeDecisionLock(
        decision_id, (req_version,), actor, "Not required", "No impact",
        None, None, b"d" * 32, NOW,
    )
    root = PrototypeRootLock(project, prototype, "NOT_REQUIRED", None, 1, decision)
    audit = PrototypeScopeDecisionAuditProof(
        uuid.uuid4(), project, prototype, actor, NOW + timedelta(seconds=1),
    )
    versions = PrototypeWorkflowVersionLinksLock((), ())
    owner = _owner(base, (root,), versions, audit=audit)
    for item in ("PROTOTYPE_SCOPE_DECISIONS", "PROTOTYPE_COVERAGE"):
        result = owner.qualify_only_current_in_transaction(
            object(), _query(project, item),
        )
        assert result.stage_key == "PROTOTYPE"
        assert len(result.subjects) == 1
        assert result.subjects[0].subject_type == "REQ-03"
        assert result.evidence_refs
    with pytest.raises(ChecklistQualificationError):
        _owner(base, (root,), versions).qualify_only_current_in_transaction(
            object(), _query(project, "PROTOTYPE_COVERAGE"),
        )
    with pytest.raises(ChecklistQualificationError):
        _owner(base, (root,), versions, audit=audit,
               acceptance=False).qualify_only_current_in_transaction(
                   object(), _query(project, "PROTOTYPE_COVERAGE"),
               )
    wrong_project = PrototypeRootLock(
        uuid.uuid4(), prototype, "NOT_REQUIRED", None, 1, decision,
    )
    with pytest.raises(ChecklistQualificationError):
        _owner(base, (wrong_project,), versions,
               audit=audit).qualify_only_current_in_transaction(
                   object(), _query(project, "PROTOTYPE_COVERAGE"),
               )


def test_approved_prototype_requires_real_artifact_review_and_coverage():
    base = _base()
    project, req, req_version, criterion, *_ = base
    prototype, version_id, document_id, document_version = (
        uuid.uuid4() for _ in range(4))
    template, template_version = uuid.uuid4(), uuid.uuid4()
    fingerprint = b"p" * 32
    snapshot = PrototypeVersionInitialView(
        version_id, prototype, project, 1, None, template, template_version,
        (VersionArtifactRef("DOCUMENT_VERSION", document_version),),
        (VersionRequirementRef(req, req_version),), {}, {},
        fingerprint.hex(), NOW, "APPROVED", 0,
    )
    fixed, _review_basis = _review(
        project, prototype, version_id, fingerprint, "PRT-03",
        "PROTOTYPE_ALL_V1",
    )
    lock = PrototypeWorkflowVersionLock(
        snapshot, fixed.review.review_id, fixed.progress.round_id,
        uuid.uuid4(), uuid.uuid4(),
    )
    root = PrototypeRootLock(project, prototype, "ACTIVE", version_id, 3, None)
    digest = "a" * 64
    document = PrototypeVersionDocumentArtifactProof(
        document_version, document_id, "PROJECT", project,
        digest, 10, "application/pdf",
    )
    facts = PrototypeVersionCurrentFacts(
        PrototypeVersionTemplateProof(template, template_version,
                                      "PROJECT", project, 1, "b" * 64),
        (document,),
        (PrototypeApprovedRequirementVersionProof(
            project, req, req_version, 1, "c" * 64,
            uuid.uuid4(), uuid.uuid4()),),
    )
    physical = PrototypeWorkflowArtifactIntegrityProof(
        document_version, digest, 10,
    )
    link = RequirementPrototypeLinkView(
        uuid.uuid4(), project, req, req_version, prototype, version_id,
        "VALIDATES", RequirementPrototypeCoverage((criterion,), ()),
        "ACTIVE", 0, uuid.uuid4(), NOW, None,
    )
    versions = PrototypeWorkflowVersionLinksLock((lock,), (link,))
    owner = _owner(base, (root,), versions, current=facts,
                   integrity=physical, review=fixed)
    result = owner.qualify_only_current_in_transaction(
        object(), _query(project, "PROTOTYPE_COVERAGE"),
    )
    assert tuple(value.subject_type for value in result.subjects) == (
        "PRT-03", "REQ-03",
    )
    assert result.subjects[0].evidence == ()
    assert len(result.evidence_refs) == 1
    with pytest.raises(ChecklistQualificationError):
        _owner(base, (root,), versions, current=facts,
               review=fixed).qualify_only_current_in_transaction(
                   object(), _query(project, "PROTOTYPE_COVERAGE"),
               )
    with pytest.raises(ChecklistQualificationError):
        _owner(base, (root,), PrototypeWorkflowVersionLinksLock((lock,), ()),
               current=facts, integrity=physical,
               review=fixed).qualify_only_current_in_transaction(
                   object(), _query(project, "PROTOTYPE_COVERAGE"),
               )
    scope_only = _owner(
        base, (root,), PrototypeWorkflowVersionLinksLock((lock,), ()),
        current=facts, integrity=physical, review=fixed,
    ).qualify_only_current_in_transaction(
        object(), _query(project, "PROTOTYPE_SCOPE_DECISIONS"),
    )
    assert scope_only.item_key == "PROTOTYPE_SCOPE_DECISIONS"
