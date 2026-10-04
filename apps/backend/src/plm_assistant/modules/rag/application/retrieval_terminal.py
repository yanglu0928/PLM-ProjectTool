"""Atomic Retrieval publication and expired-generation reconciliation."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.rag_retrieval_claim import (
    RAGRetrievalClaim,
    RAGRetrievalClaims,
)

from .fts_retrieval_merge import FTSRetrievalMergePlan
from .prepare_retrieval_query import PreparedRAGRetrieval


_ERRORS = frozenset({
    "RAG_NO_AUTHORIZED_CANDIDATES",
    "RAG_RETRIEVAL_PREPARATION_UNAVAILABLE",
    "RAG_RETRIEVAL_LEASE_EXPIRED",
})


class RAGRetrievalTerminalError(RuntimeError):
    def __init__(self, code: str = "RAG_RETRIEVAL_TERMINAL_UNAVAILABLE", *,
                 committed: bool = False) -> None:
        if type(committed) is not bool:
            raise ValueError("committed must be bool")
        self.code = code
        self.committed = committed
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PublishedRAGRetrievalTerminal:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    state: str
    candidate_count: int
    context_bundle_id: uuid.UUID | None
    context_bundle_fingerprint: bytes | None
    error_code: str | None
    completed_at: datetime

    def __post_init__(self) -> None:
        ids = (
            self.retrieval_run_id, self.job_id, self.project_id,
            self.requested_by, self.trace_id,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in ids)
                or self.state not in {"SUCCEEDED", "FAILED"}
                or type(self.candidate_count) is not int
                or not 0 <= self.candidate_count <= 100
                or not isinstance(self.completed_at, datetime)
                or self.completed_at.tzinfo is None
                or self.completed_at.utcoffset() is None):
            raise RAGRetrievalTerminalError()
        if self.state == "SUCCEEDED":
            if (self.candidate_count < 1
                    or type(self.context_bundle_id) is not uuid.UUID
                    or not self.context_bundle_id.int
                    or type(self.context_bundle_fingerprint) is not bytes
                    or len(self.context_bundle_fingerprint) != 32
                    or self.error_code is not None):
                raise RAGRetrievalTerminalError()
        elif (self.candidate_count != 0
              or self.context_bundle_id is not None
              or self.context_bundle_fingerprint is not None
              or self.error_code not in _ERRORS):
            raise RAGRetrievalTerminalError()


class RAGRetrievalTerminalRepositoryPort(Protocol):
    def publish_success(
        self, transaction: object, *, claim: RAGRetrievalClaim,
        prepared: PreparedRAGRetrieval, plan: FTSRetrievalMergePlan,
        worker_ref: str,
    ) -> PublishedRAGRetrievalTerminal: ...

    def publish_failure(
        self, transaction: object, *, claim: RAGRetrievalClaim,
        worker_ref: str, error_code: str,
    ) -> PublishedRAGRetrievalTerminal: ...

    def reconcile_expired_next(
        self, transaction: object,
    ) -> PublishedRAGRetrievalTerminal | None: ...


class _SystemActor(Protocol):
    def assert_current(self) -> uuid.UUID: ...


class RAGRetrievalTerminalService:
    """Publish terminal state with an Audit event in the same transaction."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 claims: RAGRetrievalClaims,
                 repository: RAGRetrievalTerminalRepositoryPort,
                 audit: AuditService, system_actor: _SystemActor) -> None:
        if any(value is None for value in (
                unit_of_work, claims, repository, audit, system_actor)):
            raise ValueError("RAG Retrieval terminal dependencies required")
        self._uow = unit_of_work
        self._claims = claims
        self._repository = repository
        self._audit = audit
        self._actor = system_actor

    def publish_success_in_transaction(
        self, transaction: object, *, job_id: uuid.UUID, fencing_token: int,
        worker_ref: str, prepared: PreparedRAGRetrieval,
        plan: FTSRetrievalMergePlan,
    ) -> PublishedRAGRetrievalTerminal:
        actor_id = self._system_actor()
        try:
            claim = self._claims.check_current(
                transaction, job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref,
            )
            result = self._repository.publish_success(
                transaction, claim=claim, prepared=prepared,
                plan=plan, worker_ref=worker_ref,
            )
            self._validate_result(result, claim, "SUCCEEDED", None)
            self._append_audit(transaction, result, actor_id)
            if self._actor.assert_current() != actor_id:
                raise RAGRetrievalTerminalError("SYSTEM_ACTOR_UNAVAILABLE")
            return result
        except RAGRetrievalTerminalError:
            raise
        except Exception:
            raise RAGRetrievalTerminalError() from None

    def publish_failure(
        self, *, job_id: uuid.UUID, fencing_token: int,
        worker_ref: str, error_code: str,
    ) -> PublishedRAGRetrievalTerminal:
        if error_code not in _ERRORS - {"RAG_RETRIEVAL_LEASE_EXPIRED"}:
            raise RAGRetrievalTerminalError("VALIDATION_FAILED")
        committed = False
        actor_id = self._system_actor()
        try:
            with self._uow() as transaction:
                claim = self._claims.check_current(
                    transaction, job_id=job_id, fencing_token=fencing_token,
                    worker_ref=worker_ref,
                )
                result = self._repository.publish_failure(
                    transaction, claim=claim, worker_ref=worker_ref,
                    error_code=error_code,
                )
                self._validate_result(result, claim, "FAILED", error_code)
                self._append_audit(transaction, result, actor_id)
                if self._actor.assert_current() != actor_id:
                    raise RAGRetrievalTerminalError("SYSTEM_ACTOR_UNAVAILABLE")
                transaction.commit()
                committed = True
            return result
        except RAGRetrievalTerminalError as error:
            if committed and not error.committed:
                raise RAGRetrievalTerminalError(error.code, committed=True) from None
            raise
        except Exception:
            raise RAGRetrievalTerminalError(committed=committed) from None

    def reconcile_expired_next(self) -> PublishedRAGRetrievalTerminal | None:
        committed = False
        actor_id = self._system_actor()
        try:
            with self._uow() as transaction:
                result = self._repository.reconcile_expired_next(transaction)
                if result is None:
                    return None
                result.__post_init__()
                if (result.state != "FAILED"
                        or result.error_code != "RAG_RETRIEVAL_LEASE_EXPIRED"):
                    raise RAGRetrievalTerminalError()
                self._append_audit(transaction, result, actor_id)
                if self._actor.assert_current() != actor_id:
                    raise RAGRetrievalTerminalError("SYSTEM_ACTOR_UNAVAILABLE")
                transaction.commit()
                committed = True
            return result
        except RAGRetrievalTerminalError as error:
            if committed and not error.committed:
                raise RAGRetrievalTerminalError(error.code, committed=True) from None
            raise
        except Exception:
            raise RAGRetrievalTerminalError(committed=committed) from None

    def _system_actor(self) -> uuid.UUID:
        actor_id = self._actor.assert_current()
        if type(actor_id) is not uuid.UUID or not actor_id.int:
            raise RAGRetrievalTerminalError("SYSTEM_ACTOR_UNAVAILABLE")
        return actor_id

    @staticmethod
    def _validate_result(result: object, claim: RAGRetrievalClaim,
                         state: str, error_code: str | None) -> None:
        if type(result) is not PublishedRAGRetrievalTerminal:
            raise RAGRetrievalTerminalError()
        result.__post_init__()
        if ((result.retrieval_run_id, result.job_id, result.project_id,
             result.requested_by, result.trace_id, result.state,
             result.error_code) !=
                (claim.retrieval_run_id, claim.job_id, claim.project_id,
                 claim.actor_id, claim.trace_id, state, error_code)):
            raise RAGRetrievalTerminalError()

    def _append_audit(self, transaction: object,
                      result: PublishedRAGRetrievalTerminal,
                      actor_id: uuid.UUID) -> None:
        event_id = self._audit.append(transaction, AuditEventDraft(
            trace_id=result.trace_id,
            event_scope="PROJECT",
            target_project_id=result.project_id,
            actor_type="SYSTEM",
            actor_id=actor_id,
            original_actor_id=result.requested_by,
            actor_hint_digest=None,
            action=("RAG_RETRIEVAL_COMPLETED" if result.state == "SUCCEEDED"
                    else "RAG_RETRIEVAL_FAILED"),
            outcome=("SUCCESS" if result.state == "SUCCEEDED" else "FAILED"),
            target_owner_module="rag",
            target_object_type="RAG-04",
            target_object_id=result.retrieval_run_id,
            target_version_id=result.context_bundle_id,
            reason_code=result.error_code,
            before_state="RUNNING",
            after_state=result.state,
        ))
        if type(event_id) is not uuid.UUID or not event_id.int:
            raise RAGRetrievalTerminalError()


def context_bundle_fingerprint(
    *, retrieval_run_id: uuid.UUID, project_id: uuid.UUID,
    item_facts: tuple[tuple[int, uuid.UUID, uuid.UUID, bytes, bytes], ...],
) -> bytes:
    """Fingerprint Context identities and snippets without copying their text."""

    if (type(retrieval_run_id) is not uuid.UUID or not retrieval_run_id.int
            or type(project_id) is not uuid.UUID or not project_id.int
            or type(item_facts) is not tuple or not item_facts):
        raise RAGRetrievalTerminalError()
    payload = []
    for expected, fact in enumerate(item_facts):
        if (type(fact) is not tuple or len(fact) != 5
                or fact[0] != expected
                or any(type(value) is not uuid.UUID or not value.int
                       for value in fact[1:3])
                or any(type(value) is not bytes or len(value) != 32
                       for value in fact[3:])):
            raise RAGRetrievalTerminalError()
        payload.append({
            "ordinal": fact[0], "candidate_id": str(fact[1]),
            "chunk_id": str(fact[2]), "snippet_fingerprint": fact[3].hex(),
            "access_snapshot_fingerprint": fact[4].hex(),
        })
    encoded = json.dumps({
        "schema_version": "rag-context-bundle.v1",
        "retrieval_run_id": str(retrieval_run_id),
        "project_id": str(project_id), "items": payload,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
       allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).digest()


def require_terminal_error_code(value: str) -> str:
    if (value not in _ERRORS
            or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", value) is None):
        raise RAGRetrievalTerminalError("VALIDATION_FAILED")
    return value
