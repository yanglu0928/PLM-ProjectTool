"""Atomically reconcile one expired RAG build without retrying external work."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService


class RAGEmbeddingBuildReconciliationError(RuntimeError):
    def __init__(self, code: str = "RAG_INDEX_BUILD_RECONCILIATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReconciledRAGEmbeddingBuildFailure:
    job_id: uuid.UUID
    embedding_build_id: uuid.UUID
    embedding_index_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    prior_running_batch_count: int
    error_code: str
    retryable: bool
    completed_at: datetime

    def __post_init__(self) -> None:
        required = (
            self.job_id, self.embedding_build_id, self.embedding_index_id,
            self.requested_by, self.trace_id,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in required)
                or self.scope not in {"GLOBAL", "PROJECT"}
                or (self.scope == "GLOBAL" and self.project_id is not None)
                or (self.scope == "PROJECT" and (
                    type(self.project_id) is not uuid.UUID or not self.project_id.int))
                or type(self.prior_running_batch_count) is not int
                or self.prior_running_batch_count < 0
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", self.error_code) is None
                or type(self.retryable) is not bool or self.retryable
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise RAGEmbeddingBuildReconciliationError()
        expected = (
            "RAG_PROVIDER_OUTCOME_UNKNOWN"
            if self.prior_running_batch_count else "RAG_BUILD_LEASE_EXPIRED"
        )
        if self.error_code != expected:
            raise RAGEmbeddingBuildReconciliationError()


class RAGEmbeddingBuildReconciliationStorePort(Protocol):
    def reconcile_next(
        self, transaction: object,
    ) -> ReconciledRAGEmbeddingBuildFailure | None: ...


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class ExpiredRAGEmbeddingBuildReconciler:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 store: RAGEmbeddingBuildReconciliationStorePort,
                 audit: AuditService, system_actor: _SystemActor) -> None:
        if any(value is None for value in (unit_of_work, store, audit, system_actor)):
            raise ValueError("RAG build reconciliation dependencies required")
        self._uow = unit_of_work
        self._store = store
        self._audit = audit
        self._actor = system_actor

    def reconcile_next(self) -> ReconciledRAGEmbeddingBuildFailure | None:
        try:
            actor_id = self._actor.assert_current()
            if type(actor_id) is not uuid.UUID or not actor_id.int:
                raise RAGEmbeddingBuildReconciliationError("SYSTEM_ACTOR_UNAVAILABLE")
            with self._uow() as transaction:
                result = self._store.reconcile_next(transaction)
                if result is None:
                    return None
                if type(result) is not ReconciledRAGEmbeddingBuildFailure:
                    raise RAGEmbeddingBuildReconciliationError()
                result.__post_init__()
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=result.trace_id,
                    event_scope=result.scope,
                    target_project_id=result.project_id,
                    actor_type="SYSTEM",
                    actor_id=actor_id,
                    original_actor_id=result.requested_by,
                    actor_hint_digest=None,
                    action="RAG_INDEX_BUILD_RECONCILED",
                    outcome="FAILED",
                    target_owner_module="rag",
                    target_object_type="RAG-03",
                    target_object_id=result.embedding_index_id,
                    target_version_id=result.embedding_build_id,
                    reason_code=result.error_code,
                    before_state="RUNNING",
                    after_state="FAILED",
                ))
                if (type(event_id) is not uuid.UUID or not event_id.int
                        or self._actor.assert_current() != actor_id):
                    raise RAGEmbeddingBuildReconciliationError()
                transaction.commit()
            return result
        except RAGEmbeddingBuildReconciliationError:
            raise
        except Exception:
            raise RAGEmbeddingBuildReconciliationError() from None
