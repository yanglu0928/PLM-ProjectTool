"""PostgreSQL same-transaction Provider Test Job/Outbox pair."""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.ai_provider_test_enqueue import (
    AIProviderTestEnqueueError, AIProviderTestJobRef, AIProviderTestJobRequest,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow


def _lock_key(submission_id) -> int:
    digest = hashlib.sha256(b"PLM-AI-PROVIDER-TEST-ENQUEUE-V1\x00" + submission_id.bytes).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def _payload(request: AIProviderTestJobRequest) -> dict[str, str]:
    return {
        "provider_id": str(request.provider_id),
        "config_id": str(request.config_id),
        "secret_version_id": str(request.secret_version_id),
        "policy_sha256": request.policy_sha256.hex(),
        "probe_id": request.probe_id,
    }


class SqlAlchemyAIProviderTestJobQueueRepository:
    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise AIProviderTestEnqueueError() from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise AIProviderTestEnqueueError()
        connection = session.connection()
        if connection.dialect.name != "postgresql" or connection.get_isolation_level() != "READ COMMITTED":
            raise AIProviderTestEnqueueError()
        return session

    def _pair(self, transaction: object, request: AIProviderTestJobRequest) -> tuple[Session, AIProviderTestJobRef | None]:
        if type(request) is not AIProviderTestJobRequest:
            raise AIProviderTestEnqueueError("VALIDATION_FAILED")
        request.__post_init__()
        session = self._session(transaction)
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": _lock_key(request.submission_id)})
        key = str(request.submission_id)
        jobs = list(session.scalars(select(JobRow).where(
            JobRow.owner_module == "ai", JobRow.job_type == "AI_PROVIDER_TEST",
            JobRow.idempotency_key == key,
        ).with_for_update(of=JobRow)))
        events = list(session.scalars(select(OutboxEventRow).where(
            OutboxEventRow.owner_module == "ai", OutboxEventRow.event_type == "AI_PROVIDER_TEST_REQUESTED",
            OutboxEventRow.idempotency_key == key,
        ).with_for_update(of=OutboxEventRow)))
        if not jobs and not events:
            return session, None
        if len(jobs) != 1 or len(events) != 1:
            raise AIProviderTestEnqueueError("CONFLICT_STATE")
        job, event = jobs[0], events[0]
        payload = _payload(request)
        if ((job.scope, job.project_id, job.actor_ref, job.trace_id, job.payload_refs,
             job.max_attempts) != ("DEPLOYMENT", None, request.actor_id, str(request.trace_id), payload, 3)
                or (event.scope, event.project_id, event.aggregate_ref, event.aggregate_version,
                    event.trace_id, event.payload_refs, event.max_attempts) != (
                    "DEPLOYMENT", None, request.provider_id, request.config_version,
                    str(request.trace_id), dict(payload, job_id=str(job.job_id)), 5)):
            raise AIProviderTestEnqueueError("CONFLICT_STATE")
        return session, AIProviderTestJobRef(job.job_id, event.event_id)

    def find(self, transaction: object, *, request: AIProviderTestJobRequest) -> AIProviderTestJobRef | None:
        return self._pair(transaction, request)[1]

    def find_by_job(self, transaction: object, *, job_id, provider_id, actor_id) -> AIProviderTestJobRef | None:
        session = self._session(transaction)
        job = session.execute(select(JobRow).where(
            JobRow.job_id == job_id, JobRow.owner_module == "ai",
            JobRow.job_type == "AI_PROVIDER_TEST", JobRow.scope == "DEPLOYMENT",
            JobRow.project_id.is_(None), JobRow.actor_ref == actor_id,
        )).scalar_one_or_none()
        if job is None:
            return None
        events = list(session.scalars(select(OutboxEventRow).where(
            OutboxEventRow.owner_module == "ai",
            OutboxEventRow.event_type == "AI_PROVIDER_TEST_REQUESTED",
            OutboxEventRow.idempotency_key == job.idempotency_key,
            OutboxEventRow.scope == "DEPLOYMENT", OutboxEventRow.project_id.is_(None),
            OutboxEventRow.aggregate_ref == provider_id,
        )))
        if (len(events) != 1 or job.payload_refs.get("provider_id") != str(provider_id)
                or job.payload_refs.get("probe_id") != "CHAT_CONNECTIVITY_V1"
                or not all(key in job.payload_refs for key in (
                    "config_id", "secret_version_id", "policy_sha256"))):
            raise AIProviderTestEnqueueError("CONFLICT_STATE")
        event = events[0]
        if (event.payload_refs != dict(job.payload_refs, job_id=str(job.job_id))
                or event.trace_id != job.trace_id or event.aggregate_version < 1):
            raise AIProviderTestEnqueueError("CONFLICT_STATE")
        return AIProviderTestJobRef(job.job_id, event.event_id)

    def enqueue(self, transaction: object, *, request: AIProviderTestJobRequest) -> AIProviderTestJobRef:
        session, existing = self._pair(transaction, request)
        if existing is not None:
            return existing
        job_id, event_id = session.execute(select(func.uuidv7(), func.uuidv7())).one()
        payload = _payload(request)
        key = str(request.submission_id)
        session.add(JobRow(
            job_id=job_id, owner_module="ai", job_type="AI_PROVIDER_TEST",
            scope="DEPLOYMENT", project_id=None, actor_ref=request.actor_id,
            trace_id=str(request.trace_id), payload_refs=payload,
            idempotency_key=key, max_attempts=3,
        ))
        session.add(OutboxEventRow(
            event_id=event_id, owner_module="ai", event_type="AI_PROVIDER_TEST_REQUESTED",
            scope="DEPLOYMENT", project_id=None, aggregate_ref=request.provider_id,
            aggregate_version=request.config_version, trace_id=str(request.trace_id),
            payload_refs=dict(payload, job_id=str(job_id)), idempotency_key=key,
            max_attempts=5,
        ))
        session.flush()
        return AIProviderTestJobRef(job_id, event_id)
