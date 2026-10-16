"""Current-fact validation and bounded plaintext use for one Retrieval claim."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, TypeVar

from plm_assistant.modules.jobs.application.rag_retrieval_claim import (
    RAGRetrievalClaim,
    RAGRetrievalClaims,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    canonical_payload_fingerprint,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)
from plm_assistant.modules.rag.application.create_retrieval import (
    normalize_retrieval_filter,
    normalize_retrieval_query,
)
from plm_assistant.modules.rag.application.retrieval_query_crypto import (
    RetrievalQueryCryptoError,
    RetrievalQueryEnvelope,
)


T = TypeVar("T")


class RAGRetrievalPreparationError(RuntimeError):
    def __init__(self, code: str = "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RAGRetrievalExecutionTarget:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    project_index_ref: uuid.UUID
    project_model_ref: uuid.UUID
    index_version: int
    index_lock_version: int
    source_chunk_count: int
    source_snapshot_fingerprint: bytes = field(repr=False)
    metadata_filter: dict = field(repr=False)
    metadata_filter_fingerprint: bytes = field(repr=False)
    retrieval_policy_ref: str
    rerank_policy_ref: str
    top_k: int
    query: RetrievalQueryEnvelope = field(repr=False)

    def __post_init__(self) -> None:
        required = (
            self.retrieval_run_id, self.job_id, self.project_id, self.actor_id,
            self.trace_id, self.project_index_ref, self.project_model_ref,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in required)
                or type(self.index_version) is not int or self.index_version < 1
                or type(self.index_lock_version) is not int or self.index_lock_version < 0
                or type(self.source_chunk_count) is not int
                or self.source_chunk_count < 1
                or type(self.source_snapshot_fingerprint) is not bytes
                or len(self.source_snapshot_fingerprint) != 32
                or type(self.metadata_filter) is not dict
                or type(self.metadata_filter_fingerprint) is not bytes
                or len(self.metadata_filter_fingerprint) != 32
                or self.retrieval_policy_ref != "fts.project.v1"
                or self.rerank_policy_ref != "none.v1"
                or type(self.top_k) is not int or not 1 <= self.top_k <= 100
                or type(self.query) is not RetrievalQueryEnvelope):
            raise RAGRetrievalPreparationError()


@dataclass(frozen=True, slots=True)
class PreparedRAGRetrieval:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    project_index_ref: uuid.UUID
    project_model_ref: uuid.UUID
    metadata_filter: dict = field(repr=False)
    retrieval_policy_ref: str
    top_k: int
    authorization_snapshot_fingerprint: bytes = field(repr=False)
    query_fingerprint: bytes = field(repr=False)
    query_utf8: bytearray = field(repr=False)

    def __post_init__(self) -> None:
        required = (
            self.retrieval_run_id, self.job_id, self.project_id, self.actor_id,
            self.trace_id, self.project_index_ref, self.project_model_ref,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in required)
                or type(self.metadata_filter) is not dict
                or self.retrieval_policy_ref != "fts.project.v1"
                or type(self.top_k) is not int or not 1 <= self.top_k <= 100
                or type(self.authorization_snapshot_fingerprint) is not bytes
                or len(self.authorization_snapshot_fingerprint) != 32
                or type(self.query_fingerprint) is not bytes
                or len(self.query_fingerprint) != 32
                or type(self.query_utf8) is not bytearray
                or not 1 <= len(self.query_utf8) <= 16384):
            raise RAGRetrievalPreparationError()


class _Repository(Protocol):
    def actor_enabled(self, transaction: object, *, actor_id: uuid.UUID) -> bool: ...
    def locked_target(self, transaction: object, *, claim: RAGRetrievalClaim,
                      now: datetime) -> RAGRetrievalExecutionTarget | None: ...


class _Cipher(Protocol):
    def decrypt(self, envelope: RetrievalQueryEnvelope) -> bytearray: ...


class RAGRetrievalQueryPreparationService:
    """Keep plaintext inside one authorized callback and always zero its buffer."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGRetrievalClaims, license_guard: object,
                 authorization: ProjectAuthorizationService,
                 repository: _Repository, cipher: _Cipher,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, claims, license_guard, authorization,
                repository, cipher)):
            raise ValueError("RAG Retrieval preparation dependencies required")
        self._uow, self._claims, self._guard = unit_of_work, claims, license_guard
        self._authorization, self._repo, self._cipher = authorization, repository, cipher
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def consume_current_query(
        self, *, job_id: uuid.UUID, fencing_token: int, worker_ref: str,
        consumer: Callable[[object, PreparedRAGRetrieval], T],
    ) -> T:
        now = self._now()
        if consumer is None or not callable(consumer):
            raise RAGRetrievalPreparationError("VALIDATION_FAILED")
        plaintext: bytearray | None = None
        try:
            with self._uow() as tx:
                claim = self._claims.check_current(
                    tx, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                role = self._authorize(tx, claim)
            self._guard.require_valid(trace_id=claim.trace_id)
            with self._uow() as tx:
                current = self._claims.check_current(
                    tx, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                current_role = self._authorize(tx, current)
                if current_role != role:
                    raise RAGRetrievalPreparationError("RAG_RETRIEVAL_AUTHORIZATION_CHANGED")
                target = self._repo.locked_target(tx, claim=current, now=now)
                if type(target) is not RAGRetrievalExecutionTarget:
                    raise RAGRetrievalPreparationError()
                target.__post_init__()
                self._validate_target(current, target)
                plaintext = self._cipher.decrypt(target.query)
                prepared = self._prepared(target, current_role, plaintext)
                result = consumer(tx, prepared)
                self._guard.require_valid(trace_id=current.trace_id)
                tx.commit()
                return result
        except RAGRetrievalPreparationError:
            raise
        except ProjectAuthorizationError as error:
            raise RAGRetrievalPreparationError(error.code) from None
        except RuntimeLicenseError:
            raise RAGRetrievalPreparationError("LICENSE_OPERATION_DENIED") from None
        except RetrievalQueryCryptoError:
            raise RAGRetrievalPreparationError("RAG_QUERY_DECRYPTION_UNAVAILABLE") from None
        except UnicodeDecodeError:
            raise RAGRetrievalPreparationError("RAG_QUERY_DECRYPTION_UNAVAILABLE") from None
        except Exception:
            raise RAGRetrievalPreparationError() from None
        finally:
            if plaintext is not None:
                plaintext[:] = b"\x00" * len(plaintext)

    def _authorize(self, tx: object, claim: RAGRetrievalClaim) -> str:
        if not self._repo.actor_enabled(tx, actor_id=claim.actor_id):
            raise RAGRetrievalPreparationError("RESOURCE_NOT_FOUND")
        action = self._authorization.require_in_transaction(
            tx, user_id=claim.actor_id, project_id=claim.project_id,
            operation="RAG_RETRIEVAL_EXECUTE",
        )
        return action.project_role

    @staticmethod
    def _validate_target(claim: RAGRetrievalClaim,
                         target: RAGRetrievalExecutionTarget) -> None:
        if ((target.job_id, target.retrieval_run_id, target.project_id,
             target.actor_id, target.trace_id) !=
                (claim.job_id, claim.retrieval_run_id, claim.project_id,
                 claim.actor_id, claim.trace_id)
                or target.query.retrieval_run_id != target.retrieval_run_id
                or target.query.project_id != target.project_id
                or normalize_retrieval_filter(target.metadata_filter)
                != target.metadata_filter
                or not hmac.compare_digest(
                    canonical_payload_fingerprint(target.metadata_filter),
                    target.metadata_filter_fingerprint,
                )):
            raise RAGRetrievalPreparationError()

    @staticmethod
    def _prepared(target: RAGRetrievalExecutionTarget, role: str,
                  plaintext: bytearray) -> PreparedRAGRetrieval:
        decoded = plaintext.decode("utf-8", errors="strict")
        normalized = normalize_retrieval_query(decoded)
        if normalized.encode("utf-8") != bytes(plaintext):
            raise RAGRetrievalPreparationError("RAG_QUERY_DECRYPTION_UNAVAILABLE")
        query_fingerprint = canonical_payload_fingerprint({
            "domain": "rag-query-v1", "query": normalized,
        })
        if not hmac.compare_digest(query_fingerprint, target.query.query_fingerprint):
            raise RAGRetrievalPreparationError("RAG_QUERY_DECRYPTION_UNAVAILABLE")
        authorization_fingerprint = canonical_payload_fingerprint({
            "domain": "rag-retrieval-authorization-v1",
            "retrieval_run_id": str(target.retrieval_run_id),
            "project_id": str(target.project_id),
            "actor_id": str(target.actor_id),
            "project_role": role,
            "project_index_ref": str(target.project_index_ref),
            "project_model_ref": str(target.project_model_ref),
            "index_version": target.index_version,
            "index_lock_version": target.index_lock_version,
            "source_chunk_count": target.source_chunk_count,
            "source_snapshot_fingerprint": target.source_snapshot_fingerprint.hex(),
            "metadata_filter_fingerprint": target.metadata_filter_fingerprint.hex(),
            "retrieval_policy_ref": target.retrieval_policy_ref,
            "top_k": target.top_k,
        })
        return PreparedRAGRetrieval(
            target.retrieval_run_id, target.job_id, target.project_id,
            target.actor_id, target.trace_id, target.project_index_ref,
            target.project_model_ref, dict(target.metadata_filter),
            target.retrieval_policy_ref, target.top_k,
            authorization_fingerprint, query_fingerprint, plaintext,
        )

    def _now(self) -> datetime:
        try:
            now = self._clock()
        except Exception:
            raise RAGRetrievalPreparationError("VALIDATION_FAILED") from None
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise RAGRetrievalPreparationError("VALIDATION_FAILED")
        return now.astimezone(timezone.utc)
