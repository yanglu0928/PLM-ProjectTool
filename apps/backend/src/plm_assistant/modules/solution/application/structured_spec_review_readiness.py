"""Current SOL-06 readiness proof for the unified Review Subject Owner."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Protocol

from .evaluate_structured_spec_validation import (
    StructuredSpecCurrentFactEvaluator,
    StructuredSpecCurrentFactQuery,
)
from .structured_spec_validation_contract import (
    StructuredSpecValidationObservation,
    StructuredSpecValidationSnapshot,
)
from .structured_spec_validation_source import StructuredSpecValidationSource


class StructuredSpecReviewReadinessError(RuntimeError):
    """Current fixed design cannot be proven ready for Review."""


class StructuredSpecReviewSourcePort(Protocol):
    def lock_source(
        self, transaction: object, *, project_id: uuid.UUID,
        spec_id: uuid.UUID,
    ) -> StructuredSpecValidationSource | None: ...


@dataclass(frozen=True, slots=True)
class StructuredSpecReviewReadinessProof:
    snapshot: StructuredSpecValidationSnapshot
    verified_at: datetime

    def __post_init__(self) -> None:
        if (type(self.snapshot) is not StructuredSpecValidationSnapshot
                or type(self.verified_at) is not datetime
                or self.verified_at.tzinfo is None
                or self.verified_at.utcoffset() is None):
            raise StructuredSpecReviewReadinessError()


class StructuredSpecReviewReadinessService:
    """Re-evaluate all current facts; never trusts a stored VALIDATE Audit."""

    def __init__(
        self, *, repository: StructuredSpecReviewSourcePort,
        evaluator: StructuredSpecCurrentFactEvaluator,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if repository is None or evaluator is None:
            raise ValueError("Structured spec Review readiness dependencies required")
        self._repository, self._evaluator = repository, evaluator
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(
        self, transaction: object, *, query: StructuredSpecCurrentFactQuery,
        series_id: uuid.UUID, required_state: str,
    ) -> StructuredSpecReviewReadinessProof:
        if (transaction is None
                or type(query) is not StructuredSpecCurrentFactQuery
                or type(series_id) is not uuid.UUID or series_id.int == 0
                or required_state not in ("DRAFT", "IN_REVIEW")):
            raise StructuredSpecReviewReadinessError()
        try:
            query.__post_init__()
            source = self._repository.lock_source(
                transaction, project_id=query.project_id,
                spec_id=query.structured_solution_spec_id)
            if (type(source) is not StructuredSpecValidationSource
                    or source.snapshot.spec_series_id != series_id
                    or source.snapshot.version_state != required_state
                    or not source.is_current_version):
                raise StructuredSpecReviewReadinessError()
            observation = self._evaluator.evaluate_for_review(
                transaction, query=query, source=source)
            if (type(observation) is not StructuredSpecValidationObservation
                    or any(getattr(observation.facts, name) != "PASS"
                           for name in (
                               "integrity", "payload", "requirements",
                               "sections", "evidence", "artifacts", "trace",
                               "current_version"))
                    or observation.type_checks.spec_type
                    != source.snapshot.spec_type
                    or any(item.status != "PASS"
                           for item in observation.type_checks.checks)):
                raise StructuredSpecReviewReadinessError()
            now = self._clock()
            if (type(now) is not datetime or now.tzinfo is None
                    or now.utcoffset() is None):
                raise StructuredSpecReviewReadinessError()
            return StructuredSpecReviewReadinessProof(
                source.snapshot, now.astimezone(timezone.utc))
        except StructuredSpecReviewReadinessError:
            raise
        except Exception:
            raise StructuredSpecReviewReadinessError() from None
