"""Handover-owned current-fact proof for Workflow qualification."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.ai.application.task_read import AITaskView
from plm_assistant.modules.capability.application.read_capability import (
    CapabilityItemView, CapabilityVersionView,
)
from plm_assistant.modules.document.application.prove_fixed_source import (
    VerifiedFixedSource,
)
from plm_assistant.modules.document.application.read_documents import (
    DocumentReadQuery,
)
from plm_assistant.modules.evidence.application.fixed_project_source import (
    EvidenceFixedProjectQuery, VerifiedProjectEvidence,
)
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.review.application.read_snapshot import (
    FixedReviewRoundSnapshot, ReviewIdentitySnapshot,
)
from plm_assistant.modules.review.domain.round_progress import ReviewRoundState
from plm_assistant.modules.trace.application.resolution_proof import (
    TraceResolutionProof,
)

from .source_validation import (
    HandoverDocumentRef, HandoverSourceValidator,
)
from .create_version import HandoverVersionCreateService
from .validate_version import (
    HandoverVersionSnapshot, HandoverVersionValidationService,
)
from .workflow_qualification import (
    HandoverChecklistQualification, HandoverWorkflowActionFact,
    HandoverWorkflowEvidenceObservation, HandoverWorkflowItemFact,
    HandoverWorkflowQualificationPolicy, HandoverWorkflowQualificationSnapshot,
    HandoverWorkflowReviewObservation,
)


_ITEM_STATES = frozenset({
    "CANDIDATE", "CONFIRMED", "RESOLVED", "ACCEPTED_RISK", "REJECTED",
    "SUPERSEDED",
})
_ACTION_STATES = frozenset({
    "OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED", "CLOSED", "CANCELLED",
})


class HandoverWorkflowQualificationOwnerError(RuntimeError):
    """Safe failure without disclosing which protected fact drifted."""

    def __init__(self) -> None:
        super().__init__("HANDOVER_WORKFLOW_NOT_QUALIFIED")


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ids(values: object, *, required: bool = False) -> bool:
    return (type(values) is tuple and (not required or bool(values))
            and all(_id(value) for value in values)
            and len(set(values)) == len(values))


@dataclass(frozen=True, slots=True)
class HandoverWorkflowQualificationQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    item_key: str

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes
                or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id,
                    self.handover_analysis_id,
                ))
                or type(self.item_key) is not str
                or self.item_key not in {
                    "HANDOVER_BASELINE", "HANDOVER_ISSUES",
                }):
            raise HandoverWorkflowQualificationOwnerError()


@dataclass(frozen=True, slots=True)
class HandoverWorkflowCurrentQualificationQuery:
    """Select the sole current approved Analysis without expanding API V1."""

    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    item_key: str

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes
                or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id,
                ))
                or type(self.item_key) is not str
                or self.item_key not in {
                    "HANDOVER_BASELINE", "HANDOVER_ISSUES",
                }):
            raise HandoverWorkflowQualificationOwnerError()


@dataclass(frozen=True, slots=True)
class HandoverWorkflowActionLock:
    action_item_id: uuid.UUID
    project_id: uuid.UUID
    source_analysis_version_ref: uuid.UUID
    source_item_id: uuid.UUID
    action_state: str
    lock_version: int
    response_documents: tuple[HandoverDocumentRef, ...]
    submission_evidence_refs: tuple[uuid.UUID, ...]
    verification_evidence_refs: tuple[uuid.UUID, ...]
    resolution_trace_ref: uuid.UUID | None

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.action_item_id, self.project_id,
                    self.source_analysis_version_ref, self.source_item_id,
                ))
                or self.action_state not in _ACTION_STATES
                or type(self.lock_version) is not int
                or not 0 <= self.lock_version < 2**63
                or type(self.response_documents) is not tuple
                or any(type(value) is not HandoverDocumentRef
                       for value in self.response_documents)
                or len({value.document_id for value in self.response_documents})
                   != len(self.response_documents)
                or len({value.document_version_id
                        for value in self.response_documents})
                   != len(self.response_documents)
                or not _ids(self.submission_evidence_refs)
                or not _ids(self.verification_evidence_refs)
                or self.resolution_trace_ref is not None
                   and not _id(self.resolution_trace_ref)):
            raise HandoverWorkflowQualificationOwnerError()
        for value in self.response_documents:
            value.__post_init__()


@dataclass(frozen=True, slots=True)
class HandoverWorkflowQualificationLock:
    snapshot: HandoverVersionSnapshot
    analysis_state: str
    analysis_lock_version: int
    current_approved_version_ref: uuid.UUID
    review_ref: uuid.UUID
    review_round_ref: uuid.UUID
    item_states: tuple[tuple[uuid.UUID, str], ...]
    actions: tuple[HandoverWorkflowActionLock, ...]

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not HandoverVersionSnapshot
                or self.analysis_state not in (
                    "ACTIVE", "ARCHIVED", "RESTRICTED",
                )
                or type(self.analysis_lock_version) is not int
                or not 0 <= self.analysis_lock_version < 2**63
                or not all(_id(value) for value in (
                    self.current_approved_version_ref, self.review_ref,
                    self.review_round_ref,
                ))
                or type(self.item_states) is not tuple
                or any(not _id(item_id) or state not in _ITEM_STATES
                       for item_id, state in self.item_states)
                or tuple(item.analysis_item_id for item in self.snapshot.items)
                   != tuple(item_id for item_id, _ in self.item_states)
                or type(self.actions) is not tuple
                or any(type(value) is not HandoverWorkflowActionLock
                       for value in self.actions)
                or len({value.action_item_id for value in self.actions})
                   != len(self.actions)):
            raise HandoverWorkflowQualificationOwnerError()
        item_ids = {item_id for item_id, _ in self.item_states}
        for value in self.actions:
            value.__post_init__()
            if (value.project_id != self.snapshot.project_id
                    or value.source_analysis_version_ref
                       != self.snapshot.handover_analysis_version_id
                    or value.source_item_id not in item_ids):
                raise HandoverWorkflowQualificationOwnerError()


class HandoverWorkflowQualificationRepositoryPort(Protocol):
    def only_current_analysis_id(
        self, transaction: object, *, project_id: uuid.UUID,
    ) -> uuid.UUID | None: ...

    def lock_current(
        self, transaction: object, *, project_id: uuid.UUID,
        handover_analysis_id: uuid.UUID,
    ) -> HandoverWorkflowQualificationLock | None: ...


class HandoverWorkflowDocumentProofPort(Protocol):
    def prove(
        self, transaction: object, query: DocumentReadQuery, *,
        document_id: uuid.UUID, document_version_id: uuid.UUID,
        parse_record_id: uuid.UUID | None = None,
    ) -> VerifiedFixedSource: ...


class HandoverWorkflowEvidenceProofPort(Protocol):
    def prove(
        self, transaction: object, query: EvidenceFixedProjectQuery,
        evidence_id: uuid.UUID,
    ) -> VerifiedProjectEvidence: ...


class HandoverWorkflowCapabilityPort(Protocol):
    def get_version(self, transaction: object, *, visibility: str,
                    baseline_id: uuid.UUID,
                    baseline_version_id: uuid.UUID) -> object | None: ...

    def list_items(self, transaction: object, *, visibility: str,
                   baseline_id: uuid.UUID,
                   baseline_version_id: uuid.UUID,
                   after_ordinal: int | None,
                   limit: int) -> tuple[object, ...]: ...


class HandoverWorkflowAITaskPort(Protocol):
    def get(self, transaction: object, *, ai_task_id: uuid.UUID,
            project_id: uuid.UUID) -> object | None: ...


class HandoverWorkflowReviewPort(Protocol):
    def get_review(self, transaction: object, scope: str,
                   project_id: uuid.UUID | None,
                   review_id: uuid.UUID) -> object | None: ...

    def get_round(self, transaction: object, scope: str,
                  project_id: uuid.UUID | None, review_id: uuid.UUID,
                  round_id: uuid.UUID) -> object | None: ...


class HandoverWorkflowTraceProofPort(Protocol):
    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, project_id: uuid.UUID,
              trace_link_id: uuid.UUID, source_kind: str,
              source_analysis_id: uuid.UUID | None,
              source_analysis_version_id: uuid.UUID | None,
              reason: str) -> TraceResolutionProof: ...


class HandoverWorkflowQualificationOwner:
    """Reprove current Handover facts without committing or writing Workflow."""

    def __init__(
        self, *, repository: HandoverWorkflowQualificationRepositoryPort,
        sources: HandoverSourceValidator,
        documents: HandoverWorkflowDocumentProofPort,
        evidence: HandoverWorkflowEvidenceProofPort,
        capabilities: HandoverWorkflowCapabilityPort,
        ai_tasks: HandoverWorkflowAITaskPort,
        reviews: HandoverWorkflowReviewPort,
        trace_proofs: HandoverWorkflowTraceProofPort,
        policy: HandoverWorkflowQualificationPolicy | None = None,
        clock=None,
    ) -> None:
        if any(value is None for value in (
                repository, sources, documents, evidence, capabilities,
                ai_tasks, reviews, trace_proofs)):
            raise ValueError("Handover Workflow qualification dependencies required")
        self._repo, self._sources = repository, sources
        self._documents, self._evidence = documents, evidence
        self._capabilities, self._ai_tasks = capabilities, ai_tasks
        self._reviews, self._traces = reviews, trace_proofs
        self._policy = policy or HandoverWorkflowQualificationPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: HandoverWorkflowCurrentQualificationQuery,
    ) -> HandoverChecklistQualification:
        if (transaction is None
                or type(query) is not HandoverWorkflowCurrentQualificationQuery):
            raise HandoverWorkflowQualificationOwnerError()
        query.__post_init__()
        try:
            analysis_id = self._repo.only_current_analysis_id(
                transaction, project_id=query.project_id,
            )
            if not _id(analysis_id):
                raise HandoverWorkflowQualificationOwnerError()
            return self.qualify_in_transaction(
                transaction,
                HandoverWorkflowQualificationQuery(
                    query.session_token, query.trace_id, query.project_id,
                    analysis_id, query.item_key,
                ),
            )
        except HandoverWorkflowQualificationOwnerError:
            raise
        except Exception:
            raise HandoverWorkflowQualificationOwnerError() from None

    def qualify_in_transaction(
        self, transaction: object, query: HandoverWorkflowQualificationQuery,
    ) -> HandoverChecklistQualification:
        if transaction is None or type(query) is not HandoverWorkflowQualificationQuery:
            raise HandoverWorkflowQualificationOwnerError()
        query.__post_init__()
        try:
            locked = self._repo.lock_current(
                transaction, project_id=query.project_id,
                handover_analysis_id=query.handover_analysis_id,
            )
            if type(locked) is not HandoverWorkflowQualificationLock:
                raise HandoverWorkflowQualificationOwnerError()
            locked.__post_init__()
            snapshot = locked.snapshot
            if (snapshot.project_id != query.project_id
                    or snapshot.handover_analysis_id
                       != query.handover_analysis_id
                    or locked.analysis_state != "ACTIVE"
                    or snapshot.version_state != "APPROVED"
                    or locked.current_approved_version_ref
                       != snapshot.handover_analysis_version_id
                    or any(state != "CONFIRMED"
                           for _, state in locked.item_states)):
                raise HandoverWorkflowQualificationOwnerError()
            payload = HandoverVersionValidationService._snapshot_payload(snapshot)
            if not hmac.compare_digest(
                    canonical_payload_fingerprint(payload),
                    snapshot.content_fingerprint):
                raise HandoverWorkflowQualificationOwnerError()
            stable: set[uuid.UUID] = set()
            for item in snapshot.items:
                HandoverVersionCreateService._validate_item(item, stable)
                stable.add(item.analysis_item_id)
            now = self._now()
            source_pairs = self._prove_sources(
                transaction, query, snapshot,
            )
            self._prove_capability(transaction, snapshot)
            self._prove_ai_tasks(transaction, snapshot)
            review = self._prove_review(transaction, locked, now)
            observations = self._prove_evidence(
                transaction, query, locked, source_pairs, now,
            )
            items = self._item_facts(transaction, query, locked)
            qualification = HandoverWorkflowQualificationSnapshot(
                snapshot.project_id, snapshot.handover_analysis_id,
                snapshot.handover_analysis_version_id,
                locked.current_approved_version_ref, locked.analysis_state,
                snapshot.version_state, snapshot.content_fingerprint,
                tuple(dict.fromkeys(
                    evidence_id for item in snapshot.items
                    for evidence_id in item.evidence_refs
                )), observations, review, items,
            )
            return self._policy.qualify(qualification, query.item_key)
        except HandoverWorkflowQualificationOwnerError:
            raise
        except Exception:
            raise HandoverWorkflowQualificationOwnerError() from None

    def _prove_sources(self, tx, query, snapshot):
        validated = self._sources.validate(
            tx, project_id=query.project_id,
            references=snapshot.source_documents,
        )
        if (validated.source_set_ref != snapshot.source_set_ref
                or validated.documents != tuple(sorted(
                    snapshot.source_documents,
                    key=lambda value: str(value.document_version_id),
                ))):
            raise HandoverWorkflowQualificationOwnerError()
        document_query = DocumentReadQuery(
            query.session_token, query.trace_id, "PROJECT", query.project_id,
        )
        pairs = frozenset(
            (value.document_id, value.document_version_id)
            for value in snapshot.source_documents
        )
        for document_id, version_id in sorted(pairs, key=lambda value: str(value[1])):
            self._prove_document(tx, document_query, document_id, version_id)
        return pairs

    def _prove_document(self, tx, query, document_id, version_id):
        result = self._documents.prove(
            tx, query, document_id=document_id,
            document_version_id=version_id,
        )
        if (type(result) is not VerifiedFixedSource
                or result.parse_record_id is not None
                or result.facts.document_id != document_id
                or result.facts.document_version_id != version_id
                or result.facts.scope != "PROJECT"
                or result.facts.project_id != query.project_id
                or result.facts.document_state != "ACTIVE"
                or result.facts.document_category == "TEMPLATE"):
            raise HandoverWorkflowQualificationOwnerError()

    def _prove_capability(self, tx, snapshot):
        version = self._capabilities.get_version(
            tx, visibility="CURRENT_APPROVED",
            baseline_id=snapshot.capability_baseline_id,
            baseline_version_id=snapshot.capability_baseline_version_ref,
        )
        items = self._capabilities.list_items(
            tx, visibility="CURRENT_APPROVED",
            baseline_id=snapshot.capability_baseline_id,
            baseline_version_id=snapshot.capability_baseline_version_ref,
            after_ordinal=None, limit=501,
        )
        allowed = {
            item.capability_item_id for item in items
            if type(item) is CapabilityItemView and item.state == "AVAILABLE"
        }
        if (type(version) is not CapabilityVersionView
                or version.baseline_id != snapshot.capability_baseline_id
                or version.baseline_version_id
                   != snapshot.capability_baseline_version_ref
                or version.state != "APPROVED"
                or len(items) != version.declared_item_count
                or len(items) > 500
                or any(type(item) is not CapabilityItemView for item in items)
                or any(ref.capability_item_id not in allowed
                       for item in snapshot.items
                       for ref in item.capability_refs)):
            raise HandoverWorkflowQualificationOwnerError()

    def _prove_ai_tasks(self, tx, snapshot):
        for task_id in snapshot.ai_task_refs:
            task = self._ai_tasks.get(
                tx, ai_task_id=task_id, project_id=snapshot.project_id,
            )
            if (type(task) is not AITaskView
                    or task.ai_task_id != task_id
                    or task.project_id != snapshot.project_id
                    or task.task_type != "GAP_ANALYSIS"
                    or task.task_state != "SUCCEEDED"):
                raise HandoverWorkflowQualificationOwnerError()

    def _prove_review(self, tx, locked, now):
        snapshot = locked.snapshot
        identity = self._reviews.get_review(
            tx, "PROJECT", snapshot.project_id, locked.review_ref,
        )
        fixed = self._reviews.get_round(
            tx, "PROJECT", snapshot.project_id, locked.review_ref,
            locked.review_round_ref,
        )
        if (type(identity) is not ReviewIdentitySnapshot
                or type(fixed) is not FixedReviewRoundSnapshot):
            raise HandoverWorkflowQualificationOwnerError()
        identity.__post_init__()
        fixed.__post_init__()
        if (identity.review_id != locked.review_ref
                or identity.scope != "PROJECT"
                or identity.project_id != snapshot.project_id
                or identity.subject_type != "HND-02"
                or identity.subject_id != snapshot.handover_analysis_id
                or identity.policy_code != "HANDOVER_ALL_V1"
                or identity.state != "APPROVED"
                or identity.active_round_id is not None
                or fixed.review != identity
                or fixed.progress.round_id != locked.review_round_ref
                or fixed.progress.state is not ReviewRoundState.APPROVED
                or fixed.subject_version_id
                   != snapshot.handover_analysis_version_id
                or not hmac.compare_digest(
                    fixed.subject_fingerprint, snapshot.content_fingerprint,
                )):
            raise HandoverWorkflowQualificationOwnerError()
        return HandoverWorkflowReviewObservation(
            identity.review_id, fixed.progress.round_id,
            snapshot.project_id, snapshot.handover_analysis_id,
            snapshot.handover_analysis_version_id,
            fixed.round_lock_version, fixed.subject_fingerprint, now,
        )

    def _prove_evidence(self, tx, query, locked, source_pairs, now):
        constraints: dict[uuid.UUID, list[frozenset[tuple[uuid.UUID, uuid.UUID]]]] = {}
        for item in locked.snapshot.items:
            for evidence_id in item.evidence_refs:
                constraints.setdefault(evidence_id, []).append(source_pairs)
        document_query = DocumentReadQuery(
            query.session_token, query.trace_id, "PROJECT", query.project_id,
        )
        for action in locked.actions:
            if action.action_state not in {"VERIFIED", "CLOSED"}:
                continue
            self._sources.validate(
                tx, project_id=query.project_id,
                references=action.response_documents,
            )
            pairs = frozenset(
                (value.document_id, value.document_version_id)
                for value in action.response_documents
            )
            for document_id, version_id in sorted(
                    pairs, key=lambda value: str(value[1])):
                self._prove_document(
                    tx, document_query, document_id, version_id,
                )
            for evidence_id in (
                    action.submission_evidence_refs
                    + action.verification_evidence_refs):
                constraints.setdefault(evidence_id, []).append(pairs)
        evidence_query = EvidenceFixedProjectQuery(
            query.session_token, query.trace_id, query.project_id,
        )
        observations: list[HandoverWorkflowEvidenceObservation] = []
        for evidence_id in sorted(constraints, key=str):
            result = self._evidence.prove(tx, evidence_query, evidence_id)
            if type(result) is not VerifiedProjectEvidence:
                raise HandoverWorkflowQualificationOwnerError()
            pair = (result.document_id, result.document_version_id)
            if (result.evidence_id != evidence_id
                    or result.project_id != query.project_id
                    or result.scope != "PROJECT"
                    or result.observed_state != "ELIGIBLE"
                    or any(pair not in allowed
                           for allowed in constraints[evidence_id])):
                raise HandoverWorkflowQualificationOwnerError()
            observations.append(HandoverWorkflowEvidenceObservation(
                evidence_id, query.project_id,
                result.observed_lock_version,
                result.content_fingerprint, now,
            ))
        return tuple(observations)

    def _item_facts(self, tx, query, locked):
        actions: dict[uuid.UUID, list[HandoverWorkflowActionFact]] = {
            item.analysis_item_id: [] for item in locked.snapshot.items
        }
        blocking_ids = {
            item.analysis_item_id for item in locked.snapshot.items
            if (item.source_missing
                or item.item_type in {"NEED_CONFIRM", "CONFLICT", "RISK"})
        }
        for action in locked.actions:
            if (action.action_state == "CLOSED"
                    and action.source_item_id in blocking_ids):
                proof = self._traces.prove(
                    tx, session_token=query.session_token,
                    trace_id=query.trace_id, project_id=query.project_id,
                    trace_link_id=action.resolution_trace_ref,
                    source_kind="ANALYSIS_ITEM",
                    source_analysis_id=locked.snapshot.handover_analysis_id,
                    source_analysis_version_id=(
                        locked.snapshot.handover_analysis_version_id
                    ),
                    reason="Handover Workflow qualification current-fact proof",
                )
                if (type(proof) is not TraceResolutionProof
                        or proof.trace_link_id
                           != action.resolution_trace_ref):
                    raise HandoverWorkflowQualificationOwnerError()
            actions[action.source_item_id].append(HandoverWorkflowActionFact(
                action.action_item_id, action.action_state,
                tuple(value.document_version_id
                      for value in action.response_documents),
                action.submission_evidence_refs,
                action.verification_evidence_refs,
                action.resolution_trace_ref,
            ))
        return tuple(HandoverWorkflowItemFact(
            item.analysis_item_id, item.item_type, item.source_missing,
            tuple(actions[item.analysis_item_id]),
        ) for item in locked.snapshot.items)

    def _now(self) -> datetime:
        now = self._clock()
        if (type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            raise HandoverWorkflowQualificationOwnerError()
        return now.astimezone(timezone.utc)
