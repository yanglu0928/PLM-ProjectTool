"""PostgreSQL proof for the current leased AI Task execution generation."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from plm_assistant.modules.jobs.application.ai_task_execution_claim import (
    AITaskExecutionClaim,
)
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
    try:
        parsed = uuid.UUID(value)
    except (AttributeError, ValueError):
        raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
    if not parsed.int or str(parsed) != value:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
    return parsed


def _fingerprint(value: object) -> bytes:
    if type(value) is not str or len(value) != 64:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
    try:
        parsed = bytes.fromhex(value)
    except ValueError:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
    if len(parsed) != 32 or parsed.hex() != value:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
    return parsed


class SqlAlchemyAITaskExecutionClaimRepository:
    def __init__(self) -> None:
        self._leases = SqlAlchemyJobLeaseRepository()

    @staticmethod
    def _snapshot(session, job: JobRow, *, observed_at) -> AITaskExecutionClaim:
        payload = job.payload_refs
        if (job.owner_module != "ai" or job.job_type != "AI_TASK_EXECUTE"
                or job.scope != "PROJECT"
                or type(job.project_id) is not uuid.UUID or not job.project_id.int
                or type(job.actor_ref) is not uuid.UUID or not job.actor_ref.int
                or type(job.max_attempts) is not int
                or not 1 <= job.max_attempts <= 10
                or job.lease_expires_at is None
                or job.lease_expires_at <= observed_at
                or type(payload) is not dict
                or set(payload) != {
                    "ai_task_id", "egress_authorization_ref", "input_fingerprint",
                }):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        task_id = _uuid(payload["ai_task_id"])
        authorization_ref = _uuid(payload["egress_authorization_ref"])
        input_fingerprint = _fingerprint(payload["input_fingerprint"])
        trace_id = _uuid(job.trace_id)
        if job.idempotency_key != str(task_id):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        events = list(session.scalars(select(OutboxEventRow).where(
            OutboxEventRow.owner_module == "ai",
            OutboxEventRow.event_type == "AI_TASK_QUEUED",
            OutboxEventRow.scope == "PROJECT",
            OutboxEventRow.project_id == job.project_id,
            OutboxEventRow.aggregate_ref == task_id,
            OutboxEventRow.idempotency_key == job.idempotency_key,
        ).execution_options(autoflush=False)))
        if len(events) != 1:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        event = events[0]
        if (event.aggregate_version != 0
                or event.payload_refs != {
                    "ai_task_id": str(task_id), "job_id": str(job.job_id),
                }
                or event.trace_id != job.trace_id):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        return AITaskExecutionClaim(
            job.job_id, task_id, job.project_id, job.actor_ref, trace_id,
            authorization_ref, input_fingerprint, job.fencing_token,
            job.attempt_count, job.max_attempts, observed_at,
            job.lease_expires_at,
        )

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int,
                      worker_ref: str) -> AITaskExecutionClaim:
        current = self._leases.check_current(
            transaction, job_id=job_id, fencing_token=fencing_token,
            worker_ref=worker_ref,
        )
        if current.job_type != "AI_TASK_EXECUTE" or current.scope != "PROJECT":
            raise JobLeaseError("STALE_LEASE")
        session = self._leases._session(transaction)
        job = session.get(JobRow, job_id, populate_existing=True)
        if job is None:
            raise JobLeaseError("STALE_LEASE")
        observed_at = self._leases._now(session)
        claim = self._snapshot(session, job, observed_at=observed_at)
        if (claim.fencing_token != current.fencing_token
                or claim.attempt_no != current.attempt_no
                or claim.project_id != current.project_id
                or current.payload_refs != job.payload_refs
                or current.trace_id != job.trace_id):
            raise JobLeaseError("INCONSISTENT_LEASE")
        return claim
