"""Application owner for immutable persisted AI execution Content Plans."""

from __future__ import annotations

import hmac
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.ai.application.execution_content_plan import (
    AIExecutionContentPlan,
    content_plan_fingerprint,
)
from plm_assistant.modules.ai.application.execution_envelope import AIExecutionEnvelope


class AIExecutionContentPlanPersistenceError(RuntimeError):
    def __init__(self, code: str = "AI_EXECUTION_CONTENT_PLAN_PERSISTENCE_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


@dataclass(frozen=True, slots=True)
class PersistedAIExecutionContentPlan:
    """No-content persistence projection plus the approved Envelope proof."""

    egress_preview_id: uuid.UUID
    plan: AIExecutionContentPlan
    plan_fingerprint: bytes = field(repr=False)
    payload_fingerprint: bytes = field(repr=False)
    record_count: int
    payload_bytes: int
    input_tokens: int

    def __post_init__(self) -> None:
        if (not _id(self.egress_preview_id)
                or type(self.plan) is not AIExecutionContentPlan
                or not _digest(self.plan_fingerprint)
                or not _digest(self.payload_fingerprint)
                or type(self.record_count) is not int
                or not 1 <= self.record_count <= 1_000_000_000
                or type(self.payload_bytes) is not int
                or not 1 <= self.payload_bytes <= 100_000_000
                or type(self.input_tokens) is not int
                or not 1 <= self.input_tokens <= 1_073_741_824):
            raise AIExecutionContentPlanPersistenceError()
        try:
            self.plan.__post_init__()
            expected = content_plan_fingerprint(self.plan)
        except Exception:
            raise AIExecutionContentPlanPersistenceError() from None
        if (not hmac.compare_digest(self.plan_fingerprint, expected)
                or self.record_count != sum(
                    source.record_count for source in self.plan.sources
                ) + self.plan.context.record_count):
            raise AIExecutionContentPlanPersistenceError()


class AIExecutionContentPlanRepositoryPort(Protocol):
    def get_by_id(
        self, transaction: object, *, content_plan_id: uuid.UUID,
    ) -> PersistedAIExecutionContentPlan | None: ...

    def get_by_preview(
        self, transaction: object, *, egress_preview_id: uuid.UUID,
    ) -> PersistedAIExecutionContentPlan | None: ...

    def add(
        self, transaction: object, *, value: PersistedAIExecutionContentPlan,
    ) -> None: ...


class AIExecutionContentPlanOwner:
    def __init__(self, repository: AIExecutionContentPlanRepositoryPort) -> None:
        if repository is None:
            raise ValueError("AI execution Content Plan repository required")
        self._repository = repository

    def persist(
        self, transaction: object, *, egress_preview_id: uuid.UUID,
        plan: AIExecutionContentPlan, envelope: AIExecutionEnvelope,
    ) -> PersistedAIExecutionContentPlan:
        if (not _id(egress_preview_id)
                or type(plan) is not AIExecutionContentPlan
                or type(envelope) is not AIExecutionEnvelope):
            raise AIExecutionContentPlanPersistenceError()
        try:
            plan.__post_init__()
            envelope.__post_init__()
            expected_plan_fingerprint = content_plan_fingerprint(plan)
        except Exception:
            raise AIExecutionContentPlanPersistenceError() from None
        if (envelope.content_plan_id != plan.content_plan_id
                or not hmac.compare_digest(
                    envelope.content_plan_fingerprint,
                    expected_plan_fingerprint,
                )
                or envelope.source_projection_fingerprints != tuple(
                    source.projection_fingerprint for source in plan.sources
                )
                or (envelope.encoding_ref, envelope.encoding_version) != (
                    plan.envelope_encoding_ref, plan.envelope_encoding_version,
                )
                or (envelope.token_estimator_ref,
                    envelope.token_estimator_version) != (
                    plan.token_estimator_ref, plan.token_estimator_version,
                )
                or envelope.context_bundle_fingerprint
                   != plan.context.context_bundle_fingerprint):
            raise AIExecutionContentPlanPersistenceError(
                "AI_EXECUTION_CONTENT_PLAN_ENVELOPE_MISMATCH",
            )
        value = PersistedAIExecutionContentPlan(
            egress_preview_id, plan, expected_plan_fingerprint,
            envelope.payload_fingerprint, envelope.record_count,
            envelope.payload_bytes, envelope.input_tokens,
        )
        by_id = self._repository.get_by_id(
            transaction, content_plan_id=plan.content_plan_id,
        )
        by_preview = self._repository.get_by_preview(
            transaction, egress_preview_id=egress_preview_id,
        )
        if by_id is not None or by_preview is not None:
            if by_id == value and by_preview == value:
                return value
            raise AIExecutionContentPlanPersistenceError(
                "AI_EXECUTION_CONTENT_PLAN_CONFLICT",
            )
        self._repository.add(transaction, value=value)
        stored = self._repository.get_by_id(
            transaction, content_plan_id=plan.content_plan_id,
        )
        if stored != value:
            raise AIExecutionContentPlanPersistenceError(
                "AI_EXECUTION_CONTENT_PLAN_WRITE_NOT_VISIBLE",
            )
        return stored

    def get(
        self, transaction: object, *, content_plan_id: uuid.UUID,
    ) -> PersistedAIExecutionContentPlan | None:
        if not _id(content_plan_id):
            return None
        value = self._repository.get_by_id(
            transaction, content_plan_id=content_plan_id,
        )
        if value is not None:
            value.__post_init__()
        return value
