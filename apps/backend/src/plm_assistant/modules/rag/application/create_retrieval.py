"""Authorized, ciphertext-only creation of one project RetrievalRun."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
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
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)
from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    EncryptedRetrievalQuery,
    RetrievalQueryCryptoError,
)


_OPERATION = "V1_RAG_RETRIEVAL_CREATE"
_QUERY_POLICY = "fts.project.v1"
_RERANK_POLICY = "none.v1"
_SOURCE_TYPES = frozenset({
    "CONTRACTUAL", "PROJECT_RECORD", "STANDARD_CAPABILITY",
    "REFERENCE_MATERIAL", "TEMPLATE", "GENERATED_ARTIFACT", "OTHER",
})
_FILTER_KEYS = frozenset({
    "document_category", "source_type", "document_version_ref",
    "effective_from", "effective_to", "business",
})


class RAGRetrievalCreateError(RuntimeError):
    def __init__(self, code: str = "RAG_RETRIEVAL_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateProjectRetrieval:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    query: str = field(repr=False)
    metadata_filter: dict = field(repr=False)
    project_index_ref: uuid.UUID
    global_index_ref: uuid.UUID | None
    retrieval_policy_ref: str
    rerank_policy_ref: str
    top_k: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RAGRetrievalCreateTarget:
    project_id: uuid.UUID
    project_index_ref: uuid.UUID
    project_model_ref: uuid.UUID
    global_index_ref: uuid.UUID | None
    global_model_ref: uuid.UUID | None

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.project_id, self.project_index_ref, self.project_model_ref))
                or (self.global_index_ref is None) != (self.global_model_ref is None)
                or any(type(value) is not uuid.UUID or not value.int
                       for value in (self.global_index_ref, self.global_model_ref)
                       if value is not None)):
            raise RAGRetrievalCreateError()


@dataclass(frozen=True, slots=True)
class RAGRetrievalPersistenceRequest:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    query_fingerprint: bytes = field(repr=False)
    metadata_filter: dict = field(repr=False)
    metadata_filter_fingerprint: bytes = field(repr=False)
    target: RAGRetrievalCreateTarget
    retrieval_policy_ref: str
    rerank_policy_ref: str
    top_k: int
    encrypted_query: EncryptedRetrievalQuery = field(repr=False)


@dataclass(frozen=True, slots=True)
class CreatedProjectRetrieval:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    query_fingerprint: bytes = field(repr=False)
    retrieval_state: str = "RUNNING"

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.retrieval_run_id, self.job_id, self.project_id))
                or type(self.query_fingerprint) is not bytes
                or len(self.query_fingerprint) != 32
                or self.retrieval_state != "RUNNING"):
            raise RAGRetrievalCreateError()


class _Access(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class _Cipher(Protocol):
    def encrypt(self, *, retrieval_run_id: uuid.UUID, project_id: uuid.UUID,
                query_fingerprint: bytes, plaintext: bytearray,
                retention_until: datetime) -> EncryptedRetrievalQuery: ...


class _Repository(Protocol):
    def locked_target(self, transaction: object, *, project_id: uuid.UUID,
                      project_index_ref: uuid.UUID,
                      global_index_ref: uuid.UUID | None
                      ) -> RAGRetrievalCreateTarget | None: ...
    def create(self, transaction: object, *, request: RAGRetrievalPersistenceRequest
               ) -> CreatedProjectRetrieval: ...
    def replay(self, transaction: object, *, retrieval_run_id: uuid.UUID,
               project_id: uuid.UUID,
               actor_id: uuid.UUID) -> CreatedProjectRetrieval | None: ...


class _Receipts(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


def normalize_retrieval_query(value: str) -> str:
    if type(value) is not str:
        raise RAGRetrievalCreateError("VALIDATION_FAILED")
    normalized = " ".join(unicodedata.normalize("NFKC", value).split())
    encoded = normalized.encode("utf-8")
    if not 1 <= len(normalized) <= 4096 or not 1 <= len(encoded) <= 16384:
        raise RAGRetrievalCreateError("VALIDATION_FAILED")
    return normalized


def normalize_retrieval_filter(value: dict) -> dict:
    if type(value) is not dict or len(value) > len(_FILTER_KEYS):
        raise RAGRetrievalCreateError("VALIDATION_FAILED")
    if set(value) - _FILTER_KEYS:
        raise RAGRetrievalCreateError("VALIDATION_FAILED")
    result: dict[str, object] = {}
    categories = value.get("document_category")
    if categories is not None:
        if (type(categories) is not list or not 1 <= len(categories) <= 32
                or any(type(item) is not str or not 1 <= len(item) <= 64
                       or item != item.strip() for item in categories)):
            raise RAGRetrievalCreateError("VALIDATION_FAILED")
        result["document_category"] = sorted(set(categories))
    source_types = value.get("source_type")
    if source_types is not None:
        if (type(source_types) is not list or not 1 <= len(source_types) <= 7
                or any(item not in _SOURCE_TYPES for item in source_types)):
            raise RAGRetrievalCreateError("VALIDATION_FAILED")
        result["source_type"] = sorted(set(source_types))
    version = value.get("document_version_ref")
    if version is not None:
        try:
            parsed = uuid.UUID(version) if type(version) is str else None
        except ValueError:
            parsed = None
        if parsed is None or not parsed.int:
            raise RAGRetrievalCreateError("VALIDATION_FAILED")
        result["document_version_ref"] = str(parsed)
    for key in ("effective_from", "effective_to"):
        raw = value.get(key)
        if raw is not None:
            try:
                parsed_date = date.fromisoformat(raw) if type(raw) is str else None
            except ValueError:
                parsed_date = None
            if parsed_date is None or parsed_date.isoformat() != raw:
                raise RAGRetrievalCreateError("VALIDATION_FAILED")
            result[key] = raw
    if ("effective_from" in result and "effective_to" in result
            and result["effective_from"] > result["effective_to"]):
        raise RAGRetrievalCreateError("VALIDATION_FAILED")
    business = value.get("business")
    if business is not None:
        if type(business) is not dict or business:
            raise RAGRetrievalCreateError("RAG_METADATA_FILTER_NOT_ALLOWED")
        result["business"] = {}
    return result


class RAGRetrievalCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: _Access,
                 license_guard: object,
                 authorization: ProjectAuthorizationService,
                 cipher: _Cipher, repository: _Repository,
                 receipts: _Receipts, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, license_guard, authorization, cipher,
                repository, receipts, audit)):
            raise ValueError("RAG Retrieval create dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._cipher = authorization, cipher
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateProjectRetrieval) -> CreatedProjectRetrieval:
        now, query, metadata_filter = self._validate(command)
        query_bytes = bytearray(query.encode("utf-8"))
        try:
            run_id = uuid.UUID(new_uuid7())
            query_fingerprint = canonical_payload_fingerprint({
                "domain": "rag-query-v1", "query": query,
            })
            filter_fingerprint = canonical_payload_fingerprint(metadata_filter)
            validate_idempotency_key(command.idempotency_key)
            request_fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "query_fingerprint": query_fingerprint.hex(),
                "metadata_filter": metadata_filter,
                "metadata_filter_fingerprint": filter_fingerprint.hex(),
                "project_index_ref": str(command.project_index_ref),
                "global_index_ref": (str(command.global_index_ref)
                                     if command.global_index_ref else None),
                "retrieval_policy_ref": command.retrieval_policy_ref,
                "rerank_policy_ref": command.rerank_policy_ref,
                "top_k": command.top_k,
            })
            with self._uow() as tx:
                actor = self._actor(tx, command, now)
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="RAG_RETRIEVAL_CREATE",
                )
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command, now)
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="RAG_RETRIEVAL_CREATE",
                )
                target = self._repo.locked_target(
                    tx, project_id=command.project_id,
                    project_index_ref=command.project_index_ref,
                    global_index_ref=command.global_index_ref,
                )
                if type(target) is not RAGRetrievalCreateTarget:
                    raise RAGRetrievalCreateError("RAG_ACTIVE_INDEX_NOT_FOUND")
                target.__post_init__()
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=_OPERATION, key=command.idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=request_fingerprint)
                if replay is not None:
                    if replay.ref_type != _OPERATION or replay.status_code != 202:
                        raise RAGRetrievalCreateError()
                    result = self._repo.replay(
                        tx, retrieval_run_id=replay.ref_id,
                        project_id=command.project_id, actor_id=actor)
                    if type(result) is not CreatedProjectRetrieval:
                        raise RAGRetrievalCreateError()
                    result.__post_init__()
                    self._guard.require_valid(trace_id=command.trace_id)
                    return result
                encrypted = self._cipher.encrypt(
                    retrieval_run_id=run_id, project_id=command.project_id,
                    query_fingerprint=query_fingerprint, plaintext=query_bytes,
                    retention_until=now + timedelta(days=180),
                )
                request = RAGRetrievalPersistenceRequest(
                    run_id, command.project_id, actor, command.trace_id,
                    query_fingerprint, metadata_filter, filter_fingerprint,
                    target, command.retrieval_policy_ref,
                    command.rerank_policy_ref, command.top_k, encrypted,
                )
                result = self._repo.create(tx, request=request)
                if type(result) is not CreatedProjectRetrieval:
                    raise RAGRetrievalCreateError()
                result.__post_init__()
                audit_id = self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="RAG_RETRIEVAL_CREATED", outcome="SUCCESS",
                    target_owner_module="rag", target_object_type="RAG-04",
                    target_object_id=result.retrieval_run_id,
                    after_state="RUNNING",
                ))
                if type(audit_id) is not uuid.UUID or not audit_id.int:
                    raise RAGRetrievalCreateError()
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(
                        _OPERATION, result.retrieval_run_id, 202),
                )
                self._guard.require_valid(trace_id=command.trace_id)
                tx.commit()
                return result
        except RAGRetrievalCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise RAGRetrievalCreateError(error.code) from None
        except RuntimeLicenseError:
            raise RAGRetrievalCreateError("LICENSE_OPERATION_DENIED") from None
        except (IdempotencyError, RetrievalQueryCryptoError) as error:
            code = getattr(error, "code", "RAG_QUERY_ENCRYPTION_UNAVAILABLE")
            raise RAGRetrievalCreateError(code) from None
        except Exception:
            raise RAGRetrievalCreateError() from None
        finally:
            query_bytes[:] = b"\x00" * len(query_bytes)

    def _validate(self, command: CreateProjectRetrieval
                  ) -> tuple[datetime, str, dict]:
        now = self._clock()
        if (type(command) is not CreateProjectRetrieval
                or type(command.session_token) is not bytes
                or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes
                or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID
                or not command.trace_id.int
                or type(command.project_id) is not uuid.UUID
                or not command.project_id.int
                or type(command.project_index_ref) is not uuid.UUID
                or not command.project_index_ref.int
                or command.global_index_ref is not None
                or command.retrieval_policy_ref != _QUERY_POLICY
                or command.rerank_policy_ref != _RERANK_POLICY
                or type(command.top_k) is not int or not 1 <= command.top_k <= 100
                or not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None):
            raise RAGRetrievalCreateError("VALIDATION_FAILED")
        return now.astimezone(timezone.utc), normalize_retrieval_query(command.query), \
            normalize_retrieval_filter(command.metadata_filter)

    def _actor(self, tx: object, command: CreateProjectRetrieval,
               now: datetime) -> uuid.UUID:
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now)
        if type(actor) is not uuid.UUID or not actor.int:
            raise RAGRetrievalCreateError("AUTH_ACCESS_DENIED")
        return actor
