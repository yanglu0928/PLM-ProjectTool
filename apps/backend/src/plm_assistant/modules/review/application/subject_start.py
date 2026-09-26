"""Bound internal Subject Owner contract; DTO construction is never approval/lock proof."""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID
from .read_snapshot import ReviewBasisObservation, ReviewIdentitySnapshot
from ..domain.round_progress import _utc, _uuid


class ReviewSubjectStartError(ValueError):
    def __init__(self):
        super().__init__("Review Subject start unavailable")


@dataclass(frozen=True, slots=True)
class ReviewSubjectStartRequest:
    actor_id: UUID
    review: ReviewIdentitySnapshot  # current trusted root, not a client snapshot
    round_id: UUID
    subject_version_id: UUID
    reviewer_ids: tuple[UUID, ...]

    def __post_init__(self):
        if (type(self.review) is not ReviewIdentitySnapshot
                or not all(_uuid(v) for v in (self.actor_id, self.round_id, self.subject_version_id))
                or type(self.reviewer_ids) is not tuple or not self.reviewer_ids
                or not all(_uuid(v) for v in self.reviewer_ids) or len(set(self.reviewer_ids)) != len(self.reviewer_ids)):
            raise ReviewSubjectStartError()
        try:
            self.review.__post_init__()
        except ValueError:
            raise ReviewSubjectStartError() from None
        if self.review.scope != "PROJECT" or self.review.state == "IN_REVIEW":
            raise ReviewSubjectStartError()


@dataclass(frozen=True, slots=True)
class PreparedReviewSubject:
    request: ReviewSubjectStartRequest
    content_fingerprint: bytes
    proof_schema_version: int
    verified_at: datetime
    qualified_reviewer_ids: tuple[UUID, ...]
    basis: tuple[ReviewBasisObservation, ...]

    def __post_init__(self):
        if type(self.request) is not ReviewSubjectStartRequest:
            raise ReviewSubjectStartError()
        self.request.__post_init__()
        if (type(self.content_fingerprint) is not bytes or len(self.content_fingerprint) != 32
                or type(self.proof_schema_version) is not int or self.proof_schema_version != 1
                or not _utc(self.verified_at) or type(self.qualified_reviewer_ids) is not tuple
                or self.qualified_reviewer_ids != self.request.reviewer_ids or type(self.basis) is not tuple
                or any(type(r) is not ReviewBasisObservation for r in self.basis)):
            raise ReviewSubjectStartError()
        seen = set()
        for ref in self.basis:
            try:
                ref.__post_init__()
            except ValueError:
                raise ReviewSubjectStartError() from None
            key = (ref.ref_kind, ref.ref_id)
            if (key in seen or ref.verified_at > self.verified_at
                    or ref.ref_scope == "PROJECT" and ref.ref_project_id != self.request.review.project_id
                    or ref.ref_scope == "GLOBAL" and ref.ref_kind != "EVIDENCE"):
                raise ReviewSubjectStartError()
            seen.add(key)

    def require_binding(self, expected: ReviewSubjectStartRequest) -> None:
        self.__post_init__()
        if type(expected) is not ReviewSubjectStartRequest:
            raise ReviewSubjectStartError()
        expected.__post_init__()
        if self.request != expected:
            raise ReviewSubjectStartError()


class ReviewSubjectStartPort(Protocol):
    """Trusted registered Owner, same transaction, no Review-owned or foreign SQL.

    Prepare must re-read current Actor and EVERY reviewer's concrete Subject
    eligibility, immutable version and Sources, acquire the REAL identity lock
    blocking edits and replacement drafts, and bind it to review/round/version.
    The returned DTO/UUID/fingerprint is not proof this work happened.

    assert_active_lock must independently verify the actual Owner lock/version
    binding while locks remain held; raise on missing/changed facts. No default
    implementation, True sentinel, client-provided proof or process-only lock.
    Caller persists complete round+Audit+receipt atomically; rollback rolls back
    Owner work too. Terminal Owner consumption/release is a separate contract.
    """
    def prepare_start_in_transaction(self, tx: object, request: ReviewSubjectStartRequest) -> PreparedReviewSubject: ...
    def assert_active_lock_in_transaction(self, tx: object, request: ReviewSubjectStartRequest) -> None: ...
