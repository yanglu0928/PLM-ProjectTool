"""Pure Handover policy for the two fixed Workflow checklist items.

The current-fact Owner is responsible for constructing this input only after
locking and reproving its external facts.  This module neither queries another
module nor writes a Workflow record.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta


_ITEM_KEYS = frozenset({"HANDOVER_BASELINE", "HANDOVER_ISSUES"})
_ITEM_TYPES = frozenset({
    "GAP", "MISSING", "CONFLICT", "RISK", "SCOPE", "NEED_CONFIRM",
})
_ACTION_STATES = frozenset({
    "OPEN", "IN_PROGRESS", "SUBMITTED", "VERIFIED", "CLOSED", "CANCELLED",
})
_BLOCKING_TYPES = frozenset({"NEED_CONFIRM", "CONFLICT", "RISK"})
_QUALIFIED_ACTION_STATES = frozenset({"VERIFIED", "CLOSED"})


class HandoverWorkflowQualificationError(RuntimeError):
    """Fail closed without disclosing which protected fact was unavailable."""

    def __init__(self) -> None:
        super().__init__("HANDOVER_WORKFLOW_NOT_QUALIFIED")


def _identity(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _version(value: object) -> bool:
    return type(value) is int and 0 <= value < 2**63


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _identities(values: object, *, required: bool) -> bool:
    return (type(values) is tuple
            and (not required or bool(values))
            and all(_identity(value) for value in values)
            and len(set(values)) == len(values))


@dataclass(frozen=True, slots=True)
class HandoverWorkflowEvidenceObservation:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    observed_lock_version: int
    content_fingerprint: bytes
    verified_at: datetime

    def __post_init__(self) -> None:
        if (not _identity(self.evidence_id) or not _identity(self.project_id)
                or not _version(self.observed_lock_version)
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or not _utc(self.verified_at)):
            raise HandoverWorkflowQualificationError()


@dataclass(frozen=True, slots=True)
class HandoverWorkflowReviewObservation:
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    project_id: uuid.UUID
    subject_id: uuid.UUID
    subject_version_id: uuid.UUID
    observed_lock_version: int
    subject_fingerprint: bytes
    verified_at: datetime
    subject_type: str = "HND-02"
    policy_code: str = "HANDOVER_ALL_V1"
    observed_state: str = "APPROVED"

    def __post_init__(self) -> None:
        if (not all(_identity(value) for value in (
                    self.review_id, self.review_round_id, self.project_id,
                    self.subject_id, self.subject_version_id))
                or not _version(self.observed_lock_version)
                or type(self.subject_fingerprint) is not bytes
                or len(self.subject_fingerprint) != 32
                or not _utc(self.verified_at)
                or self.subject_type != "HND-02"
                or self.policy_code != "HANDOVER_ALL_V1"
                or self.observed_state != "APPROVED"):
            raise HandoverWorkflowQualificationError()


@dataclass(frozen=True, slots=True)
class HandoverWorkflowActionFact:
    action_item_id: uuid.UUID
    action_state: str
    response_document_version_refs: tuple[uuid.UUID, ...] = ()
    submission_evidence_refs: tuple[uuid.UUID, ...] = ()
    verification_evidence_refs: tuple[uuid.UUID, ...] = ()
    resolution_trace_ref: uuid.UUID | None = None

    def __post_init__(self) -> None:
        if (not _identity(self.action_item_id)
                or self.action_state not in _ACTION_STATES
                or not _identities(self.response_document_version_refs,
                                   required=False)
                or not _identities(self.submission_evidence_refs,
                                   required=False)
                or not _identities(self.verification_evidence_refs,
                                   required=False)
                or self.resolution_trace_ref is not None
                   and not _identity(self.resolution_trace_ref)):
            raise HandoverWorkflowQualificationError()
        if self.action_state in _QUALIFIED_ACTION_STATES:
            if (not self.response_document_version_refs
                    or not self.submission_evidence_refs
                    or not self.verification_evidence_refs):
                raise HandoverWorkflowQualificationError()
        if ((self.action_state == "CLOSED")
                != (self.resolution_trace_ref is not None)):
            raise HandoverWorkflowQualificationError()

    @property
    def evidence_refs(self) -> tuple[uuid.UUID, ...]:
        return tuple(dict.fromkeys(
            self.submission_evidence_refs + self.verification_evidence_refs
        ))


@dataclass(frozen=True, slots=True)
class HandoverWorkflowItemFact:
    analysis_item_id: uuid.UUID
    item_type: str
    source_missing: bool
    actions: tuple[HandoverWorkflowActionFact, ...] = ()

    def __post_init__(self) -> None:
        if (not _identity(self.analysis_item_id)
                or self.item_type not in _ITEM_TYPES
                or type(self.source_missing) is not bool
                or type(self.actions) is not tuple
                or any(type(action) is not HandoverWorkflowActionFact
                       for action in self.actions)
                or len({action.action_item_id for action in self.actions})
                   != len(self.actions)):
            raise HandoverWorkflowQualificationError()
        for action in self.actions:
            action.__post_init__()

    @property
    def blocking(self) -> bool:
        return self.source_missing or self.item_type in _BLOCKING_TYPES


@dataclass(frozen=True, slots=True)
class HandoverWorkflowQualificationSnapshot:
    project_id: uuid.UUID
    handover_analysis_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    current_approved_version_ref: uuid.UUID
    analysis_state: str
    version_state: str
    version_fingerprint: bytes
    source_evidence_refs: tuple[uuid.UUID, ...]
    evidence: tuple[HandoverWorkflowEvidenceObservation, ...]
    review: HandoverWorkflowReviewObservation
    items: tuple[HandoverWorkflowItemFact, ...]

    def __post_init__(self) -> None:
        if (not all(_identity(value) for value in (
                    self.project_id, self.handover_analysis_id,
                    self.handover_analysis_version_id,
                    self.current_approved_version_ref))
                or self.analysis_state != "ACTIVE"
                or self.version_state != "APPROVED"
                or self.current_approved_version_ref
                   != self.handover_analysis_version_id
                or type(self.version_fingerprint) is not bytes
                or len(self.version_fingerprint) != 32
                or not _identities(self.source_evidence_refs, required=False)
                or type(self.evidence) is not tuple
                or any(type(value) is not HandoverWorkflowEvidenceObservation
                       for value in self.evidence)
                or type(self.review) is not HandoverWorkflowReviewObservation
                or type(self.items) is not tuple
                or any(type(value) is not HandoverWorkflowItemFact
                       for value in self.items)
                or len({value.evidence_id for value in self.evidence})
                   != len(self.evidence)
                or len({value.analysis_item_id for value in self.items})
                   != len(self.items)):
            raise HandoverWorkflowQualificationError()
        self.review.__post_init__()
        for value in self.evidence:
            value.__post_init__()
        for value in self.items:
            value.__post_init__()
        if (self.review.project_id != self.project_id
                or self.review.subject_id != self.handover_analysis_id
                or self.review.subject_version_id
                   != self.handover_analysis_version_id
                or self.review.subject_fingerprint != self.version_fingerprint
                or any(value.project_id != self.project_id
                       for value in self.evidence)):
            raise HandoverWorkflowQualificationError()


@dataclass(frozen=True, slots=True)
class HandoverChecklistQualification:
    item_key: str
    project_id: uuid.UUID
    handover_analysis_version_id: uuid.UUID
    content_fingerprint: bytes
    evidence: tuple[HandoverWorkflowEvidenceObservation, ...]
    review: HandoverWorkflowReviewObservation

    def __post_init__(self) -> None:
        if (self.item_key not in _ITEM_KEYS
                or not _identity(self.project_id)
                or not _identity(self.handover_analysis_version_id)
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.evidence) is not tuple or not self.evidence
                or any(type(value) is not HandoverWorkflowEvidenceObservation
                       for value in self.evidence)
                or type(self.review) is not HandoverWorkflowReviewObservation):
            raise HandoverWorkflowQualificationError()
        self.review.__post_init__()
        for value in self.evidence:
            value.__post_init__()
        if (self.review.project_id != self.project_id
                or self.review.subject_version_id
                   != self.handover_analysis_version_id
                or any(value.project_id != self.project_id
                       for value in self.evidence)):
            raise HandoverWorkflowQualificationError()


class HandoverWorkflowQualificationPolicy:
    """Evaluate only frozen Handover checklist semantics, without I/O."""

    def qualify(
        self, snapshot: HandoverWorkflowQualificationSnapshot, item_key: str,
    ) -> HandoverChecklistQualification:
        if (type(snapshot) is not HandoverWorkflowQualificationSnapshot
                or item_key not in _ITEM_KEYS):
            raise HandoverWorkflowQualificationError()
        snapshot.__post_init__()
        evidence_by_id = {value.evidence_id: value
                          for value in snapshot.evidence}
        selected = list(snapshot.source_evidence_refs)
        if item_key == "HANDOVER_ISSUES":
            selected.extend(self._qualify_issues(snapshot.items))
        elif any(item.blocking for item in snapshot.items):
            selected.extend(self._qualified_action_evidence(snapshot.items))
        evidence_ids = tuple(dict.fromkeys(selected))
        if not evidence_ids or any(value not in evidence_by_id
                                   for value in evidence_ids):
            raise HandoverWorkflowQualificationError()
        evidence = tuple(evidence_by_id[value] for value in evidence_ids)
        return HandoverChecklistQualification(
            item_key, snapshot.project_id,
            snapshot.handover_analysis_version_id,
            self._fingerprint(snapshot, item_key, evidence_ids),
            evidence, snapshot.review,
        )

    @staticmethod
    def _qualify_issues(
        items: tuple[HandoverWorkflowItemFact, ...],
    ) -> tuple[uuid.UUID, ...]:
        selected: list[uuid.UUID] = []
        for item in items:
            if not item.blocking:
                continue
            active = tuple(action for action in item.actions
                           if action.action_state != "CANCELLED")
            if (not active
                    or any(action.action_state not in _QUALIFIED_ACTION_STATES
                           for action in active)):
                raise HandoverWorkflowQualificationError()
            for action in active:
                selected.extend(action.evidence_refs)
        return tuple(dict.fromkeys(selected))

    @classmethod
    def _qualified_action_evidence(
        cls, items: tuple[HandoverWorkflowItemFact, ...],
    ) -> tuple[uuid.UUID, ...]:
        selected: list[uuid.UUID] = []
        for item in items:
            if not item.blocking:
                continue
            active = tuple(action for action in item.actions
                           if action.action_state != "CANCELLED")
            for action in active:
                if action.action_state in _QUALIFIED_ACTION_STATES:
                    selected.extend(action.evidence_refs)
        return tuple(dict.fromkeys(selected))

    @staticmethod
    def _fingerprint(
        snapshot: HandoverWorkflowQualificationSnapshot, item_key: str,
        evidence_ids: tuple[uuid.UUID, ...],
    ) -> bytes:
        payload = {
            "schema": "handover-workflow-qualification.v1",
            "item_key": item_key,
            "project_id": str(snapshot.project_id),
            "analysis_id": str(snapshot.handover_analysis_id),
            "version_id": str(snapshot.handover_analysis_version_id),
            "version_fingerprint": snapshot.version_fingerprint.hex(),
            "review_id": str(snapshot.review.review_id),
            "review_round_id": str(snapshot.review.review_round_id),
            "review_lock_version": snapshot.review.observed_lock_version,
            "evidence": [{
                "evidence_id": str(value.evidence_id),
                "lock_version": value.observed_lock_version,
                "content_fingerprint": value.content_fingerprint.hex(),
            } for value in (
                next(item for item in snapshot.evidence
                     if item.evidence_id == evidence_id)
                for evidence_id in evidence_ids
            )],
            "items": [{
                "item_id": str(item.analysis_item_id),
                "type": item.item_type,
                "source_missing": item.source_missing,
                "actions": [{
                    "action_id": str(action.action_item_id),
                    "state": action.action_state,
                    "response_versions": [str(value) for value in
                                          action.response_document_version_refs],
                    "submission_evidence": [str(value) for value in
                                            action.submission_evidence_refs],
                    "verification_evidence": [str(value) for value in
                                              action.verification_evidence_refs],
                    "resolution_trace": (None if action.resolution_trace_ref is None
                                         else str(action.resolution_trace_ref)),
                } for action in item.actions],
            } for item in snapshot.items],
        }
        return hashlib.sha256(json.dumps(
            payload, ensure_ascii=True, separators=(",", ":"),
            sort_keys=True, allow_nan=False,
        ).encode("ascii")).digest()
