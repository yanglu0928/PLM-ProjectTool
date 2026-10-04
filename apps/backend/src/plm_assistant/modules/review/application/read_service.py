"""Internal PROJECT reads, current authorization first; no public router or Gate proof."""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, AuthorizedProjectAction, ProjectAuthorizationError,
)
from .read_snapshot import FixedReviewRoundSnapshot, ReviewIdentitySnapshot, ReviewSnapshotReadPort
from ..domain.round_progress import _uuid


class ReviewReadError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReviewReadQuery:
    session_token: bytes = field(repr=False)
    project_id: UUID
    review_id: UUID
    trace_id: UUID
    round_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class AuthorizedReviewSubjectRead:
    """Trusted Owner's access result, not a signature or customer approval."""
    user_id: UUID
    project_id: UUID
    subject_type: str
    subject_id: UUID
    subject_version_id: UUID | None


@dataclass(frozen=True, slots=True)
class AuthorizedReviewRead:
    review: ReviewIdentitySnapshot
    fixed_round: FixedReviewRoundSnapshot | None

    @property
    def etag(self) -> str:
        return f'"v{self.review.lock_version}"'


class ReviewReadSessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes, now: datetime) -> UUID | None: ...


class ReviewReadProjectPort(Protocol):
    def require_in_transaction(self, transaction: object, *, user_id: UUID,
                               project_id: UUID, operation: str) -> AuthorizedProjectAction: ...


class ReviewReadLicensePort(Protocol):
    def require_valid(self, *, trace_id: UUID) -> object: ...


class ReviewSubjectReadPort(Protocol):
    """Owner rereads/locks current access facts in caller tx; unknown Owner returns None.

    Identity permission and requested historical version permission are separate.
    No implicit assignment/admin bypass, no source content permission, no Gate proof.
    """
    def authorize_read(self, transaction: object, *, user_id: UUID, project_id: UUID,
                       subject_type: str, subject_id: UUID,
                       subject_version_id: UUID | None) -> AuthorizedReviewSubjectRead | None: ...


class ReviewReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], sessions: ReviewReadSessionPort,
                 projects: ReviewReadProjectPort, license_guard: ReviewReadLicensePort,
                 repository: ReviewSnapshotReadPort, subjects: ReviewSubjectReadPort | None = None,
                 clock: Callable[[], datetime] | None = None):
        if any(v is None for v in (unit_of_work, sessions, projects, license_guard, repository)):
            raise ValueError("Review read dependencies required")
        self._uow, self._sessions, self._projects = unit_of_work, sessions, projects
        self._guard, self._repository, self._subjects = license_guard, repository, subjects
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _authorize_subject(self, tx, actor, identity, version):
        if self._subjects is None:
            raise ReviewReadError("RESOURCE_NOT_FOUND")
        proof = self._subjects.authorize_read(tx, user_id=actor, project_id=identity.project_id,
            subject_type=identity.subject_type, subject_id=identity.subject_id, subject_version_id=version)
        if (type(proof) is not AuthorizedReviewSubjectRead or proof.user_id != actor
                or proof.project_id != identity.project_id or proof.subject_type != identity.subject_type
                or proof.subject_id != identity.subject_id or proof.subject_version_id != version):
            raise ReviewReadError("RESOURCE_NOT_FOUND")

    def get(self, query: ReviewReadQuery) -> AuthorizedReviewRead:
        if (type(query) is not ReviewReadQuery or type(query.session_token) is not bytes or len(query.session_token) != 32
                or not all(_uuid(v) for v in (query.project_id, query.review_id, query.trace_id))
                or query.round_id is not None and not _uuid(query.round_id)):
            raise ReviewReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise ReviewReadError("REVIEW_UNAVAILABLE")
                actor = self._sessions.authenticated_user(tx, session_token=query.session_token, now=now.astimezone(timezone.utc))
                if not _uuid(actor):
                    raise ReviewReadError("AUTH_ACCESS_DENIED")
                proof = self._projects.require_in_transaction(tx, user_id=actor, project_id=query.project_id, operation="REVIEW_GET")
                if (type(proof) is not AuthorizedProjectAction or proof.user_id != actor
                        or proof.project_id != query.project_id or proof.operation != "REVIEW_GET"
                        or proof.project_role not in ALL_MEMBERS):
                    raise ReviewReadError("RESOURCE_NOT_FOUND")
                identity = self._repository.get_review(tx, "PROJECT", query.project_id, query.review_id)
                if identity is None:
                    raise ReviewReadError("RESOURCE_NOT_FOUND")
                if (type(identity) is not ReviewIdentitySnapshot or identity.scope != "PROJECT"
                        or identity.project_id != query.project_id or identity.review_id != query.review_id):
                    raise ReviewReadError("REVIEW_UNAVAILABLE")
                identity.__post_init__()
                self._authorize_subject(tx, actor, identity, None)
                fixed = None
                if query.round_id is not None:
                    version = self._repository.get_round_subject_version(tx, "PROJECT", query.project_id, query.review_id, query.round_id)
                    if version is None:
                        raise ReviewReadError("RESOURCE_NOT_FOUND")
                    if not _uuid(version):
                        raise ReviewReadError("REVIEW_UNAVAILABLE")
                    self._authorize_subject(tx, actor, identity, version)
                    fixed = self._repository.get_round(tx, "PROJECT", query.project_id, query.review_id, query.round_id)
                    if (type(fixed) is not FixedReviewRoundSnapshot or fixed.review != identity
                            or fixed.progress.round_id != query.round_id or fixed.subject_version_id != version):
                        raise ReviewReadError("REVIEW_UNAVAILABLE")
                    fixed.__post_init__()
                return AuthorizedReviewRead(identity, fixed)
        except ReviewReadError:
            raise
        except ProjectAuthorizationError:
            raise ReviewReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise ReviewReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise ReviewReadError("REVIEW_UNAVAILABLE") from None
