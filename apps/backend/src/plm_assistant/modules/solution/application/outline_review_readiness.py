"""Internal same-transaction Outline Review readiness, never an old Audit replay."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from .outline_version_history import OutlineVersionHistoryView
from .outline_version_validation_contract import (
    OutlineCurrentFactQuery,
    OutlineVersionValidationFacts,
)
from .prove_outline_version_current import OutlineVersionCurrentFactsService


class OutlineReviewReadinessError(RuntimeError):
    """The exact latest Outline version is not currently ready for Review."""


class OutlineReviewSourcePort(Protocol):
    def lock_latest(self, transaction: object, *, project_id: uuid.UUID,
                    outline_id: uuid.UUID, version_id: uuid.UUID,
                    required_state: str,
                    ) -> OutlineVersionHistoryView | None: ...


@dataclass(frozen=True, slots=True)
class OutlineReviewReadinessProof:
    version: OutlineVersionHistoryView
    facts: OutlineVersionValidationFacts
    verified_at: datetime
    content_fingerprint: bytes = field(repr=False)
    required_state: str = "DRAFT"

    def __post_init__(self) -> None:
        if (type(self.version) is not OutlineVersionHistoryView
                or type(self.facts) is not OutlineVersionValidationFacts
                or self.required_state not in ("DRAFT", "IN_REVIEW")
                or self.version.version_state != self.required_state
                or type(self.content_fingerprint) is not bytes
                or self.content_fingerprint != self.version.content_fingerprint
                or type(self.verified_at) is not datetime
                or self.verified_at.tzinfo is None
                or self.verified_at.utcoffset() is None
                or any(getattr(self.facts, name) != "PASS" for name in (
                    "order", "source", "coverage"))):
            raise OutlineReviewReadinessError()


class OutlineReviewReadinessService:
    """Re-observe all three dimensions under the caller's transaction."""

    def __init__(self, *, repository: OutlineReviewSourcePort,
                 current: OutlineVersionCurrentFactsService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if repository is None or current is None:
            raise ValueError("Outline Review readiness dependencies required")
        self._repository, self._current = repository, current
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, *, query: OutlineCurrentFactQuery,
              required_state: str = "DRAFT") -> OutlineReviewReadinessProof:
        if (transaction is None or type(query) is not OutlineCurrentFactQuery
                or required_state not in ("DRAFT", "IN_REVIEW")):
            raise OutlineReviewReadinessError()
        try:
            query.__post_init__()
            version = self._repository.lock_latest(
                transaction, project_id=query.project_id,
                outline_id=query.solution_outline_id,
                version_id=query.solution_outline_version_id,
                required_state=required_state)
            if (type(version) is not OutlineVersionHistoryView
                    or (version.project_id, version.solution_outline_id,
                        version.solution_outline_version_id) != (
                            query.project_id, query.solution_outline_id,
                            query.solution_outline_version_id)
                    or version.version_state != required_state
                    or type(version.content_fingerprint) is not bytes
                    or len(version.content_fingerprint) != 32):
                raise OutlineReviewReadinessError()
            facts = self._current.facts(
                transaction, command=query, version=version)
            if type(facts) is not OutlineVersionValidationFacts:
                raise OutlineReviewReadinessError()
            now = self._clock()
            if (type(now) is not datetime or now.tzinfo is None
                    or now.utcoffset() is None):
                raise OutlineReviewReadinessError()
            return OutlineReviewReadinessProof(
                version, facts, now.astimezone(timezone.utc),
                version.content_fingerprint, required_state)
        except OutlineReviewReadinessError:
            raise
        except Exception:
            raise OutlineReviewReadinessError() from None
