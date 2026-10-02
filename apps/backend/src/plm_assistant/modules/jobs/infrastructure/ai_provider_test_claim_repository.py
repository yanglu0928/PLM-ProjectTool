"""PostgreSQL owner-only Provider Test lease admission and immutable pair proof."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import and_, or_, select

from plm_assistant.modules.jobs.application.ai_provider_test_claim import AIProviderTestClaim
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import (
    JobAttemptRow, JobLeaseRow, JobRow, OutboxEventRow,
)


def _uuid(value: object) -> uuid.UUID:
    if type(value) is not str:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
    if not parsed.int or str(parsed) != value:
        raise JobLeaseError("JOB_STORE_UNAVAILABLE")
    return parsed


class SqlAlchemyAIProviderTestClaimRepository:
    def __init__(self) -> None:
        self._leases = SqlAlchemyJobLeaseRepository()

    def _snapshot(self, session, job: JobRow) -> tuple[uuid.UUID, uuid.UUID, int, uuid.UUID, bytes]:
        payload = job.payload_refs
        if (job.owner_module != "ai" or job.job_type != "AI_PROVIDER_TEST"
                or job.scope != "DEPLOYMENT" or job.project_id is not None
                or job.max_attempts != 3 or type(job.actor_ref) is not uuid.UUID
                or not job.actor_ref.int or type(payload) is not dict
                or set(payload) != {"provider_id", "config_id", "secret_version_id",
                                    "policy_sha256", "probe_id"}
                or payload["probe_id"] != "CHAT_CONNECTIVITY_V1"):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        provider_id = _uuid(payload["provider_id"])
        config_id = _uuid(payload["config_id"])
        secret_version_id = _uuid(payload["secret_version_id"])
        digest = payload["policy_sha256"]
        if type(digest) is not str or len(digest) != 64:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        try:
            policy_sha256 = bytes.fromhex(digest)
            trace_id = _uuid(job.trace_id)
        except ValueError:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE") from None
        if policy_sha256.hex() != digest:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        events = list(session.scalars(select(OutboxEventRow).where(
            OutboxEventRow.owner_module == "ai",
            OutboxEventRow.event_type == "AI_PROVIDER_TEST_REQUESTED",
            OutboxEventRow.idempotency_key == job.idempotency_key,
            OutboxEventRow.scope == "DEPLOYMENT", OutboxEventRow.project_id.is_(None),
            OutboxEventRow.aggregate_ref == provider_id,
        )))
        if len(events) != 1:
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        event = events[0]
        if (event.payload_refs != dict(payload, job_id=str(job.job_id))
                or event.trace_id != job.trace_id or type(event.aggregate_version) is not int
                or not 1 <= event.aggregate_version <= 2147483647):
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        return provider_id, config_id, event.aggregate_version, secret_version_id, policy_sha256

    def _claim(self, session, job: JobRow) -> AIProviderTestClaim:
        provider, config, version, secret, policy = self._snapshot(session, job)
        return AIProviderTestClaim(
            job.job_id, provider, config, version, secret, job.actor_ref,
            _uuid(job.trace_id), policy, job.fencing_token, job.attempt_count,
        )

    def claim_next(self, transaction: object, *, worker_ref: str,
                   lease_seconds: int) -> AIProviderTestClaim | None:
        session = self._leases._session(transaction)
        connection = session.connection()
        if connection.dialect.name != "postgresql" or connection.get_isolation_level() != "READ COMMITTED":
            raise JobLeaseError("JOB_STORE_UNAVAILABLE")
        now = self._leases._now(session)
        job = session.scalar(select(JobRow).where(
            JobRow.owner_module == "ai", JobRow.job_type == "AI_PROVIDER_TEST",
            JobRow.scope == "DEPLOYMENT", JobRow.project_id.is_(None),
            JobRow.max_attempts == 3, JobRow.attempt_count < JobRow.max_attempts,
            or_(
                and_(JobRow.state.in_(("PENDING", "RETRY_WAIT")), JobRow.available_at <= now),
                and_(JobRow.state == "RUNNING", JobRow.lease_expires_at <= now),
            ),
        ).order_by(JobRow.priority.desc(), JobRow.available_at, JobRow.job_id)
            .limit(1).with_for_update(of=JobRow, skip_locked=True)
            .execution_options(populate_existing=True))
        if job is None:
            return None
        self._snapshot(session, job)
        if (job.completed_at is not None or job.fencing_token >= 9223372036854775807
                or job.attempt_count < 0 or job.attempt_count != job.fencing_token):
            raise JobLeaseError("INCONSISTENT_LEASE")
        if job.state == "RUNNING":
            prior = self._leases._lease(session, job.job_id, job.fencing_token)
            attempt = self._leases._attempt(session, job.job_id, job.fencing_token)
            if (job.lease_expires_at is None or prior.lease_expires_at != job.lease_expires_at
                    or prior.lease_expires_at > now or attempt.attempt_no != job.attempt_count
                    or attempt.worker_ref != prior.worker_ref or attempt.completed_at is not None
                    or attempt.error_code is not None):
                raise JobLeaseError("INCONSISTENT_LEASE")
            prior.state = "EXPIRED"
            attempt.completed_at = now
            attempt.error_code = "LEASE_EXPIRED"
            session.flush()
        else:
            if (job.lease_expires_at is not None
                    or session.scalar(select(JobLeaseRow.lease_id).where(
                        JobLeaseRow.job_id == job.job_id,
                        JobLeaseRow.state == "ACTIVE",
                    )) is not None
                    or job.state == "PENDING" and job.attempt_count != 0):
                raise JobLeaseError("INCONSISTENT_LEASE")
        job.attempt_count += 1
        job.fencing_token += 1
        job.state = "RUNNING"
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        session.add(JobLeaseRow(job_id=job.job_id, worker_ref=worker_ref,
                                fencing_token=job.fencing_token,
                                lease_expires_at=job.lease_expires_at))
        session.add(JobAttemptRow(job_id=job.job_id, attempt_no=job.attempt_count,
                                  worker_ref=worker_ref, fencing_token=job.fencing_token))
        session.flush()
        return self._claim(session, job)

    def check_current(self, transaction: object, *, job_id: uuid.UUID,
                      fencing_token: int, worker_ref: str) -> AIProviderTestClaim:
        current = self._leases.check_current(
            transaction, job_id=job_id, fencing_token=fencing_token, worker_ref=worker_ref,
        )
        if current.job_type != "AI_PROVIDER_TEST" or current.scope != "DEPLOYMENT":
            raise JobLeaseError("STALE_LEASE")
        session = self._leases._session(transaction)
        job = session.get(JobRow, job_id)
        if job is None:
            raise JobLeaseError("STALE_LEASE")
        return self._claim(session, job)
