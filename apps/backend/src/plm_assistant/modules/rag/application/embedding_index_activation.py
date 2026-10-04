"""Authorized atomic activation of a quality-approved RAG index."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)


_OPERATION = "V1_RAG_INDEX_ACTIVATE"


class RAGEmbeddingIndexActivationError(RuntimeError):
    def __init__(self, code: str = "RAG_INDEX_ACTIVATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ActivateRAGEmbeddingIndex:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    embedding_index_id: uuid.UUID
    expected_lock_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RAGEmbeddingIndexActivationTarget:
    embedding_index_id: uuid.UUID
    quality_result_ref: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    index_purpose: str
    index_state: str
    lock_version: int
    retired_index_ref: uuid.UUID | None = None
    retired_before_lock_version: int | None = None

    def __post_init__(self) -> None:
        if (
            any(type(value) is not uuid.UUID or not value.int for value in (
                self.embedding_index_id,
                self.quality_result_ref,
            ))
            or self.scope not in {"GLOBAL", "PROJECT"}
            or (self.scope == "GLOBAL") != (self.project_id is None)
            or (self.project_id is not None and (
                type(self.project_id) is not uuid.UUID or not self.project_id.int
            ))
            or type(self.index_purpose) is not str
            or not 1 <= len(self.index_purpose) <= 128
            or self.index_state not in {"READY", "ACTIVE"}
            or type(self.lock_version) is not int
            or self.lock_version not in {2, 3}
            or (self.index_state == "READY") != (self.lock_version == 2)
            or (self.retired_index_ref is None)
            != (self.retired_before_lock_version is None)
            or (self.retired_index_ref is not None and (
                type(self.retired_index_ref) is not uuid.UUID
                or not self.retired_index_ref.int
                or self.retired_index_ref == self.embedding_index_id
                or type(self.retired_before_lock_version) is not int
                or self.retired_before_lock_version < 3
            ))
        ):
            raise RAGEmbeddingIndexActivationError()


@dataclass(frozen=True, slots=True)
class ActivatedRAGEmbeddingIndex:
    activation_result_id: uuid.UUID
    embedding_index_id: uuid.UUID
    quality_result_ref: uuid.UUID
    actor_id: uuid.UUID
    audit_event_id: uuid.UUID
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    index_purpose: str
    retired_index_ref: uuid.UUID | None
    expected_lock_version: int
    lock_version: int
    retired_before_lock_version: int | None
    retired_after_lock_version: int | None
    activated_at: datetime

    def __post_init__(self) -> None:
        if (
            any(type(value) is not uuid.UUID or not value.int for value in (
                self.activation_result_id,
                self.embedding_index_id,
                self.quality_result_ref,
                self.actor_id,
                self.audit_event_id,
                self.trace_id,
            ))
            or self.scope not in {"GLOBAL", "PROJECT"}
            or (self.scope == "GLOBAL") != (self.project_id is None)
            or self.expected_lock_version != 2
            or self.lock_version != 3
            or (self.retired_index_ref is None) != (
                self.retired_before_lock_version is None
                and self.retired_after_lock_version is None
            )
            or (self.retired_index_ref is not None and (
                type(self.retired_index_ref) is not uuid.UUID
                or not self.retired_index_ref.int
                or self.retired_index_ref == self.embedding_index_id
                or type(self.retired_before_lock_version) is not int
                or type(self.retired_after_lock_version) is not int
                or self.retired_before_lock_version < 3
                or self.retired_after_lock_version
                != self.retired_before_lock_version + 1
            ))
            or not isinstance(self.activated_at, datetime)
            or self.activated_at.tzinfo is None
            or self.activated_at.utcoffset() is None
        ):
            raise RAGEmbeddingIndexActivationError()


class _Access(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class _Repository(Protocol):
    def locked_target(self, transaction: object, *, embedding_index_id: uuid.UUID,
                      actor_id: uuid.UUID,
                      now: datetime) -> RAGEmbeddingIndexActivationTarget | None: ...
    def activate(self, transaction: object, *,
                 target: RAGEmbeddingIndexActivationTarget,
                 actor_id: uuid.UUID, audit_event_id: uuid.UUID,
                 trace_id: uuid.UUID) -> ActivatedRAGEmbeddingIndex: ...
    def get(self, transaction: object, *, activation_result_id: uuid.UUID,
            embedding_index_id: uuid.UUID,
            actor_id: uuid.UUID) -> ActivatedRAGEmbeddingIndex | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class RAGEmbeddingIndexActivationService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: object, repository: _Repository,
                 receipts: _Receipts, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, repository, receipts, audit,
        )):
            raise ValueError("RAG activation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def activate(self, command: ActivateRAGEmbeddingIndex) -> ActivatedRAGEmbeddingIndex:
        now = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "embedding_index_id": str(command.embedding_index_id),
                "expected_lock_version": command.expected_lock_version,
            })
        except IdempotencyError:
            raise RAGEmbeddingIndexActivationError("VALIDATION_FAILED") from None
        try:
            with self._uow() as tx:
                self._require_user(tx, command, now)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_user(tx, command, now)
                target = self._repo.locked_target(
                    tx, embedding_index_id=command.embedding_index_id,
                    actor_id=actor, now=now,
                )
                if type(target) is not RAGEmbeddingIndexActivationTarget:
                    raise RAGEmbeddingIndexActivationError("RAG_INDEX_NOT_FOUND")
                target.__post_init__()
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=target.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise RAGEmbeddingIndexActivationError()
                    original = self._repo.get(
                        tx, activation_result_id=replay.ref_id,
                        embedding_index_id=command.embedding_index_id,
                        actor_id=actor,
                    )
                    if type(original) is not ActivatedRAGEmbeddingIndex:
                        raise RAGEmbeddingIndexActivationError()
                    original.__post_init__()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return original
                if target.index_state != "READY" or target.lock_version != 2:
                    raise RAGEmbeddingIndexActivationError("CONFLICT_VERSION")
                if command.expected_lock_version != target.lock_version:
                    raise RAGEmbeddingIndexActivationError("CONFLICT_VERSION")
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope=("DEPLOYMENT" if target.scope == "GLOBAL"
                                 else "PROJECT"),
                    target_project_id=target.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="RAG_INDEX_ACTIVATED", outcome="SUCCESS",
                    target_owner_module="rag", target_object_type="RAG-03",
                    target_object_id=target.embedding_index_id,
                    target_version_id=target.quality_result_ref,
                    before_state="READY", after_state="ACTIVE",
                ))
                if type(audit_id) is not uuid.UUID or not audit_id.int:
                    raise RAGEmbeddingIndexActivationError()
                result = self._repo.activate(
                    tx, target=target, actor_id=actor,
                    audit_event_id=audit_id, trace_id=command.trace_id,
                )
                if type(result) is not ActivatedRAGEmbeddingIndex:
                    raise RAGEmbeddingIndexActivationError()
                result.__post_init__()
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _OPERATION, result.activation_result_id, 200,
                ))
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except RAGEmbeddingIndexActivationError:
            raise
        except RuntimeLicenseError:
            raise RAGEmbeddingIndexActivationError(
                "LICENSE_OPERATION_DENIED",
            ) from None
        except IdempotencyError as error:
            raise RAGEmbeddingIndexActivationError(error.code) from None
        except Exception:
            raise RAGEmbeddingIndexActivationError() from None

    def _validate(self, command: ActivateRAGEmbeddingIndex) -> datetime:
        try:
            now = self._clock()
        except Exception:
            raise RAGEmbeddingIndexActivationError() from None
        if (
            type(command) is not ActivateRAGEmbeddingIndex
            or type(command.session_token) is not bytes
            or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes
            or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID
            or not command.trace_id.int
            or type(command.embedding_index_id) is not uuid.UUID
            or not command.embedding_index_id.int
            or command.expected_lock_version != 2
            or not isinstance(now, datetime)
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise RAGEmbeddingIndexActivationError("VALIDATION_FAILED")
        return now.astimezone(timezone.utc)

    def _require_user(self, tx: object, command: ActivateRAGEmbeddingIndex,
                      now: datetime) -> uuid.UUID:
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise RAGEmbeddingIndexActivationError("AUTH_ACCESS_DENIED")
        return actor
