"""Owner-scoped lease contract for a Provider Test Worker, not egress authority."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.jobs.application.lease import JobLeaseError, JobLeaseService
from plm_assistant.modules.jobs.application.lease_checkpoint import validate_checkpoint

PROBE_ID = "CHAT_CONNECTIVITY_V1"


@dataclass(frozen=True, slots=True)
class AIProviderTestClaim:
    job_id: uuid.UUID
    provider_id: uuid.UUID
    config_id: uuid.UUID
    config_version: int
    secret_version_id: uuid.UUID
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    policy_sha256: bytes = field(repr=False)
    fencing_token: int = 0
    attempt_no: int = 0
    probe_id: str = PROBE_ID

    def __post_init__(self) -> None:
        if (any(type(value) is not uuid.UUID or not value.int for value in (
                self.job_id, self.provider_id, self.config_id,
                self.secret_version_id, self.actor_id, self.trace_id))
                or type(self.config_version) is not int or not 1 <= self.config_version <= 2147483647
                or type(self.policy_sha256) is not bytes or len(self.policy_sha256) != 32
                or type(self.fencing_token) is not int or not 1 <= self.fencing_token <= 9223372036854775807
                or type(self.attempt_no) is not int or not 1 <= self.attempt_no <= 3
                or self.probe_id != PROBE_ID):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")


class AIProviderTestClaimRepositoryPort(Protocol):
    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> AIProviderTestClaim | None: ...
    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> AIProviderTestClaim: ...


class AIProviderTestClaims:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: AIProviderTestClaimRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("Provider Test claim dependencies required")
        self._uow, self._repo = unit_of_work, repository

    def claim_next(self, *, worker_ref: str, lease_seconds: int) -> AIProviderTestClaim | None:
        JobLeaseService._validate_worker(worker_ref)
        if type(lease_seconds) is not int or not 3 <= lease_seconds <= 3600:
            raise JobLeaseError("INVALID_LEASE_DURATION")
        try:
            with self._uow() as tx:
                claim = self._repo.claim_next(tx, worker_ref=worker_ref,
                                              lease_seconds=lease_seconds)
                if claim is not None:
                    if type(claim) is not AIProviderTestClaim:
                        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
                    claim.__post_init__()
                tx.commit()
                return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> AIProviderTestClaim:
        validate_checkpoint(job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref)
        try:
            claim = self._repo.check_current(transaction, job_id=job_id,
                                             fencing_token=fencing_token,
                                             worker_ref=worker_ref)
            if (type(claim) is not AIProviderTestClaim or claim.job_id != job_id
                    or claim.fencing_token != fencing_token):
                raise JobLeaseError("JOB_STORE_UNAVAILABLE")
            claim.__post_init__()
            return claim
        except JobLeaseError:
            raise
        except Exception:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
