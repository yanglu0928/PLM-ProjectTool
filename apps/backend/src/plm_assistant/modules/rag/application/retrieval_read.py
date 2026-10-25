"""Current-authority safe reads for one project RAG RetrievalRun."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.project.application.authorization import (
    AuthorizedProjectAction,
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


_RUN_STATES = frozenset({"RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"})
_RERANK_STATES = frozenset({"PENDING", "NOT_APPLICABLE"})
_EGRESS_STATES = frozenset({"PENDING", "NOT_APPLICABLE"})
_OVERSIGHT_ROLES = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


class RAGRetrievalReadError(RuntimeError):
    def __init__(self, code: str = "RAG_RETRIEVAL_READ_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _time(value: object) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


def _digest(value: object) -> bool:
    return type(value) is bytes and len(value) == 32


def _locator(value: object) -> bool:
    return (type(value) is dict and type(value.get("locator_type")) is str
            and bool(value["locator_type"]))


@dataclass(frozen=True, slots=True)
class GetRAGRetrieval:
    session_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    retrieval_run_id: uuid.UUID

    def __post_init__(self) -> None:
        if (type(self.session_token) is not bytes or len(self.session_token) != 32
                or not all(_id(value) for value in (
                    self.trace_id, self.project_id, self.retrieval_run_id,
                ))):
            raise RAGRetrievalReadError("VALIDATION_FAILED")


@dataclass(frozen=True, slots=True)
class RAGRetrievalRunView:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    global_index_ref: uuid.UUID | None
    project_index_ref: uuid.UUID
    retrieval_policy_ref: str
    rerank_policy_ref: str
    top_k: int
    rerank_state: str
    egress_state: str
    retrieval_state: str
    quality_flags: tuple[str, ...]
    degraded: bool
    error_code: str | None
    job_id: uuid.UUID
    trace_id: uuid.UUID
    lock_version: int
    created_at: datetime
    completed_at: datetime | None

    def __post_init__(self) -> None:
        optional_ids = (self.global_index_ref,)
        if (not all(_id(value) for value in (
                self.retrieval_run_id, self.project_id, self.requested_by,
                self.project_index_ref, self.job_id, self.trace_id,
            ))
                or any(value is not None and not _id(value) for value in optional_ids)
                or type(self.retrieval_policy_ref) is not str
                or not self.retrieval_policy_ref
                or type(self.rerank_policy_ref) is not str
                or not self.rerank_policy_ref
                or type(self.top_k) is not int or not 1 <= self.top_k <= 100
                or self.rerank_state not in _RERANK_STATES
                or self.egress_state not in _EGRESS_STATES
                or self.retrieval_state not in _RUN_STATES
                or type(self.quality_flags) is not tuple
                or any(type(item) is not str or not item for item in self.quality_flags)
                or len(set(self.quality_flags)) != len(self.quality_flags)
                or type(self.degraded) is not bool
                or self.error_code is not None and (
                    type(self.error_code) is not str or not self.error_code)
                or type(self.lock_version) is not int or self.lock_version < 0
                or not _time(self.created_at)
                or self.completed_at is not None and not _time(self.completed_at)):
            raise RAGRetrievalReadError()


@dataclass(frozen=True, slots=True)
class RAGRetrievalScorePartView:
    score_kind: str
    score_ordinal: int
    raw_score_micros: int
    normalized_score_micros: int
    weight_micros: int
    weighted_score_micros: int
    score_policy_ref: str

    def __post_init__(self) -> None:
        if (self.score_kind not in {
                "FTS", "VECTOR", "METADATA", "SOURCE_WEIGHT", "RERANK", "FINAL",
            }
                or type(self.score_ordinal) is not int
                or not 0 <= self.score_ordinal <= 31
                or any(type(value) is not int for value in (
                    self.raw_score_micros, self.normalized_score_micros,
                    self.weight_micros, self.weighted_score_micros,
                ))
                or not -1_000_000_000 <= self.raw_score_micros <= 1_000_000_000
                or not 0 <= self.normalized_score_micros <= 1_000_000
                or not 0 <= self.weight_micros <= 1_000_000
                or not -1_000_000_000 <= self.weighted_score_micros <= 1_000_000_000
                or type(self.score_policy_ref) is not str
                or not self.score_policy_ref):
            raise RAGRetrievalReadError()


@dataclass(frozen=True, slots=True)
class RAGRetrievalCandidateView:
    candidate_id: uuid.UUID
    rank: int
    chunk_id: uuid.UUID
    document_version_ref: uuid.UUID
    parse_result_ref: uuid.UUID
    source_type: str
    source_locator: dict[str, object]
    retrieval_channel: str
    final_score_micros: int
    score_parts: tuple[RAGRetrievalScorePartView, ...]
    snippet: str = field(repr=False)

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.candidate_id, self.chunk_id, self.document_version_ref,
                self.parse_result_ref,
            ))
                or type(self.rank) is not int or not 0 <= self.rank <= 9999
                or type(self.source_type) is not str or not self.source_type
                or not _locator(self.source_locator)
                or self.retrieval_channel not in {"FTS", "VECTOR", "HYBRID", "EXACT"}
                or type(self.final_score_micros) is not int
                or not -1_000_000_000 <= self.final_score_micros <= 1_000_000_000
                or type(self.score_parts) is not tuple or not self.score_parts
                or any(type(item) is not RAGRetrievalScorePartView
                       for item in self.score_parts)
                or type(self.snippet) is not str or not self.snippet
                or len(self.snippet) > 8192):
            raise RAGRetrievalReadError()
        for part in self.score_parts:
            part.__post_init__()


@dataclass(frozen=True, slots=True)
class RAGRetrievalResultView:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    candidates: tuple[RAGRetrievalCandidateView, ...]
    quality_flags: tuple[str, ...]
    degraded: bool
    completed_at: datetime

    def __post_init__(self) -> None:
        if (not _id(self.retrieval_run_id) or not _id(self.project_id)
                or type(self.candidates) is not tuple or not self.candidates
                or len(self.candidates) > 100
                or any(type(item) is not RAGRetrievalCandidateView
                       for item in self.candidates)
                or tuple(item.rank for item in self.candidates)
                   != tuple(range(len(self.candidates)))
                or len({item.candidate_id for item in self.candidates})
                   != len(self.candidates)
                or type(self.quality_flags) is not tuple
                or type(self.degraded) is not bool or not _time(self.completed_at)):
            raise RAGRetrievalReadError()
        for item in self.candidates:
            item.__post_init__()


@dataclass(frozen=True, slots=True)
class RAGContextItemView:
    ordinal: int
    chunk_id: uuid.UUID
    document_version_ref: uuid.UUID
    source_locator: dict[str, object]
    snippet_start: int
    snippet_end: int
    token_count: int
    snippet: str = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.ordinal) is not int or not 0 <= self.ordinal <= 99
                or not _id(self.chunk_id) or not _id(self.document_version_ref)
                or not _locator(self.source_locator)
                or type(self.snippet_start) is not int or self.snippet_start < 0
                or type(self.snippet_end) is not int
                or self.snippet_end <= self.snippet_start
                or self.snippet_end - self.snippet_start > 8192
                or type(self.token_count) is not int or not 1 <= self.token_count <= 16384
                or type(self.snippet) is not str or not self.snippet
                or len(self.snippet) != self.snippet_end - self.snippet_start):
            raise RAGRetrievalReadError()


@dataclass(frozen=True, slots=True)
class RAGContextBundleView:
    context_bundle_id: uuid.UUID
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    context_policy_ref: str
    bundle_fingerprint: bytes = field(repr=False)
    token_budget: int
    token_count: int
    items: tuple[RAGContextItemView, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.context_bundle_id, self.retrieval_run_id, self.project_id,
            ))
                or type(self.context_policy_ref) is not str
                or not self.context_policy_ref
                or not _digest(self.bundle_fingerprint)
                or type(self.token_budget) is not int or self.token_budget < 1
                or type(self.token_count) is not int
                or not 1 <= self.token_count <= self.token_budget
                or type(self.items) is not tuple or not self.items
                or len(self.items) > 100
                or tuple(item.ordinal for item in self.items)
                   != tuple(range(len(self.items)))
                or sum(item.token_count for item in self.items) != self.token_count
                or not _time(self.created_at)):
            raise RAGRetrievalReadError()
        for item in self.items:
            item.__post_init__()


class RAGRetrievalReadRepositoryPort(Protocol):
    def get_run(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                project_id: uuid.UUID) -> RAGRetrievalRunView | None: ...

    def get_result(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                   project_id: uuid.UUID) -> RAGRetrievalResultView | None: ...

    def get_context(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                    project_id: uuid.UUID) -> RAGContextBundleView | None: ...


class RAGRetrievalReadAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           now: datetime) -> uuid.UUID | None: ...


class RAGRetrievalReadService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: RAGRetrievalReadAccessPort, license_guard: object,
                 authorization: ProjectAuthorizationService,
                 repository: RAGRetrievalReadRepositoryPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository,
        )):
            raise ValueError("RAG Retrieval read dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def get_run(self, query: GetRAGRetrieval) -> RAGRetrievalRunView:
        return self._read(query, operation="RAG_RETRIEVAL_GET", kind="run")

    def get_result(self, query: GetRAGRetrieval) -> RAGRetrievalResultView:
        return self._read(query, operation="RAG_RETRIEVAL_RESULT_GET", kind="result")

    def get_context(self, query: GetRAGRetrieval) -> RAGContextBundleView:
        return self._read(query, operation="RAG_CONTEXT_GET", kind="context")

    def _read(self, query: GetRAGRetrieval, *, operation: str, kind: str):
        if type(query) is not GetRAGRetrieval:
            raise RAGRetrievalReadError("VALIDATION_FAILED")
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as transaction:
                now = self._clock()
                if not _time(now):
                    raise RAGRetrievalReadError()
                actor = self._access.authenticated_user(
                    transaction, session_token=query.session_token,
                    now=now.astimezone(timezone.utc),
                )
                if not _id(actor):
                    raise RAGRetrievalReadError("AUTH_ACCESS_DENIED")
                proof = self._authorization.require_in_transaction(
                    transaction, user_id=actor, project_id=query.project_id,
                    operation=operation,
                )
                if (type(proof) is not AuthorizedProjectAction
                        or proof.user_id != actor
                        or proof.project_id != query.project_id
                        or proof.operation != operation):
                    raise RAGRetrievalReadError("RESOURCE_NOT_FOUND")
                run = self._repository.get_run(
                    transaction, retrieval_run_id=query.retrieval_run_id,
                    project_id=query.project_id,
                )
                if type(run) is not RAGRetrievalRunView:
                    raise RAGRetrievalReadError("RESOURCE_NOT_FOUND")
                run.__post_init__()
                if (run.retrieval_run_id != query.retrieval_run_id
                        or run.project_id != query.project_id):
                    raise RAGRetrievalReadError()
                if (run.requested_by != actor
                        and proof.project_role not in _OVERSIGHT_ROLES):
                    raise RAGRetrievalReadError("RESOURCE_NOT_FOUND")
                if kind == "run":
                    value = run
                else:
                    if run.retrieval_state != "SUCCEEDED":
                        raise RAGRetrievalReadError(
                            "RAG_RETRIEVAL_RESULT_NOT_READY"
                            if kind == "result" else "RAG_CONTEXT_NOT_READY"
                        )
                    method = (self._repository.get_result if kind == "result"
                              else self._repository.get_context)
                    value = method(
                        transaction, retrieval_run_id=query.retrieval_run_id,
                        project_id=query.project_id,
                    )
                    expected = (RAGRetrievalResultView if kind == "result"
                                else RAGContextBundleView)
                    if type(value) is not expected:
                        raise RAGRetrievalReadError()
                    value.__post_init__()
                    if (value.retrieval_run_id != query.retrieval_run_id
                            or value.project_id != query.project_id):
                        raise RAGRetrievalReadError()
                self._guard.require_valid(trace_id=query.trace_id)
                return value
        except RAGRetrievalReadError:
            raise
        except ProjectAuthorizationError:
            raise RAGRetrievalReadError("RESOURCE_NOT_FOUND") from None
        except RuntimeLicenseError:
            raise RAGRetrievalReadError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise RAGRetrievalReadError() from None
