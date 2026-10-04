"""Trusted PROJECT Review submission inside a caller-owned transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from plm_assistant.modules.audit.application.public import AuditEventDraft

from ..domain.round_progress import _utc, _uuid
from .create_review import AuthorizedReviewCreation, CreatedReviewRef, _code
from .persist_round import (
    ReviewRoundPersistenceService, ReviewRoundPersistError, StartedReviewRoundRef,
)
from .read_snapshot import ReviewIdentitySnapshot


@dataclass(frozen=True, slots=True)
class SubmittedProjectReviewRef:
    review_id: UUID
    round_id: UUID
    project_id: UUID
    subject_type: str
    subject_id: UUID
    subject_version_id: UUID
    policy_code: str
    reviewer_ids: tuple[UUID, ...]
    submitted_by: UUID
    submitted_at: datetime
    review_after_version: int = 1
    round_no: int = 1

    def __post_init__(self) -> None:
        if (not all(_uuid(value) for value in (
                self.review_id, self.round_id, self.project_id, self.subject_id,
                self.subject_version_id, self.submitted_by))
                or not _code(self.subject_type, subject=True)
                or not _code(self.policy_code)
                or type(self.reviewer_ids) is not tuple or not self.reviewer_ids
                or any(not _uuid(value) for value in self.reviewer_ids)
                or len(set(self.reviewer_ids)) != len(self.reviewer_ids)
                or not _utc(self.submitted_at)
                or self.review_after_version != 1 or self.round_no != 1):
            raise ReviewRoundPersistError()


@dataclass(frozen=True, slots=True)
class PersistedProjectReviewSubmission:
    review: ReviewIdentitySnapshot
    submission: SubmittedProjectReviewRef

    def __post_init__(self) -> None:
        if (type(self.review) is not ReviewIdentitySnapshot
                or type(self.submission) is not SubmittedProjectReviewRef):
            raise ReviewRoundPersistError()
        self.review.__post_init__()
        self.submission.__post_init__()
        if (self.review.review_id != self.submission.review_id
                or self.review.scope != "PROJECT"
                or self.review.project_id != self.submission.project_id
                or self.review.subject_type != self.submission.subject_type
                or self.review.subject_id != self.submission.subject_id
                or self.review.policy_code != self.submission.policy_code):
            raise ReviewRoundPersistError()


class ProjectReviewPersistenceService:
    """Create and start one PROJECT Review without exposing an intermediate draft."""

    def __init__(self, *, creation_repository, round_repository, audit,
                 subjects=None, clock=None) -> None:
        if creation_repository is None or round_repository is None or audit is None:
            raise ValueError("PROJECT Review persistence dependencies required")
        self._creation, self._round_repository = creation_repository, round_repository
        self._audit, self._subjects = audit, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._rounds = ReviewRoundPersistenceService(
            repository=round_repository, audit=audit, subjects=subjects,
            clock=self._clock,
        )

    def submit_in_transaction(
        self, tx, *, actor_id, project_id, subject_type, subject_id,
        subject_version_id, reviewer_ids, policy_code, trace_id,
    ) -> SubmittedProjectReviewRef:
        if (not all(_uuid(value) for value in (
                actor_id, project_id, subject_id, subject_version_id, trace_id))
                or not _code(subject_type, subject=True) or not _code(policy_code)
                or type(reviewer_ids) is not tuple or not reviewer_ids
                or any(not _uuid(value) for value in reviewer_ids)
                or len(set(reviewer_ids)) != len(reviewer_ids)):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if self._subjects is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        proof = self._subjects.authorize_create(
            tx, user_id=actor_id, project_id=project_id,
            subject_type=subject_type, subject_id=subject_id,
            subject_version_id=subject_version_id,
        )
        if (type(proof) is not AuthorizedReviewCreation
                or proof.user_id != actor_id or proof.project_id != project_id
                or proof.subject_type != subject_type or proof.subject_id != subject_id
                or proof.subject_version_id != subject_version_id
                or proof.policy_code != policy_code):
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        created = self._creation.create(tx, proof=proof)
        if (type(created) is not CreatedReviewRef
                or created.project_id != project_id
                or created.subject_type != subject_type
                or created.subject_id != subject_id
                or created.policy_code != policy_code
                or created.created_by != actor_id):
            raise ReviewRoundPersistError()
        created.__post_init__()
        self._audit.append(tx, AuditEventDraft(
            trace_id=trace_id, event_scope="PROJECT",
            target_project_id=project_id, actor_type="USER", actor_id=actor_id,
            original_actor_id=None, actor_hint_digest=None,
            action="REVIEW_CREATED", outcome="SUCCESS",
            target_owner_module="review", target_object_type="RVW-01",
            target_object_id=created.review_id, after_state="DRAFT",
        ))
        started = self._rounds.start_in_transaction(
            tx, actor_id=actor_id, project_id=project_id,
            review_id=created.review_id, subject_version_id=subject_version_id,
            reviewer_ids=reviewer_ids, expected_version=0, trace_id=trace_id,
        )
        if (type(started) is not StartedReviewRoundRef
                or started.review_id != created.review_id
                or started.project_id != project_id
                or started.subject_version_id != subject_version_id
                or started.started_by != actor_id or started.round_no != 1):
            raise ReviewRoundPersistError()
        result = SubmittedProjectReviewRef(
            created.review_id, started.round_id, project_id,
            subject_type, subject_id, subject_version_id, policy_code,
            reviewer_ids, actor_id, started.started_at,
        )
        result.__post_init__()
        return result

    def is_retryable_deadlock(self, error: Exception) -> bool:
        classifier = getattr(self._round_repository, "is_retryable_deadlock", None)
        return callable(classifier) and classifier(error) is True
