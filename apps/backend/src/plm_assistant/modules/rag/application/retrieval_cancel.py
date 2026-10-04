"""Current-authorized Retrieval cancellation and cooperative reconciliation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy.exc import DBAPIError

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.cancel_request import (
    JobCancelError,
    JobCancelResult,
    RequestProjectJobCancel,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


_JOB_OPERATION = "V1_RAG_RETRIEVAL_JOB_CANCEL"
_RUN_OPERATION = "V1_RAG_RETRIEVAL_CANCEL"
_STATES = frozenset({
    "PENDING", "RUNNING", "CANCEL_REQUESTED", "CANCELLED",
    "SUCCEEDED", "FAILED",
})


class RAGRetrievalCancelError(RuntimeError):
    def __init__(self, code: str = "RAG_RETRIEVAL_CANCEL_UNAVAILABLE", *,
                 committed: bool = False) -> None:
        if type(committed) is not bool:
            raise ValueError("committed must be bool")
        self.code = code
        self.committed = committed
        super().__init__(code)


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and bool(value.int)


def _time(value: object) -> bool:
    return (isinstance(value, datetime) and value.tzinfo is not None
            and value.utcoffset() is not None)


@dataclass(frozen=True, slots=True)
class RequestRAGRetrievalCancel:
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    reason: str = field(repr=False)
    expected_version: int

    def __post_init__(self) -> None:
        try:
            RequestProjectJobCancel(
                self.retrieval_run_id, self.project_id, self.session_token,
                self.csrf_token, self.trace_id, self.reason,
                self.expected_version,
            ).__post_init__()
        except JobCancelError as error:
            raise RAGRetrievalCancelError(error.code) from None


@dataclass(frozen=True, slots=True)
class RAGRetrievalCancelBinding:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    run_state: str
    job_state: str
    run_lock_version: int
    job_lock_version: int

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.retrieval_run_id, self.job_id, self.project_id,
                self.requested_by, self.trace_id,
        ))
                or self.job_state not in _STATES
                or self.run_state not in {
                    "RUNNING", "CANCELLED", "SUCCEEDED", "FAILED",
                }
                or any(type(value) is not int or value < 0 for value in (
                    self.run_lock_version, self.job_lock_version,
                ))):
            raise RAGRetrievalCancelError()


@dataclass(frozen=True, slots=True)
class CancelledRAGRetrieval:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    state: str
    changed: bool
    run_lock_version: int
    job_lock_version: int
    completed_at: datetime | None

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.retrieval_run_id, self.job_id, self.project_id,
        ))
                or self.state not in {
                    "CANCEL_REQUESTED", "CANCELLED", "SUCCEEDED", "FAILED",
                }
                or type(self.changed) is not bool
                or self.changed and self.state in {"SUCCEEDED", "FAILED"}
                or any(type(value) is not int or value < 0 for value in (
                    self.run_lock_version, self.job_lock_version,
                ))
                or self.completed_at is not None and not _time(self.completed_at)):
            raise RAGRetrievalCancelError()
        if ((self.state in {"CANCELLED", "SUCCEEDED", "FAILED"})
                != (self.completed_at is not None)):
            raise RAGRetrievalCancelError()


@dataclass(frozen=True, slots=True)
class ReconciledRAGRetrievalCancel:
    retrieval_run_id: uuid.UUID
    job_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    trace_id: uuid.UUID
    lease_outcome: str
    completed_at: datetime

    def __post_init__(self) -> None:
        if (not all(_id(value) for value in (
                self.retrieval_run_id, self.job_id, self.project_id,
                self.requested_by, self.trace_id,
        )) or self.lease_outcome not in {"RELEASED", "EXPIRED"}
                or not _time(self.completed_at)):
            raise RAGRetrievalCancelError()


class RAGRetrievalCancellationRepositoryPort(Protocol):
    def binding_for_job(self, transaction: object, *, job_id: uuid.UUID,
                        project_id: uuid.UUID
                        ) -> RAGRetrievalCancelBinding | None: ...

    def binding_for_run(self, transaction: object, *, retrieval_run_id: uuid.UUID,
                        project_id: uuid.UUID
                        ) -> RAGRetrievalCancelBinding | None: ...

    def request_cancel(self, transaction: object, *,
                       binding: RAGRetrievalCancelBinding,
                       requested_by: uuid.UUID,
                       reason: str) -> CancelledRAGRetrieval: ...

    def receipt(self, transaction: object, *,
                binding: RAGRetrievalCancelBinding, actor_id: uuid.UUID,
                audit_event_id: uuid.UUID) -> CancelledRAGRetrieval: ...

    def reconcile_current(self, transaction: object, *, job_id: uuid.UUID,
                          fencing_token: int,
                          worker_ref: str) -> ReconciledRAGRetrievalCancel: ...

    def reconcile_expired_next(self, transaction: object
                               ) -> ReconciledRAGRetrievalCancel | None: ...


class RAGRetrievalCancelOwner:
    """Single write Owner used by Retrieval alias and generic Job dispatch."""

    def __init__(self, *, unit_of_work: Callable[[], object], access: object,
                 authorization: ProjectAuthorizationService,
                 license_guard: object,
                 repository: RAGRetrievalCancellationRepositoryPort,
                 receipts: object, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (
                unit_of_work, access, authorization, license_guard,
                repository, receipts, audit)):
            raise ValueError("RAG Retrieval cancellation dependencies required")
        self._uow, self._access = unit_of_work, access
        self._authorization, self._guard = authorization, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _deadlock(error: BaseException) -> bool:
        seen: set[int] = set()
        for _ in range(16):
            if id(error) in seen:
                return False
            seen.add(id(error))
            if (isinstance(error, DBAPIError)
                    and getattr(error.orig, "sqlstate", None) == "40P01"):
                return True
            nested = error.__cause__ or error.__context__
            if not isinstance(nested, BaseException):
                return False
            error = nested
        return False

    def cancel(self, command: RequestProjectJobCancel, *,
               idempotency_key: str) -> JobCancelResult:
        if type(command) is not RequestProjectJobCancel:
            raise JobCancelError("VALIDATION_FAILED")
        command.__post_init__()
        try:
            result = self._execute(
                command=command, idempotency_key=idempotency_key,
                operation=_JOB_OPERATION, by_run=False,
                target_id=command.job_id,
            )
        except RAGRetrievalCancelError as error:
            code = {
                "RESOURCE_NOT_FOUND": "RESOURCE_NOT_FOUND",
                "CONFLICT_VERSION": "CONFLICT_VERSION",
                "CONFLICT_IDEMPOTENCY": "CONFLICT_IDEMPOTENCY",
                "LICENSE_OPERATION_DENIED": "LICENSE_OPERATION_DENIED",
                "VALIDATION_FAILED": "VALIDATION_FAILED",
            }.get(error.code, "JOB_UNAVAILABLE")
            raise JobCancelError(code) from None
        return JobCancelResult(
            result.job_id, result.state, result.changed,
            result.job_lock_version,
        )

    def cancel_retrieval(self, command: RequestRAGRetrievalCancel, *,
                         idempotency_key: str) -> CancelledRAGRetrieval:
        if type(command) is not RequestRAGRetrievalCancel:
            raise RAGRetrievalCancelError("VALIDATION_FAILED")
        command.__post_init__()
        generic = RequestProjectJobCancel(
            command.retrieval_run_id, command.project_id,
            command.session_token, command.csrf_token, command.trace_id,
            command.reason, command.expected_version,
        )
        return self._execute(
            command=generic, idempotency_key=idempotency_key,
            operation=_RUN_OPERATION, by_run=True,
            target_id=command.retrieval_run_id,
        )

    def _execute(self, *, command: RequestProjectJobCancel,
                 idempotency_key: str, operation: str, by_run: bool,
                 target_id: uuid.UUID) -> CancelledRAGRetrieval:
        try:
            validate_idempotency_key(idempotency_key)
        except IdempotencyError as error:
            raise RAGRetrievalCancelError(error.code) from None
        for attempt in range(3):
            try:
                return self._execute_once(
                    command=command, idempotency_key=idempotency_key,
                    operation=operation, by_run=by_run,
                    target_id=target_id,
                )
            except Exception as error:
                if self._deadlock(error):
                    if attempt < 2:
                        continue
                    raise RAGRetrievalCancelError() from None
                raise self._map_error(error) from None
        raise RAGRetrievalCancelError()

    @staticmethod
    def _map_error(error: Exception) -> RAGRetrievalCancelError:
        if isinstance(error, RAGRetrievalCancelError):
            return error
        if isinstance(error, JobCancelError):
            return RAGRetrievalCancelError(error.code)
        if isinstance(error, IdempotencyError):
            return RAGRetrievalCancelError(error.code)
        if isinstance(error, ProjectAuthorizationError):
            return RAGRetrievalCancelError("RESOURCE_NOT_FOUND")
        if isinstance(error, RuntimeLicenseError):
            return RAGRetrievalCancelError("LICENSE_OPERATION_DENIED")
        return RAGRetrievalCancelError()

    def _binding(self, transaction: object, *, by_run: bool,
                 target_id: uuid.UUID,
                 project_id: uuid.UUID) -> RAGRetrievalCancelBinding:
        method = (self._repo.binding_for_run if by_run
                  else self._repo.binding_for_job)
        keywords = ({"retrieval_run_id": target_id} if by_run
                    else {"job_id": target_id})
        binding = method(transaction, project_id=project_id, **keywords)
        if type(binding) is not RAGRetrievalCancelBinding:
            raise RAGRetrievalCancelError("RESOURCE_NOT_FOUND")
        binding.__post_init__()
        return binding

    def _authorize(self, transaction: object, *,
                   command: RequestProjectJobCancel,
                   binding: RAGRetrievalCancelBinding) -> uuid.UUID:
        self._guard.require_valid(trace_id=command.trace_id)
        now = self._clock()
        if not _time(now):
            raise RAGRetrievalCancelError()
        actor = self._access.authenticated_user(
            transaction, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if not _id(actor):
            raise RAGRetrievalCancelError("RESOURCE_NOT_FOUND")
        proof = self._authorization.require_in_transaction(
            transaction, user_id=actor, project_id=command.project_id,
            operation="JOB_PROJECT_CANCEL",
        )
        if (proof.user_id != actor or proof.project_id != command.project_id
                or (actor != binding.requested_by
                    and proof.project_role != "PROJECT_MANAGER")):
            raise RAGRetrievalCancelError("RESOURCE_NOT_FOUND")
        return actor

    def _execute_once(self, *, command: RequestProjectJobCancel,
                      idempotency_key: str, operation: str, by_run: bool,
                      target_id: uuid.UUID) -> CancelledRAGRetrieval:
        with self._uow() as transaction:
            binding = self._binding(
                transaction, by_run=by_run, target_id=target_id,
                project_id=command.project_id,
            )
            actor = self._authorize(
                transaction, command=command, binding=binding,
            )
            scope = IdempotencyScope.from_key(
                actor_id=actor, project_id=command.project_id,
                operation=operation, key=idempotency_key,
            )
            fingerprint = canonical_payload_fingerprint({
                "retrieval_run_id": str(binding.retrieval_run_id),
                "job_id": str(binding.job_id),
                "reason": command.reason,
                "expected_version": command.expected_version,
            })
            replay = self._receipts.reserve(
                transaction, scope=scope,
                request_fingerprint=fingerprint,
            )
            if replay is not None:
                if (type(replay) is not IdempotencyResult
                        or replay.ref_type != operation
                        or replay.status_code != 200):
                    raise RAGRetrievalCancelError()
                result = self._repo.receipt(
                    transaction, binding=binding, actor_id=actor,
                    audit_event_id=replay.ref_id,
                )
            else:
                actual_version = (binding.run_lock_version if by_run
                                  else binding.job_lock_version)
                if actual_version != command.expected_version:
                    raise RAGRetrievalCancelError("CONFLICT_VERSION")
                result = self._repo.request_cancel(
                    transaction, binding=binding, requested_by=actor,
                    reason=command.reason,
                )
                result.__post_init__()
                action = ("RAG_RETRIEVAL_CANCEL_CHECKED"
                          if not result.changed else
                          "RAG_RETRIEVAL_CANCEL_REQUESTED"
                          if result.state == "CANCEL_REQUESTED" else
                          "RAG_RETRIEVAL_CANCELLED")
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id,
                    actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action=action, outcome="SUCCESS",
                    target_owner_module="rag", target_object_type="RAG-04",
                    target_object_id=binding.retrieval_run_id,
                    reason_code="USER_REQUESTED",
                    before_state=binding.job_state,
                    after_state=result.state,
                ))
                if not _id(event_id):
                    raise RAGRetrievalCancelError()
                self._receipts.complete(
                    transaction, scope=scope,
                    result=IdempotencyResult(operation, event_id, 200),
                )
            if (type(result) is not CancelledRAGRetrieval
                    or result.retrieval_run_id != binding.retrieval_run_id
                    or result.job_id != binding.job_id
                    or result.project_id != binding.project_id):
                raise RAGRetrievalCancelError()
            result.__post_init__()
            if self._authorize(
                    transaction, command=command, binding=binding) != actor:
                raise RAGRetrievalCancelError("RESOURCE_NOT_FOUND")
            if replay is None:
                transaction.commit()
            return result


class RAGRetrievalCancelReconciler:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: RAGRetrievalCancellationRepositoryPort,
                 audit: AuditService, system_actor: object) -> None:
        if any(value is None for value in (
                unit_of_work, repository, audit, system_actor)):
            raise ValueError("RAG Retrieval cancel reconciler dependencies required")
        self._uow, self._repo = unit_of_work, repository
        self._audit, self._actor = audit, system_actor

    def reconcile_current(self, *, job_id: uuid.UUID, fencing_token: int,
                          worker_ref: str) -> ReconciledRAGRetrievalCancel:
        if (not _id(job_id) or type(fencing_token) is not int
                or fencing_token < 1 or type(worker_ref) is not str
                or not 1 <= len(worker_ref) <= 128
                or worker_ref.strip() != worker_ref):
            raise RAGRetrievalCancelError("VALIDATION_FAILED")
        return self._run(lambda transaction: self._repo.reconcile_current(
            transaction, job_id=job_id, fencing_token=fencing_token,
            worker_ref=worker_ref,
        ))

    def reconcile_expired_next(self) -> ReconciledRAGRetrievalCancel | None:
        return self._run(self._repo.reconcile_expired_next, optional=True)

    def _run(self, callback, *, optional: bool = False):
        committed = False
        try:
            actor = self._actor.assert_current()
            if not _id(actor):
                raise RAGRetrievalCancelError("SYSTEM_ACTOR_UNAVAILABLE")
            with self._uow() as transaction:
                result = callback(transaction)
                if result is None and optional:
                    return None
                if type(result) is not ReconciledRAGRetrievalCancel:
                    raise RAGRetrievalCancelError()
                result.__post_init__()
                event_id = self._audit.append(transaction, AuditEventDraft(
                    trace_id=result.trace_id, event_scope="PROJECT",
                    target_project_id=result.project_id,
                    actor_type="SYSTEM", actor_id=actor,
                    original_actor_id=result.requested_by,
                    actor_hint_digest=None,
                    action="RAG_RETRIEVAL_CANCELLED", outcome="SUCCESS",
                    target_owner_module="rag", target_object_type="RAG-04",
                    target_object_id=result.retrieval_run_id,
                    reason_code=("LEASE_EXPIRED"
                                 if result.lease_outcome == "EXPIRED"
                                 else "USER_REQUESTED"),
                    before_state="CANCEL_REQUESTED", after_state="CANCELLED",
                ))
                if not _id(event_id) or self._actor.assert_current() != actor:
                    raise RAGRetrievalCancelError("SYSTEM_ACTOR_UNAVAILABLE")
                transaction.commit()
                committed = True
            return result
        except RAGRetrievalCancelError as error:
            if committed and not error.committed:
                raise RAGRetrievalCancelError(
                    error.code, committed=True,
                ) from None
            raise
        except Exception:
            raise RAGRetrievalCancelError(committed=committed) from None
