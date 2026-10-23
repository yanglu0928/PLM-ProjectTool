"""Internal, read-only Section Review readiness; caller owns authorization/transaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol

from .read_section_version import SectionVersionHistoryView
from .section_version_validation_contract import (
    SectionCurrentFactQuery, SectionVersionValidationFacts,
)
from .validate_section_version import SectionVersionCurrentValidator


class SectionReviewReadinessError(RuntimeError):
    """The exact latest DRAFT cannot be proved ready from current facts."""


class SectionReviewSourcePort(Protocol):
    def lock_latest(self, transaction: object, *, project_id: uuid.UUID,
                    section_id: uuid.UUID,
                    version_id: uuid.UUID) -> SectionVersionHistoryView | None: ...


@dataclass(frozen=True, slots=True)
class SectionReviewReadinessProof:
    version: SectionVersionHistoryView
    facts: SectionVersionValidationFacts
    verified_at: datetime
    content_fingerprint: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.version) is not SectionVersionHistoryView
                or type(self.facts) is not SectionVersionValidationFacts
                or self.version.version_state != "DRAFT"
                or type(self.content_fingerprint) is not bytes
                or self.content_fingerprint != self.version.content_fingerprint
                or type(self.verified_at) is not datetime
                or self.verified_at.tzinfo is None
                or self.verified_at.utcoffset() is None
                or any(getattr(self.facts, name) != "PASS" for name in (
                    "integrity", "content", "requirements", "evidence", "trace", "spec"))):
            raise SectionReviewReadinessError()


class SectionReviewReadinessService:
    """Re-observe six dimensions; never consumes VALIDATE Audit or receipt."""

    def __init__(self, *, repository: SectionReviewSourcePort,
                 current: SectionVersionCurrentValidator,
                 clock: Callable[[], datetime] | None = None) -> None:
        if repository is None or current is None:
            raise ValueError("Section Review readiness dependencies required")
        self._repository, self._current = repository, current
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, *, query: SectionCurrentFactQuery,
              ) -> SectionReviewReadinessProof:
        if transaction is None or type(query) is not SectionCurrentFactQuery:
            raise SectionReviewReadinessError()
        try:
            query.__post_init__()
            version = self._repository.lock_latest(
                transaction, project_id=query.project_id,
                section_id=query.solution_section_id,
                version_id=query.solution_section_version_id)
            if (type(version) is not SectionVersionHistoryView
                    or (version.project_id, version.solution_section_id,
                        version.solution_section_version_id) != (
                            query.project_id, query.solution_section_id,
                            query.solution_section_version_id)
                    or version.version_state != "DRAFT"
                    or type(version.content_fingerprint) is not bytes
                    or len(version.content_fingerprint) != 32):
                raise SectionReviewReadinessError()
            facts = self._current.facts(transaction, command=query, version=version)
            if type(facts) is not SectionVersionValidationFacts:
                raise SectionReviewReadinessError()
            now = self._clock()
            if (type(now) is not datetime or now.tzinfo is None
                    or now.utcoffset() is None):
                raise SectionReviewReadinessError()
            return SectionReviewReadinessProof(
                version, facts, now.astimezone(timezone.utc),
                version.content_fingerprint)
        except SectionReviewReadinessError:
            raise
        except Exception:
            raise SectionReviewReadinessError() from None
