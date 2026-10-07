"""Business-neutral current Checklist qualification contract and registry."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Protocol

from ..domain.catalog_v1 import six_stage_definition


class ChecklistQualificationError(RuntimeError):
    """Fail closed without disclosing which protected owner fact failed."""

    def __init__(self) -> None:
        super().__init__("WORKFLOW_GATE_NOT_SATISFIED")


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _version(value: object) -> bool:
    return type(value) is int and 0 <= value < 2**63


def _utc(value: object) -> bool:
    return (type(value) is datetime and value.tzinfo is not None
            and value.utcoffset() == timedelta(0))


def _token(value: object, *, limit: int) -> bool:
    return (type(value) is str and 0 < len(value) <= limit
            and value.strip() == value and "\x00" not in value)


_DEFINITION = six_stage_definition(1)
_ITEM_STAGES = {
    item.item_key: stage.stage_key
    for stage in _DEFINITION.stages
    for item in stage.checklist_items
}


@dataclass(frozen=True, slots=True)
class CurrentChecklistQualificationQuery:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    item_key: str

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes
                or len(self.session_token) != 32
                or not _id(self.trace_id) or not _id(self.project_id)
                or type(self.item_key) is not str
                or self.item_key not in _ITEM_STAGES):
            raise ChecklistQualificationError()


@dataclass(frozen=True, slots=True)
class ChecklistQualificationEvidence:
    evidence_id: uuid.UUID
    project_id: uuid.UUID
    observed_lock_version: int
    content_fingerprint: bytes
    verified_at: datetime

    def __post_init__(self) -> None:
        if (not _id(self.evidence_id) or not _id(self.project_id)
                or not _version(self.observed_lock_version)
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or not _utc(self.verified_at)):
            raise ChecklistQualificationError()


@dataclass(frozen=True, slots=True)
class ChecklistQualificationReview:
    review_id: uuid.UUID
    review_round_id: uuid.UUID
    project_id: uuid.UUID
    subject_id: uuid.UUID
    subject_version_id: uuid.UUID
    observed_lock_version: int
    subject_fingerprint: bytes
    verified_at: datetime
    subject_type: str
    policy_code: str
    observed_state: str = "APPROVED"

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                    self.review_id, self.review_round_id, self.project_id,
                    self.subject_id, self.subject_version_id))
                or not _version(self.observed_lock_version)
                or type(self.subject_fingerprint) is not bytes
                or len(self.subject_fingerprint) != 32
                or not _utc(self.verified_at)
                or not _token(self.subject_type, limit=64)
                or not _token(self.policy_code, limit=128)
                or self.observed_state != "APPROVED"):
            raise ChecklistQualificationError()


@dataclass(frozen=True, slots=True)
class CurrentChecklistQualification:
    project_id: uuid.UUID
    stage_key: str
    item_key: str
    subject_type: str
    subject_id: uuid.UUID
    subject_version_id: uuid.UUID
    content_fingerprint: bytes
    evidence: tuple[ChecklistQualificationEvidence, ...]
    review: ChecklistQualificationReview

    def __post_init__(self) -> None:
        if (not _id(self.project_id)
                or self.item_key not in _ITEM_STAGES
                or self.stage_key != _ITEM_STAGES.get(self.item_key)
                or not _token(self.subject_type, limit=64)
                or not _id(self.subject_id)
                or not _id(self.subject_version_id)
                or type(self.content_fingerprint) is not bytes
                or len(self.content_fingerprint) != 32
                or type(self.evidence) is not tuple or not self.evidence
                or any(type(value) is not ChecklistQualificationEvidence
                       for value in self.evidence)
                or len({value.evidence_id for value in self.evidence})
                   != len(self.evidence)
                or type(self.review) is not ChecklistQualificationReview):
            raise ChecklistQualificationError()
        self.review.__post_init__()
        for value in self.evidence:
            value.__post_init__()
        if (self.review.project_id != self.project_id
                or self.review.subject_id != self.subject_id
                or self.review.subject_version_id != self.subject_version_id
                or self.review.subject_type != self.subject_type
                or any(value.project_id != self.project_id
                       for value in self.evidence)):
            raise ChecklistQualificationError()

    @property
    def coherence_key(self) -> tuple[str, uuid.UUID, uuid.UUID, uuid.UUID]:
        return (
            self.subject_type, self.subject_id, self.subject_version_id,
            self.review.review_round_id,
        )


class ChecklistQualificationOwnerPort(Protocol):
    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> CurrentChecklistQualification: ...


@dataclass(frozen=True, slots=True)
class ChecklistQualificationRegistration:
    item_keys: tuple[str, ...]
    owner: ChecklistQualificationOwnerPort

    def __post_init__(self) -> None:
        if (type(self.item_keys) is not tuple or not self.item_keys
                or len(set(self.item_keys)) != len(self.item_keys)
                or any(type(value) is not str or value not in _ITEM_STAGES
                       for value in self.item_keys)
                or self.owner is None
                or not callable(getattr(
                    self.owner, "qualify_only_current_in_transaction", None,
                ))):
            raise ChecklistQualificationError()


class ChecklistQualificationRegistry:
    """Explicit immutable allowlist; never discovers business owners dynamically."""

    def __init__(
        self, registrations: tuple[ChecklistQualificationRegistration, ...],
    ) -> None:
        if type(registrations) is not tuple or not registrations:
            raise ChecklistQualificationError()
        owners: dict[str, ChecklistQualificationOwnerPort] = {}
        for registration in registrations:
            if type(registration) is not ChecklistQualificationRegistration:
                raise ChecklistQualificationError()
            registration.__post_init__()
            for item_key in registration.item_keys:
                if item_key in owners:
                    raise ChecklistQualificationError()
                owners[item_key] = registration.owner
        self._owners = MappingProxyType(owners)

    @property
    def item_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self._owners))

    def qualify_only_current_in_transaction(
        self, transaction: object,
        query: CurrentChecklistQualificationQuery,
    ) -> CurrentChecklistQualification:
        if transaction is None or type(query) is not CurrentChecklistQualificationQuery:
            raise ChecklistQualificationError()
        query.__post_init__()
        owner = self._owners.get(query.item_key)
        if owner is None:
            raise ChecklistQualificationError()
        try:
            result = owner.qualify_only_current_in_transaction(
                transaction, query,
            )
            if type(result) is not CurrentChecklistQualification:
                raise ChecklistQualificationError()
            result.__post_init__()
            if (result.project_id != query.project_id
                    or result.item_key != query.item_key
                    or result.stage_key != _ITEM_STAGES[query.item_key]):
                raise ChecklistQualificationError()
            return result
        except ChecklistQualificationError:
            raise
        except Exception:
            raise ChecklistQualificationError() from None
