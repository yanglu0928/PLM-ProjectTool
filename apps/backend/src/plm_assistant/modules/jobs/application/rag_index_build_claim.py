"""Jobs-owned, owner-scoped proof for one RAG index build lease."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint


@dataclass(frozen=True, slots=True)
class RAGIndexBuildClaim:
    job_id: uuid.UUID
    embedding_build_id: uuid.UUID
    embedding_index_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    build_generation: int
    fencing_token: int
    attempt_no: int
    observed_at: datetime
    lease_expires_at: datetime

    def __post_init__(self) -> None:
        required = (
            self.job_id, self.embedding_build_id, self.embedding_index_id,
            self.actor_id, self.trace_id,
        )
        if (any(type(value) is not uuid.UUID or not value.int for value in required)
                or self.scope not in {"GLOBAL", "PROJECT"}
                or (self.scope == "GLOBAL" and self.project_id is not None)
                or (self.scope == "PROJECT" and (
                    type(self.project_id) is not uuid.UUID or not self.project_id.int))
                or type(self.build_generation) is not int or self.build_generation != 1
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


class RAGIndexBuildClaimRepositoryPort(Protocol):
    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> RAGIndexBuildClaim | None: ...
    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> RAGIndexBuildClaim: ...


class RAGIndexBuildClaims:
    """Claim only RAG build Jobs and verify the exact current generation."""

    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: RAGIndexBuildClaimRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("RAG index build claim dependencies required")
        self._uow = unit_of_work
        self._repository = repository

    def claim_next(self, *, worker_ref: str,
                   lease_seconds: int) -> RAGIndexBuildClaim | None:
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
                    if type(claim) is not RAGIndexBuildClaim:
                        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
                    claim.__post_init__()
                transaction.commit()
                return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> RAGIndexBuildClaim:
        validate_checkpoint(
            job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref,
        )
        try:
            claim = self._repository.check_current(
                transaction, job_id=job_id, fencing_token=fencing_token,
                worker_ref=worker_ref,
            )
            if (type(claim) is not RAGIndexBuildClaim
                    or claim.job_id != job_id
                    or claim.fencing_token != fencing_token):
                raise JobLeaseError("JOB_STORE_UNAVAILABLE")
            claim.__post_init__()
            return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
