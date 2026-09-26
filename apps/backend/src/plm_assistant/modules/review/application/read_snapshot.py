"""Immutable historical metadata, never a Subject Owner/Gate approval proof."""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Protocol
from uuid import UUID

from ..domain.round_progress import ReviewRoundProgress, ReviewRoundState, _utc, _uuid


class ReviewSnapshotReadError(ValueError):
    def __init__(self) -> None:
        super().__init__("Review snapshot unavailable")


def valid_scope(scope: object, project_id: object) -> bool:
    return type(scope) is str and (scope == "GLOBAL" and project_id is None
                                  or scope == "PROJECT" and _uuid(project_id))


def _version(value: object) -> bool:
    return type(value) is int and 0 <= value < 2**63


@dataclass(frozen=True, slots=True)
class ReviewIdentitySnapshot:
    review_id: UUID
    scope: str
    project_id: UUID | None
    subject_type: str
    subject_id: UUID
    policy_code: str
    state: str
    active_round_id: UUID | None
    lock_version: int

    def __post_init__(self) -> None:
        if (not _uuid(self.review_id) or not _uuid(self.subject_id) or not valid_scope(self.scope, self.project_id)
                or type(self.subject_type) is not str or re.fullmatch(r"[A-Z][A-Z0-9_-]{0,63}", self.subject_type) is None
                or type(self.policy_code) is not str or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.policy_code) is None
                or type(self.state) is not str or self.state not in ("DRAFT", "IN_REVIEW", "APPROVED", "RETURNED", "WITHDRAWN")
                or not _version(self.lock_version)
                or self.state == "DRAFT" and self.lock_version != 0
                or self.state == "IN_REVIEW" and not _uuid(self.active_round_id)
                or self.state != "IN_REVIEW" and self.active_round_id is not None):
            raise ReviewSnapshotReadError()


@dataclass(frozen=True, slots=True)
class ReviewBasisObservation:
    ref_kind: str
    ref_id: UUID
    ref_scope: str
    ref_project_id: UUID | None
    observed_state: str
    observed_lock_version: int
    content_fingerprint: bytes
    verified_at: datetime

    def __post_init__(self) -> None:
        if (type(self.ref_kind) is not str or self.ref_kind not in ("EVIDENCE", "TRACE_LINK")
                or not _uuid(self.ref_id) or not valid_scope(self.ref_scope, self.ref_project_id)
                or self.observed_state != ("ELIGIBLE" if self.ref_kind == "EVIDENCE" else "ACTIVE")
                or not _version(self.observed_lock_version)
                or self.ref_kind == "TRACE_LINK" and self.observed_lock_version != 0
                or type(self.content_fingerprint) is not bytes or len(self.content_fingerprint) != 32
                or not _utc(self.verified_at)):
            raise ReviewSnapshotReadError()


@dataclass(frozen=True, slots=True)
class FixedReviewRoundSnapshot:
    review: ReviewIdentitySnapshot  # current identity, distinct from this historical round
    round_no: int
    subject_version_id: UUID
    started_by: UUID
    progress: ReviewRoundProgress
    assignment_ids: tuple[UUID, ...]  # same order as progress.reviewer_ids
    round_lock_version: int
    subject_snapshot_id: UUID
    subject_fingerprint: bytes
    proof_schema_version: int
    subject_verified_at: datetime
    basis: tuple[ReviewBasisObservation, ...]
    subject_lock_id: UUID
    lock_acquired_at: datetime
    lock_released_at: datetime | None

    def __post_init__(self) -> None:
        if type(self.review) is not ReviewIdentitySnapshot or type(self.progress) is not ReviewRoundProgress:
            raise ReviewSnapshotReadError()
        self.review.__post_init__()
        try:
            self.progress.__post_init__()
        except ValueError:
            raise ReviewSnapshotReadError() from None
        if (type(self.round_no) is not int or not 0 < self.round_no < 2**31
                or not all(_uuid(v) for v in (self.subject_version_id, self.started_by, self.subject_snapshot_id, self.subject_lock_id))
                or type(self.assignment_ids) is not tuple
                or len(self.assignment_ids) != len(self.progress.reviewer_ids)
                or not all(_uuid(v) for v in self.assignment_ids) or len(set(self.assignment_ids)) != len(self.assignment_ids)
                or not _version(self.round_lock_version)
                or self.round_lock_version != len(self.progress.decisions)+(self.progress.withdrawal is not None)
                or self.review.lock_version < self.round_no+self.round_lock_version
                or type(self.subject_fingerprint) is not bytes or len(self.subject_fingerprint) != 32
                or type(self.proof_schema_version) is not int or self.proof_schema_version != 1
                or not _utc(self.subject_verified_at) or not _utc(self.lock_acquired_at)
                or type(self.basis) is not tuple or any(type(r) is not ReviewBasisObservation for r in self.basis)):
            raise ReviewSnapshotReadError()
        active = self.progress.state is ReviewRoundState.IN_REVIEW
        if (active and (self.review.state != "IN_REVIEW" or self.review.active_round_id != self.progress.round_id or self.lock_released_at is not None)
                or not active and (self.review.active_round_id == self.progress.round_id or not _utc(self.lock_released_at))
                or self.lock_released_at is not None and self.lock_released_at < self.lock_acquired_at):
            raise ReviewSnapshotReadError()
        identities = set()
        for ref in self.basis:
            ref.__post_init__()
            key = (ref.ref_kind, ref.ref_id)
            if (key in identities or ref.ref_scope == "PROJECT" and ref.ref_project_id != self.review.project_id
                    or self.review.scope == "PROJECT" and ref.ref_scope == "GLOBAL" and ref.ref_kind != "EVIDENCE"):
                raise ReviewSnapshotReadError()
            identities.add(key)


class ReviewSnapshotReadPort(Protocol):
    """Caller authorizes Scope/Subject and License first, supplies an active transaction.

    Readers don't initialize or commit. Historical APPROVED/ELIGIBLE/ACTIVE do
    not prove current Owner facts. GLOBAL is explicit, never a Project fallback.
    """
    def get_review(self, transaction: object, scope: str, project_id: UUID | None,
                   review_id: UUID) -> ReviewIdentitySnapshot | None: ...
    def get_round(self, transaction: object, scope: str, project_id: UUID | None,
                  review_id: UUID, round_id: UUID) -> FixedReviewRoundSnapshot | None: ...
