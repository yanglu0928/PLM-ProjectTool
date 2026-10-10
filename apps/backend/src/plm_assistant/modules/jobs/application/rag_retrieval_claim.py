"""Jobs-owned, owner-scoped proof for one RAG retrieval lease."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint


@dataclass(frozen=True, slots=True)
class RAGRetrievalClaim:
    job_id: uuid.UUID
    retrieval_run_id: uuid.UUID
    project_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    fencing_token: int
    attempt_no: int
    observed_at: datetime
    lease_expires_at: datetime

    def __post_init__(self) -> None:
        required = (
            self.job_id, self.retrieval_run_id, self.project_id,
            self.actor_id, self.trace_id,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in required)
                or type(self.fencing_token) is not int or self.fencing_token != 1
                or type(self.attempt_no) is not int or self.attempt_no != 1
                or not isinstance(self.observed_at, datetime)
                or self.observed_at.tzinfo is None
                or self.observed_at.utcoffset() is None
                or not isinstance(self.lease_expires_at, datetime)
                or self.lease_expires_at.tzinfo is None
                or self.lease_expires_at.utcoffset() is None
                or self.observed_at >= self.lease_expires_at):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")


class RAGRetrievalClaimRepositoryPort(Protocol):
    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> RAGRetrievalClaim | None: ...
    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> RAGRetrievalClaim: ...


class RAGRetrievalClaims:
    """Claim only RAG retrieval Jobs and verify the exact current generation."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: RAGRetrievalClaimRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("RAG retrieval claim dependencies required")
        self._uow = unit_of_work
        self._repository = repository

    def claim_next(self, *, worker_ref: str,
                   lease_seconds: int) -> RAGRetrievalClaim | None:
        JobLeaseService._validate_worker(worker_ref)
        if type(lease_seconds) is not int or not 3 <= lease_seconds <= 3600:
            raise JobLeaseError("INVALID_LEASE_DURATION")
        try:
            with self._uow() as transaction:
                claim = self._repository.claim_next(
                    transaction, worker_ref=worker_ref,
                    lease_seconds=lease_seconds,
                )
                if claim is not None:
                    if type(claim) is not RAGRetrievalClaim:
                        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
                    claim.__post_init__()
                transaction.commit()
                return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> RAGRetrievalClaim:
        validate_checkpoint(
            job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref,
        )
        try:
            claim = self._repository.check_current(
                transaction, job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref,
            )
            if (type(claim) is not RAGRetrievalClaim
                    or claim.job_id != job_id
                    or claim.fencing_token != fencing_token):
                raise JobLeaseError("JOB_STORE_UNAVAILABLE")
            claim.__post_init__()
            return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
