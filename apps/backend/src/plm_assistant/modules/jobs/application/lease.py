"""Transaction-scoped job leasing; consumers still need idempotent publication."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from re import fullmatch
from typing import Protocol


class JobLeaseError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ClaimedJob:
    job_id: uuid.UUID
    job_type: str
    scope: str
    project_id: uuid.UUID | None
    payload_refs: dict
    trace_id: str
    fencing_token: int
    attempt_no: int


class JobLeaseRepositoryPort(Protocol):
    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> ClaimedJob | None: ...
    def heartbeat(self, transaction: object, *, job_id: uuid.UUID,
                  fencing_token: int, worker_ref: str, lease_seconds: int) -> None: ...
    def finish(self, transaction: object, *, job_id: uuid.UUID,
               fencing_token: int, worker_ref: str) -> ClaimedJob: ...
    def retry_or_fail(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str,
                      error_code: str, retryable: bool, delay_seconds: int) -> str: ...


class JobLeaseService:
    """Every method owns a short database transaction; no external work runs inside it."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: JobLeaseRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("Job lease dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository

    def claim_next(self, *, worker_ref: str, lease_seconds: int) -> ClaimedJob | None:
        self._validate_worker(worker_ref)
        if not 1 <= lease_seconds <= 3600:
            raise JobLeaseError("INVALID_LEASE_DURATION")
        with self._unit_of_work() as tx:
            result = self._repository.claim_next(tx, worker_ref=worker_ref,
                                                 lease_seconds=lease_seconds)
            tx.commit()
            return result

    def heartbeat(self, *, job_id: uuid.UUID, fencing_token: int,
                  worker_ref: str, lease_seconds: int) -> None:
        self._validate_worker(worker_ref)
        if not 1 <= lease_seconds <= 3600:
            raise JobLeaseError("INVALID_LEASE_DURATION")
        with self._unit_of_work() as tx:
            self._repository.heartbeat(tx, job_id=job_id, fencing_token=fencing_token,
                                       worker_ref=worker_ref, lease_seconds=lease_seconds)
            tx.commit()

    def finish(self, *, job_id: uuid.UUID, fencing_token: int,
               worker_ref: str, publish: Callable[[object, ClaimedJob], None]) -> None:
        """Publish must only perform short, idempotent database work in this transaction."""
        self._validate_worker(worker_ref)
        if publish is None:
            raise JobLeaseError("PUBLISH_REQUIRED")
        with self._unit_of_work() as tx:
            claim = self._repository.finish(tx, job_id=job_id,
                                            fencing_token=fencing_token,
                                            worker_ref=worker_ref)
            publish(tx, claim)
            tx.commit()

    def retry_or_fail(self, *, job_id: uuid.UUID, fencing_token: int,
                      worker_ref: str, error_code: str,
                      retryable: bool, delay_seconds: int = 0) -> str:
        self._validate_worker(worker_ref)
        if not error_code or len(error_code) > 64 or not error_code.replace("_", "").isalnum():
            raise JobLeaseError("INVALID_ERROR_CODE")
        if not 0 <= delay_seconds <= 86_400:
            raise JobLeaseError("INVALID_RETRY_DELAY")
        with self._unit_of_work() as tx:
            state = self._repository.retry_or_fail(
                tx, job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref, error_code=error_code,
                retryable=retryable, delay_seconds=delay_seconds,
            )
            tx.commit()
            return state

    @staticmethod
    def _validate_worker(worker_ref: str) -> None:
        if not isinstance(worker_ref, str) or not fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", worker_ref):
            raise JobLeaseError("INVALID_WORKER")
