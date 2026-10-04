"""Trusted caller tx only; real authorization/idempotency entry point is separate."""
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from plm_assistant.modules.audit.application.public import AuditEventDraft
from .subject_start import ReviewSubjectStartRequest, PreparedReviewSubject
from .read_snapshot import ReviewIdentitySnapshot
from ..domain.round_progress import _uuid, _utc


class ReviewRoundPersistError(ValueError):
    def __init__(self, code="REVIEW_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StartedReviewRoundRef:
    round_id: UUID
    review_id: UUID
    project_id: UUID
    round_no: int
    subject_version_id: UUID
    started_by: UUID
    started_at: datetime

    def __post_init__(self):
        if (not all(_uuid(v) for v in (self.round_id,self.review_id,self.project_id,self.subject_version_id,self.started_by))
                or type(self.round_no) is not int or not 0 < self.round_no < 2**31 or not _utc(self.started_at)):
            raise ReviewRoundPersistError()


class ReviewRoundPersistenceService:
    """Caller has already authenticated, authorized PM/License/Project/reviewers.

    No UOW creation, commit, receipt or HTTP. Caller owns transaction rollback;
    Owner must be registered/trusted and actually hold the concrete Subject lock.
    """
    def __init__(self, *, repository, audit, subjects=None, clock=None):
        if repository is None or audit is None:
            raise ValueError("Review round persistence dependencies required")
        self._repository, self._audit, self._subjects = repository, audit, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def start_in_transaction(self, tx, *, actor_id, project_id, review_id, subject_version_id,
                             reviewer_ids, expected_version, trace_id):
        if (not all(_uuid(v) for v in (actor_id,project_id,review_id,subject_version_id,trace_id))
                or type(expected_version) is not int or not 0 <= expected_version < 2**63-1):
            raise ReviewRoundPersistError("VALIDATION_FAILED")
        if self._subjects is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        identity, round_id = self._repository.lock_start_context(tx, project_id=project_id, review_id=review_id)
        if identity is None:
            raise ReviewRoundPersistError("RESOURCE_NOT_FOUND")
        if (type(identity) is not ReviewIdentitySnapshot or identity.scope != "PROJECT"
                or identity.project_id != project_id or identity.review_id != review_id):
            raise ReviewRoundPersistError()
        if identity.lock_version != expected_version:
            raise ReviewRoundPersistError("CONFLICT_VERSION")
        if identity.state == "IN_REVIEW":
            raise ReviewRoundPersistError("REVIEW_SUBJECT_LOCKED")
        request = ReviewSubjectStartRequest(actor_id, identity, round_id, subject_version_id, reviewer_ids)
        prepared = self._subjects.prepare_start_in_transaction(tx, request)
        if type(prepared) is not PreparedReviewSubject:
            raise ReviewRoundPersistError()
        prepared.require_binding(request)
        if self._subjects.assert_active_lock_in_transaction(tx, request) is not None:
            raise ReviewRoundPersistError()
        now = self._clock()
        if not _utc(now) or now < prepared.verified_at:
            raise ReviewRoundPersistError()
        result = self._repository.insert_round(tx, prepared=prepared, trace_id=trace_id, started_at=now)
        if (type(result) is not StartedReviewRoundRef or result.round_id != round_id or result.review_id != review_id
                or result.project_id != project_id or result.subject_version_id != subject_version_id or result.started_by != actor_id
                or result.started_at != now):
            raise ReviewRoundPersistError()
        result.__post_init__()
        if self._subjects.assert_active_lock_in_transaction(tx, request) is not None:
            raise ReviewRoundPersistError()
        self._audit.append(tx, AuditEventDraft(trace_id=trace_id, event_scope="PROJECT", target_project_id=project_id,
            actor_type="USER", actor_id=actor_id, original_actor_id=None, actor_hint_digest=None,
            action="REVIEW_STARTED", outcome="SUCCESS", target_owner_module="review", target_object_type="RVW-02",
            target_object_id=round_id, after_state="IN_REVIEW"))
        return result
