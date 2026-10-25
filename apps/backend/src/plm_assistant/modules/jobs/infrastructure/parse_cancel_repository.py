"""Jobs-owned Parser cancellation state and immutable first response version."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select

from plm_assistant.modules.jobs.application.parse_enqueue import ParseJobBinding
from plm_assistant.modules.jobs.infrastructure.lease_repository import SqlAlchemyJobLeaseRepository
from plm_assistant.modules.jobs.infrastructure.orm import JobLeaseRow, JobRow, parse_cancel_versions
from plm_assistant.modules.jobs.infrastructure.parse_enqueue_repository import SqlAlchemyParseJobQueueRepository


class ParseCancelStoreError(RuntimeError):
    def __init__(self, code="JOB_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ParseCancelFacts:
    job_id: UUID
    state: str
    requested_by: UUID | None
    requested_at: datetime | None
    reason: str | None = field(repr=False)
    lock_version: int = 0

    def __post_init__(self):
        if (type(self.job_id) is not UUID or not self.job_id.int
                or self.state not in {"PENDING", "RUNNING", "RETRY_WAIT", "CANCEL_REQUESTED",
                                      "CANCELLED", "SUCCEEDED", "FAILED"}
                or type(self.lock_version) is not int or not 0 <= self.lock_version <= 2**63-1):
            raise ParseCancelStoreError()
        history = (self.requested_by, self.requested_at, self.reason)
        if all(value is None for value in history):
            if self.state in {"CANCEL_REQUESTED", "CANCELLED"}:
                raise ParseCancelStoreError()
        elif (type(self.requested_by) is not UUID or not self.requested_by.int
              or type(self.requested_at) is not datetime or self.requested_at.tzinfo is None
              or self.requested_at.utcoffset() is None
              or type(self.reason) is not str or not self.reason
              or self.state not in {"CANCEL_REQUESTED", "CANCELLED"}):
            raise ParseCancelStoreError()


@dataclass(frozen=True, slots=True)
class ParseCancelMutation:
    job_id: UUID
    state: str
    changed: bool

    def __post_init__(self):
        if (type(self.job_id) is not UUID or not self.job_id.int
                or self.state not in {"CANCEL_REQUESTED", "CANCELLED", "SUCCEEDED", "FAILED"}
                or type(self.changed) is not bool
                or self.changed and self.state in {"SUCCEEDED", "FAILED"}):
            raise ParseCancelStoreError()


class SqlAlchemyParseCancellationRepository:
    def __init__(self):
        self._queue = SqlAlchemyParseJobQueueRepository()
        self._leases = SqlAlchemyJobLeaseRepository()

    def _job(self, tx, binding):
        if type(binding) is not ParseJobBinding:
            raise ParseCancelStoreError("VALIDATION_FAILED")
        binding.__post_init__()
        if self._queue.find_parse(tx, request=binding.request) != binding.refs:
            raise ParseCancelStoreError("RESOURCE_NOT_FOUND")
        session = self._leases._session(tx)
        job = session.scalar(select(JobRow).where(JobRow.job_id == binding.refs.job_id)
                             .with_for_update(of=JobRow).execution_options(populate_existing=True))
        if job is None or (job.owner_module, job.job_type, job.scope, job.project_id, job.actor_ref) != (
                "document", "DOCUMENT_PARSE", "PROJECT", binding.request.project_id,
                binding.request.actor_id):
            raise ParseCancelStoreError("RESOURCE_NOT_FOUND")
        return session, job

    def read_facts(self, tx, *, binding):
        _, job = self._job(tx, binding)
        return ParseCancelFacts(job.job_id, job.state, job.cancel_requested_by,
                                job.cancel_requested_at, job.cancel_reason, job.lock_version)

    def request_cancel(self, tx, *, binding, requested_by, reason):
        session, job = self._job(tx, binding)
        if type(requested_by) is not UUID or not requested_by.int or type(reason) is not str:
            raise ParseCancelStoreError("VALIDATION_FAILED")
        if job.state in {"SUCCEEDED", "FAILED"}:
            return ParseCancelMutation(job.job_id, job.state, False)
        if job.state in {"CANCEL_REQUESTED", "CANCELLED"}:
            if any(v is None for v in (job.cancel_requested_by, job.cancel_requested_at, job.cancel_reason)):
                raise ParseCancelStoreError("CONFLICT_STATE")
            return ParseCancelMutation(job.job_id, job.state, False)
        if job.state not in {"PENDING", "RETRY_WAIT", "RUNNING"}:
            raise ParseCancelStoreError("CONFLICT_STATE")
        now = self._leases._now(session)
        if job.state == "RUNNING":
            try:
                lease = self._leases._lease(session, job.job_id, job.fencing_token)
                attempt = self._leases._attempt(session, job.job_id, job.fencing_token)
            except Exception:
                raise ParseCancelStoreError("CONFLICT_STATE") from None
            if (job.completed_at is not None or job.lease_expires_at is None
                    or job.lease_expires_at != lease.lease_expires_at
                    or lease.state != "ACTIVE" or attempt.completed_at is not None
                    or attempt.worker_ref != lease.worker_ref
                    or attempt.attempt_no != job.attempt_count):
                raise ParseCancelStoreError("CONFLICT_STATE")
        elif (job.lease_expires_at is not None or job.completed_at is not None
              or session.scalar(select(JobLeaseRow.lease_id).where(
                  JobLeaseRow.job_id == job.job_id, JobLeaseRow.state == "ACTIVE"
              ).with_for_update(of=JobLeaseRow)) is not None):
            raise ParseCancelStoreError("CONFLICT_STATE")
        immediate = job.state != "RUNNING"
        job.cancel_requested_by = requested_by
        job.cancel_requested_at = now
        job.cancel_reason = reason
        job.state = "CANCEL_REQUESTED"
        session.flush()
        if immediate:
            job.state = "CANCELLED"
            job.completed_at = now
            session.flush()
        return ParseCancelMutation(job.job_id, job.state, True)

    def record_version(self, tx, *, event_id, lock_version):
        if (type(event_id) is not UUID or not event_id.int
                or type(lock_version) is not int or not 0 <= lock_version <= 2**63-1):
            raise ParseCancelStoreError("VALIDATION_FAILED")
        self._leases._session(tx).execute(insert(parse_cancel_versions).values(
            audit_event_id=event_id, lock_version=lock_version))

    def receipt_version(self, tx, *, event_id):
        if type(event_id) is not UUID or not event_id.int:
            raise ParseCancelStoreError("VALIDATION_FAILED")
        value = self._leases._session(tx).scalar(select(parse_cancel_versions.c.lock_version)
                                                  .where(parse_cancel_versions.c.audit_event_id == event_id))
        if type(value) is not int or not 0 <= value <= 2**63-1:
            raise ParseCancelStoreError()
        return value
