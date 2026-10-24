"""Current-admin read of a fixed CAP-01 GLOBAL Review; metadata is not approval proof."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.auth.application.current_user import CurrentUserFacts
from plm_assistant.modules.capability.application.read_capability import CapabilityVersionView
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

from .read_snapshot import FixedReviewRoundSnapshot, ReviewIdentitySnapshot


class GlobalCapabilityReviewReadError(RuntimeError):
    def __init__(self, code: str = "GLOBAL_REVIEW_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class GetGlobalCapabilityReview:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    review_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class AuthorizedGlobalCapabilityReview:
    review: ReviewIdentitySnapshot
    fixed_round: FixedReviewRoundSnapshot

    @property
    def review_etag(self) -> str:
        return f'"v{self.review.lock_version}"'

    @property
    def round_etag(self) -> str:
        return f'"v{self.fixed_round.round_lock_version}"'


class _SessionPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class _UserPort(Protocol):
    def current_enabled_user(self, transaction: object, *, user_id: uuid.UUID
                             ) -> CurrentUserFacts | None: ...


class _LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class _ReviewPort(Protocol):
    def get_single_global_round_id(self, transaction: object, *,
                                   review_id: uuid.UUID) -> uuid.UUID | None: ...
    def get_review(self, transaction: object, scope: str, project_id: None,
                   review_id: uuid.UUID) -> ReviewIdentitySnapshot | None: ...
    def get_round(self, transaction: object, scope: str, project_id: None,
                  review_id: uuid.UUID, round_id: uuid.UUID
                  ) -> FixedReviewRoundSnapshot | None: ...


class _CapabilityPort(Protocol):
    def get_version(self, transaction: object, *, visibility: str,
                    baseline_id: uuid.UUID, baseline_version_id: uuid.UUID
                    ) -> CapabilityVersionView | None: ...


class GlobalCapabilityReviewReadService:
    def __init__(self, *, unit_of_work: Callable[[], object], sessions: _SessionPort,
                 users: _UserPort, license_guard: _LicensePort,
                 reviews: _ReviewPort, capabilities: _CapabilityPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, sessions, users, license_guard, reviews, capabilities)):
            raise ValueError("GLOBAL Capability Review read dependencies required")
        self._uow, self._sessions, self._users = unit_of_work, sessions, users
        self._guard, self._reviews, self._capabilities = license_guard, reviews, capabilities
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get(self, query: GetGlobalCapabilityReview) -> AuthorizedGlobalCapabilityReview:
        if (type(query) is not GetGlobalCapabilityReview
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.trace_id) is not uuid.UUID or not query.trace_id.int
                or type(query.review_id) is not uuid.UUID or not query.review_id.int):
            raise GlobalCapabilityReviewReadError("VALIDATION_FAILED")
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now = self._clock()
                if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                    raise GlobalCapabilityReviewReadError()
                actor = self._sessions.authenticated_user(
                    tx, session_token=query.session_token, now=now.astimezone(timezone.utc),
                )
                if type(actor) is not uuid.UUID or not actor.int:
                    raise GlobalCapabilityReviewReadError("AUTH_ACCESS_DENIED")
                facts = self._users.current_enabled_user(tx, user_id=actor)
                if type(facts) is not CurrentUserFacts or facts.user_id != actor:
                    raise GlobalCapabilityReviewReadError("RESOURCE_NOT_FOUND")
                review = self._reviews.get_review(tx, "GLOBAL", None, query.review_id)
                if review is None:
                    raise GlobalCapabilityReviewReadError("RESOURCE_NOT_FOUND")
                if (type(review) is not ReviewIdentitySnapshot
                        or review.review_id != query.review_id
                        or review.scope != "GLOBAL" or review.project_id is not None
                        or review.subject_type != "CAP-01"
                        or review.policy_code != "DEPLOYMENT_ALL_V1"):
                    raise GlobalCapabilityReviewReadError("RESOURCE_NOT_FOUND")
                review.__post_init__()
                round_id = self._reviews.get_single_global_round_id(
                    tx, review_id=query.review_id,
                )
                if type(round_id) is not uuid.UUID or not round_id.int:
                    raise GlobalCapabilityReviewReadError()
                fixed = self._reviews.get_round(
                    tx, "GLOBAL", None, query.review_id, round_id,
                )
                if (type(fixed) is not FixedReviewRoundSnapshot or fixed.review != review
                        or fixed.progress.round_id != round_id or fixed.round_no != 1):
                    raise GlobalCapabilityReviewReadError()
                fixed.__post_init__()
                if (facts.deployment_role != "DEPLOYMENT_ADMIN"
                        and actor not in fixed.progress.reviewer_ids):
                    raise GlobalCapabilityReviewReadError("RESOURCE_NOT_FOUND")
                version = self._capabilities.get_version(
                    tx, visibility="ADMIN_HISTORY", baseline_id=review.subject_id,
                    baseline_version_id=fixed.subject_version_id,
                )
                if (type(version) is not CapabilityVersionView
                        or version.baseline_id != review.subject_id
                        or version.baseline_version_id != fixed.subject_version_id
                        or version.review_ref != review.review_id
                        or version.review_round_ref != round_id):
                    raise GlobalCapabilityReviewReadError("RESOURCE_NOT_FOUND")
                return AuthorizedGlobalCapabilityReview(review, fixed)
        except GlobalCapabilityReviewReadError:
            raise
        except RuntimeLicenseError:
            raise GlobalCapabilityReviewReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise GlobalCapabilityReviewReadError() from None
