"""Authorized registration of immutable held-out RAG quality evidence."""

from __future__ import annotations

import re
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
_OPERATION = "V1_RAG_INDEX_QUALITY_REGISTER"
_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,255}$")
_PURPOSE_REF = re.compile(r"^[A-Za-z][A-Za-z0-9._:/-]{0,127}$")
_POLICY = "rag-business-quality-v1"
_FAILURE = "RAG_BUSINESS_QUALITY_THRESHOLD_FAILED"


class RAGEmbeddingIndexQualityError(RuntimeError):
    def __init__(self, code: str = "RAG_INDEX_QUALITY_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RegisterRAGEmbeddingIndexQuality:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    embedding_index_id: uuid.UUID
    expected_lock_version: int
    dataset_ref: str
    dataset_fingerprint: bytes = field(repr=False)
    isolation_attestation_fingerprint: bytes = field(repr=False)
    evaluation_artifact_fingerprint: bytes = field(repr=False)
    dataset_case_count: int
    classification_correct_count: int
    exact_citation_correct_count: int
    project_isolation_pass: bool
    out_of_scope_citation_count: int
    failure_closure_pass: bool
    dataset_sealed_at: datetime
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RAGEmbeddingIndexQualityTarget:
    embedding_index_id: uuid.UUID
    technical_validation_ref: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    index_purpose: str
    embedding_model_ref: uuid.UUID
    source_snapshot_fingerprint: bytes = field(repr=False)
    index_state: str = "READY"
    lock_version: int = 2

    def __post_init__(self) -> None:
        ids = (self.embedding_index_id, self.technical_validation_ref,
               self.embedding_model_ref)
        if (any(type(value) is not uuid.UUID or not value.int for value in ids)
                or self.scope not in {"GLOBAL", "PROJECT"}
                or (self.scope == "GLOBAL") != (self.project_id is None)
                or (self.project_id is not None and
                    (type(self.project_id) is not uuid.UUID or not self.project_id.int))
                or type(self.index_purpose) is not str
                or _PURPOSE_REF.fullmatch(self.index_purpose) is None
                or type(self.source_snapshot_fingerprint) is not bytes
                or len(self.source_snapshot_fingerprint) != 32
                or self.index_state != "READY" or self.lock_version != 2):
            raise RAGEmbeddingIndexQualityError()


@dataclass(frozen=True, slots=True)
class RecordedRAGEmbeddingIndexQuality:
    quality_result_id: uuid.UUID
    embedding_index_id: uuid.UUID
    actor_id: uuid.UUID
    dataset_ref: str
    dataset_fingerprint: bytes = field(repr=False)
    dataset_case_count: int
    classification_correct_count: int
    exact_citation_correct_count: int
    classification_basis_points: int
    exact_citation_basis_points: int
    project_isolation_pass: bool
    out_of_scope_citation_count: int
    failure_closure_pass: bool
    quality_state: str
    error_code: str | None
    completed_at: datetime

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.quality_result_id, self.embedding_index_id, self.actor_id))
                or _REF.fullmatch(self.dataset_ref) is None
                or type(self.dataset_fingerprint) is not bytes
                or len(self.dataset_fingerprint) != 32
                or type(self.dataset_case_count) is not int
                or not 50 <= self.dataset_case_count <= 10000
                or any(type(value) is not int or not 0 <= value <= self.dataset_case_count
                       for value in (self.classification_correct_count,
                                     self.exact_citation_correct_count))
                or type(self.classification_basis_points) is not int
                or type(self.exact_citation_basis_points) is not int
                or self.classification_basis_points !=
                   self.classification_correct_count * 10000 // self.dataset_case_count
                or self.exact_citation_basis_points !=
                   self.exact_citation_correct_count * 10000 // self.dataset_case_count
                or type(self.project_isolation_pass) is not bool
                or type(self.out_of_scope_citation_count) is not int
                or not 0 <= self.out_of_scope_citation_count <= self.dataset_case_count
                or type(self.failure_closure_pass) is not bool
                or self.quality_state not in {"PASSED", "FAILED"}
                or (self.quality_state == "PASSED") != (self.error_code is None)
                or (self.quality_state == "PASSED" and not (
                    self.classification_basis_points >= 9000
                    and self.exact_citation_basis_points >= 9800
                    and self.project_isolation_pass
                    and self.out_of_scope_citation_count == 0
                    and self.failure_closure_pass
                ))
                or (self.error_code is not None and self.error_code != _FAILURE)
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise RAGEmbeddingIndexQualityError()


class _Access(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class _Repository(Protocol):
    def locked_target(self, transaction: object, *,
                      embedding_index_id: uuid.UUID,
                      actor_id: uuid.UUID,
                      expected_lock_version: int) -> RAGEmbeddingIndexQualityTarget | None: ...
    def save(self, transaction: object, *,
             target: RAGEmbeddingIndexQualityTarget,
             actor_id: uuid.UUID,
             command: RegisterRAGEmbeddingIndexQuality,
             classification_basis_points: int,
             exact_citation_basis_points: int,
             quality_state: str,
             error_code: str | None) -> RecordedRAGEmbeddingIndexQuality: ...
    def get(self, transaction: object, *, quality_result_id: uuid.UUID,
            embedding_index_id: uuid.UUID,
            actor_id: uuid.UUID) -> RecordedRAGEmbeddingIndexQuality | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class RAGEmbeddingIndexQualityService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: object, repository: _Repository,
                 receipts: _Receipts, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, repository, receipts, audit)):
            raise ValueError("RAG quality dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def register(self, command: RegisterRAGEmbeddingIndexQuality
                 ) -> RecordedRAGEmbeddingIndexQuality:
        now = self._validate(command)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "embedding_index_id": str(command.embedding_index_id),
                "expected_lock_version": command.expected_lock_version,
                "dataset_ref": command.dataset_ref,
                "dataset_fingerprint": command.dataset_fingerprint.hex(),
                "isolation_attestation_fingerprint":
                    command.isolation_attestation_fingerprint.hex(),
                "evaluation_artifact_fingerprint":
                    command.evaluation_artifact_fingerprint.hex(),
                "evaluation_policy_ref": _POLICY,
                "dataset_case_count": command.dataset_case_count,
                "classification_correct_count":
                    command.classification_correct_count,
                "exact_citation_correct_count":
                    command.exact_citation_correct_count,
                "project_isolation_pass": command.project_isolation_pass,
                "out_of_scope_citation_count":
                    command.out_of_scope_citation_count,
                "failure_closure_pass": command.failure_closure_pass,
                "dataset_sealed_at":
                    command.dataset_sealed_at.astimezone(timezone.utc).isoformat(),
            })
        except IdempotencyError:
            raise RAGEmbeddingIndexQualityError("VALIDATION_FAILED") from None
        classification = (command.classification_correct_count * 10000
                          // command.dataset_case_count)
        citation = (command.exact_citation_correct_count * 10000
                    // command.dataset_case_count)
        passed = bool(
            classification >= 9000 and citation >= 9800
            and command.project_isolation_pass
            and command.out_of_scope_citation_count == 0
            and command.failure_closure_pass
        )
        state, error_code = (("PASSED", None) if passed else
                             ("FAILED", _FAILURE))
        try:
            with self._uow() as tx:
                actor = self._require_user(tx, command, now)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_user(tx, command, now)
                target = self._repo.locked_target(
                    tx, embedding_index_id=command.embedding_index_id,
                    actor_id=actor,
                    expected_lock_version=command.expected_lock_version,
                )
                if type(target) is not RAGEmbeddingIndexQualityTarget:
                    raise RAGEmbeddingIndexQualityError("RAG_INDEX_NOT_FOUND")
                target.__post_init__()
                receipt_scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=target.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=receipt_scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 200:
                        raise RAGEmbeddingIndexQualityError()
                    original = self._repo.get(
                        tx, quality_result_id=replay.ref_id,
                        embedding_index_id=command.embedding_index_id,
                        actor_id=actor,
                    )
                    if type(original) is not RecordedRAGEmbeddingIndexQuality:
                        raise RAGEmbeddingIndexQualityError()
                    original.__post_init__()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return original
                result = self._repo.save(
                    tx, target=target, actor_id=actor, command=command,
                    classification_basis_points=classification,
                    exact_citation_basis_points=citation,
                    quality_state=state, error_code=error_code,
                )
                if type(result) is not RecordedRAGEmbeddingIndexQuality:
                    raise RAGEmbeddingIndexQualityError()
                result.__post_init__()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id,
                    event_scope=("DEPLOYMENT" if target.scope == "GLOBAL"
                                 else "PROJECT"),
                    target_project_id=target.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="RAG_INDEX_QUALITY_RECORDED", outcome="SUCCESS",
                    target_owner_module="rag", target_object_type="RAG-03",
                    target_object_id=target.embedding_index_id,
                    target_version_id=result.quality_result_id,
                    before_state="READY",
                    after_state="QUALITY_PASSED" if passed else "QUALITY_FAILED",
                ))
                if type(audit_id) is not uuid.UUID or not audit_id.int:
                    raise RAGEmbeddingIndexQualityError()
                self._receipts.complete(
                    tx, scope=receipt_scope,
                    result=IdempotencyResult(
                        _OPERATION, result.quality_result_id, 200,
                    ),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except RAGEmbeddingIndexQualityError:
            raise
        except RuntimeLicenseError:
            raise RAGEmbeddingIndexQualityError(
                "LICENSE_OPERATION_DENIED",
            ) from None
        except IdempotencyError as error:
            raise RAGEmbeddingIndexQualityError(error.code) from None
        except Exception:
            raise RAGEmbeddingIndexQualityError() from None

    def _validate(self, command: RegisterRAGEmbeddingIndexQuality) -> datetime:
        now = self._clock()
        if type(command) is not RegisterRAGEmbeddingIndexQuality:
            raise RAGEmbeddingIndexQualityError("VALIDATION_FAILED")
        values = (
            command.dataset_fingerprint,
            command.isolation_attestation_fingerprint,
            command.evaluation_artifact_fingerprint,
        )
        if (type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or not command.trace_id.int
                or type(command.embedding_index_id) is not uuid.UUID
                or not command.embedding_index_id.int
                or command.expected_lock_version != 2
                or type(command.dataset_ref) is not str
                or _REF.fullmatch(command.dataset_ref) is None
                or any(type(value) is not bytes or len(value) != 32
                       for value in values)
                or type(command.dataset_case_count) is not int
                or not 50 <= command.dataset_case_count <= 10000
                or any(type(value) is not int
                       or not 0 <= value <= command.dataset_case_count
                       for value in (command.classification_correct_count,
                                     command.exact_citation_correct_count,
                                     command.out_of_scope_citation_count))
                or type(command.project_isolation_pass) is not bool
                or type(command.failure_closure_pass) is not bool
                or not isinstance(command.dataset_sealed_at, datetime)
                or command.dataset_sealed_at.tzinfo is None
                or command.dataset_sealed_at.utcoffset() is None
                or not isinstance(now, datetime)
                or now.tzinfo is None
                or now.utcoffset() is None
                or command.dataset_sealed_at.astimezone(timezone.utc) >= now):
            raise RAGEmbeddingIndexQualityError("VALIDATION_FAILED")
        return now

    def _require_user(self, tx: object,
                      command: RegisterRAGEmbeddingIndexQuality,
                      now: datetime) -> uuid.UUID:
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now,
        )
        if type(actor) is not uuid.UUID or not actor.int:
            raise RAGEmbeddingIndexQualityError("AUTH_ACCESS_DENIED")
        return actor
