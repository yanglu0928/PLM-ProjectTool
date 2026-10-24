"""PostgreSQL owner-only admission for one single-attempt RAG retrieval Job."""

from __future__ import annotations

import uuid

from plm_assistant.modules.jobs.application.lease import ClaimedJob, JobLeaseError
from plm_assistant.modules.jobs.application.rag_retrieval_claim import RAGRetrievalClaim
from plm_assistant.modules.jobs.infrastructure.lease_repository import (
    SqlAlchemyJobLeaseRepository,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow


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


class SqlAlchemyRAGRetrievalClaimRepository:
    def __init__(self) -> None:
        self._leases = SqlAlchemyJobLeaseRepository()

    def _snapshot(self, session, job: JobRow, *, observed_at) -> RAGRetrievalClaim:
        del session
        payload = job.payload_refs
        if (job.owner_module != "rag" or job.job_type != "RAG_RETRIEVAL"
                or job.scope != "PROJECT"
                or type(job.project_id) is not uuid.UUID or not job.project_id.int
                or type(job.actor_ref) is not uuid.UUID or not job.actor_ref.int
                or job.max_attempts != 1 or job.attempt_count != 1
                or job.fencing_token != 1 or job.completed_at is not None
                or job.state != "RUNNING"
                or job.lease_expires_at is None
                or job.lease_expires_at <= observed_at
                or type(payload) is not dict
                or set(payload) != {"retrieval_run_id"}):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        retrieval_run_id = _uuid(payload["retrieval_run_id"])
        if job.idempotency_key != str(retrieval_run_id):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        return RAGRetrievalClaim(
            job.job_id, retrieval_run_id, job.project_id, job.actor_ref,
            _uuid(job.trace_id), job.fencing_token, job.attempt_count,
            observed_at, job.lease_expires_at,
        )

    @staticmethod
    def _matches_generic(claim: RAGRetrievalClaim, current: ClaimedJob) -> bool:
        return (current.job_id == claim.job_id
                and current.job_type == "RAG_RETRIEVAL"
                and current.scope == "PROJECT"
                and current.project_id == claim.project_id
                and current.fencing_token == claim.fencing_token
                and current.attempt_no == claim.attempt_no
                and current.trace_id == str(claim.trace_id)
                and current.payload_refs == {
                    "retrieval_run_id": str(claim.retrieval_run_id),
                })

    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> RAGRetrievalClaim | None:
        current = self._leases.claim_next_rag_retrieval(
            transaction, worker_ref=worker_ref, lease_seconds=lease_seconds,
        )
        if current is None:
            return None
        session = self._leases._session(transaction)
        job = session.get(JobRow, current.job_id, populate_existing=True)
        if job is None:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        claim = self._snapshot(session, job, observed_at=self._leases._now(session))
        if not self._matches_generic(claim, current):
            raise JobLeaseError("INCONSISTENT_LEASE")
        return claim

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> RAGRetrievalClaim:
        current = self._leases.check_current(
            transaction, job_id=job_id, fencing_token=fencing_token,
            worker_ref=worker_ref,
        )
        if current.job_type != "RAG_RETRIEVAL":
            raise JobLeaseError("STALE_LEASE")
        session = self._leases._session(transaction)
        job = session.get(JobRow, job_id, populate_existing=True)
        if job is None:
            raise JobLeaseError("STALE_LEASE")
        claim = self._snapshot(session, job, observed_at=self._leases._now(session))
        if not self._matches_generic(claim, current):
            raise JobLeaseError("INCONSISTENT_LEASE")
        return claim
