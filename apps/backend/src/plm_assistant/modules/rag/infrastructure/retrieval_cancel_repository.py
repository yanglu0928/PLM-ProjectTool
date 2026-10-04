"""PostgreSQL state Owner for atomic Retrieval cancellation."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text

from plm_assistant.modules.audit.infrastructure.audit_orm import AuditEventRow
from plm_assistant.modules.jobs.infrastructure.orm import (
    JobAttemptRow,
    JobLeaseRow,
    JobRow,
)
from plm_assistant.modules.rag.application.retrieval_cancel import (
    CancelledRAGRetrieval,
    RAGRetrievalCancelBinding,
    RAGRetrievalCancelError,
    ReconciledRAGRetrievalCancel,
)
from plm_assistant.modules.rag.infrastructure.orm import RetrievalRunRow
from plm_assistant.modules.rag.infrastructure.retrieval_create_repository import _session


_CONSTRAINTS = (
    "plm.trg_rag_retrieval_run_terminal_complete,"
    "plm.trg_rag_retrieval_job_terminal_complete,"
    "plm.trg_rag_retrieval_candidate_terminal_complete,"
    "plm.trg_rag_retrieval_score_terminal_complete,"
    "plm.trg_rag_context_bundle_terminal_complete,"
    "plm.trg_rag_context_item_terminal_complete"
)


class SqlAlchemyRAGRetrievalCancellationRepository:
    def binding_for_job(self, transaction: object, *, job_id: uuid.UUID,
                        project_id: uuid.UUID
                        ) -> RAGRetrievalCancelBinding | None:
        if not self._ids(job_id, project_id):
            raise RAGRetrievalCancelError("VALIDATION_FAILED")
        session = _session(transaction)
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == job_id,
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        if job is None:
            return None
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.job_id == job_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(
            populate_existing=True,
        ))
        return self._binding(job, run, project_id)

    def binding_for_run(self, transaction: object, *,
                        retrieval_run_id: uuid.UUID, project_id: uuid.UUID
                        ) -> RAGRetrievalCancelBinding | None:
        if not self._ids(retrieval_run_id, project_id):
            raise RAGRetrievalCancelError("VALIDATION_FAILED")
        session = _session(transaction)
        job_id = session.scalar(select(RetrievalRunRow.job_id).where(
            RetrievalRunRow.retrieval_run_id == retrieval_run_id,
            RetrievalRunRow.project_id == project_id,
        ).execution_options(autoflush=False))
        if type(job_id) is not uuid.UUID:
            return None
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == job_id,
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.retrieval_run_id == retrieval_run_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(
            populate_existing=True,
        ))
        return self._binding(job, run, project_id)

    @staticmethod
    def _ids(*values: object) -> bool:
        return all(type(value) is uuid.UUID and bool(value.int)
                   for value in values)

    @staticmethod
    def _binding(job, run, project_id: uuid.UUID
                 ) -> RAGRetrievalCancelBinding | None:
        if (job is None or run is None
                or (job.owner_module, job.job_type, job.scope, job.project_id)
                != ("rag", "RAG_RETRIEVAL", "PROJECT", project_id)
                or (run.scope, run.project_id, run.job_id)
                != ("PROJECT", project_id, job.job_id)
                or job.actor_ref != run.actor_ref
                or job.trace_id != str(run.trace_id)
                or job.payload_refs != {
                    "retrieval_run_id": str(run.retrieval_run_id),
                }
                or job.max_attempts != 1):
            return None
        valid_pair = (
            job.state in {"PENDING", "RUNNING", "CANCEL_REQUESTED"}
            and run.retrieval_state == "RUNNING"
        ) or (
            job.state in {"CANCELLED", "SUCCEEDED", "FAILED"}
            and run.retrieval_state == job.state
        )
        if not valid_pair:
            raise RAGRetrievalCancelError()
        try:
            trace_id = uuid.UUID(job.trace_id)
        except (TypeError, ValueError):
            raise RAGRetrievalCancelError() from None
        return RAGRetrievalCancelBinding(
            run.retrieval_run_id, job.job_id, project_id, run.actor_ref,
            trace_id, run.retrieval_state, job.state,
            run.lock_version, job.lock_version,
        )

    def request_cancel(self, transaction: object, *,
                       binding: RAGRetrievalCancelBinding,
                       requested_by: uuid.UUID,
                       reason: str) -> CancelledRAGRetrieval:
        binding.__post_init__()
        if (type(requested_by) is not uuid.UUID or not requested_by.int
                or type(reason) is not str or not reason):
            raise RAGRetrievalCancelError("VALIDATION_FAILED")
        session = _session(transaction)
        current = self.binding_for_job(
            transaction, job_id=binding.job_id,
            project_id=binding.project_id,
        )
        if current != binding:
            raise RAGRetrievalCancelError("CONFLICT_VERSION")
        job = session.get(JobRow, binding.job_id, populate_existing=True)
        run = session.get(
            RetrievalRunRow, binding.retrieval_run_id,
            populate_existing=True,
        )
        if job is None or run is None:
            raise RAGRetrievalCancelError("RESOURCE_NOT_FOUND")
        if job.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            self._validate_cancel_history(job)
            return self._result(job, run, changed=False)
        if job.state == "CANCEL_REQUESTED":
            self._validate_cancel_history(job)
            return self._result(job, run, changed=False)
        if job.state not in {"PENDING", "RUNNING"}:
            raise RAGRetrievalCancelError("CONFLICT_STATE")
        now = session.scalar(select(func.clock_timestamp()))
        if now is None:
            raise RAGRetrievalCancelError()
        if job.state == "PENDING":
            if (job.attempt_count != 0 or job.fencing_token != 0
                    or job.lease_expires_at is not None
                    or session.scalar(select(JobLeaseRow.lease_id).where(
                        JobLeaseRow.job_id == job.job_id,
                    ).limit(1)) is not None
                    or session.scalar(select(JobAttemptRow.attempt_id).where(
                        JobAttemptRow.job_id == job.job_id,
                    ).limit(1)) is not None):
                raise RAGRetrievalCancelError("CONFLICT_STATE")
            job.cancel_requested_by = requested_by
            job.cancel_requested_at = now
            job.cancel_reason = reason
            job.state = "CANCEL_REQUESTED"
            session.flush()
            job.state = "CANCELLED"
            job.completed_at = now
            run.retrieval_state = "CANCELLED"
            run.rerank_state = "NOT_APPLICABLE"
            run.egress_state = "NOT_APPLICABLE"
            run.quality_flags = []
            run.degraded = False
            run.error_code = None
            run.completed_at = now
            run.lock_version = 1
            session.flush()
            self._validate_constraints(session)
            session.refresh(job, attribute_names=(
                "state", "lock_version", "completed_at", "lease_expires_at",
            ))
            return self._result(job, run, changed=True)
        lease = session.scalar(select(JobLeaseRow).where(
            JobLeaseRow.job_id == job.job_id,
            JobLeaseRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobLeaseRow).execution_options(populate_existing=True))
        attempt = session.scalar(select(JobAttemptRow).where(
            JobAttemptRow.job_id == job.job_id,
            JobAttemptRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
        if (job.attempt_count != 1 or job.fencing_token != 1
                or job.lease_expires_at is None or lease is None or attempt is None
                or lease.state != "ACTIVE"
                or lease.lease_expires_at != job.lease_expires_at
                or attempt.attempt_no != 1 or attempt.worker_ref != lease.worker_ref
                or attempt.completed_at is not None
                or attempt.error_code is not None):
            raise RAGRetrievalCancelError("CONFLICT_STATE")
        job.cancel_requested_by = requested_by
        job.cancel_requested_at = now
        job.cancel_reason = reason
        job.state = "CANCEL_REQUESTED"
        session.flush()
        session.refresh(job, attribute_names=(
            "state", "lock_version", "completed_at", "lease_expires_at",
        ))
        return self._result(job, run, changed=True)

    @staticmethod
    def _validate_cancel_history(job) -> None:
        values = (
            job.cancel_requested_by, job.cancel_requested_at,
            job.cancel_reason,
        )
        if job.state in {"CANCEL_REQUESTED", "CANCELLED"}:
            if any(value is None for value in values):
                raise RAGRetrievalCancelError()
        elif any(value is not None for value in values):
            raise RAGRetrievalCancelError()

    @staticmethod
    def _result(job, run, *, changed: bool) -> CancelledRAGRetrieval:
        return CancelledRAGRetrieval(
            run.retrieval_run_id, job.job_id, run.project_id, job.state,
            changed, run.lock_version, job.lock_version, job.completed_at,
        )

    def receipt(self, transaction: object, *,
                binding: RAGRetrievalCancelBinding, actor_id: uuid.UUID,
                audit_event_id: uuid.UUID) -> CancelledRAGRetrieval:
        if not self._ids(actor_id, audit_event_id):
            raise RAGRetrievalCancelError("VALIDATION_FAILED")
        session = _session(transaction)
        event = session.scalar(select(AuditEventRow).where(
            AuditEventRow.audit_event_id == audit_event_id,
            AuditEventRow.event_scope == "PROJECT",
            AuditEventRow.target_project_id == binding.project_id,
            AuditEventRow.actor_type == "USER",
            AuditEventRow.actor_id == actor_id,
            AuditEventRow.original_actor_id.is_(None),
            AuditEventRow.action.in_((
                "RAG_RETRIEVAL_CANCEL_REQUESTED",
                "RAG_RETRIEVAL_CANCELLED",
                "RAG_RETRIEVAL_CANCEL_CHECKED",
            )),
            AuditEventRow.outcome == "SUCCESS",
            AuditEventRow.target_owner_module == "rag",
            AuditEventRow.target_object_type == "RAG-04",
            AuditEventRow.target_object_id == binding.retrieval_run_id,
            AuditEventRow.reason_code == "USER_REQUESTED",
        ))
        if event is None:
            raise RAGRetrievalCancelError()
        changed = event.action != "RAG_RETRIEVAL_CANCEL_CHECKED"
        state = event.after_state
        if state == "CANCEL_REQUESTED":
            run_version, job_version, completed = 0, 2, None
        elif state == "CANCELLED":
            current = self.binding_for_job(
                transaction, job_id=binding.job_id,
                project_id=binding.project_id,
            )
            if current is None or current.job_state != "CANCELLED":
                raise RAGRetrievalCancelError()
            run_version, completed = 1, session.get(
                JobRow, binding.job_id, populate_existing=True,
            ).completed_at
            job_version = (2 if event.before_state == "PENDING"
                           else current.job_lock_version)
        elif state in {"SUCCEEDED", "FAILED"}:
            current = self.binding_for_job(
                transaction, job_id=binding.job_id,
                project_id=binding.project_id,
            )
            if current is None or current.job_state != state:
                raise RAGRetrievalCancelError()
            row = session.get(JobRow, binding.job_id, populate_existing=True)
            run_version, job_version = 1, current.job_lock_version
            completed = row.completed_at
        else:
            raise RAGRetrievalCancelError()
        return CancelledRAGRetrieval(
            binding.retrieval_run_id, binding.job_id, binding.project_id,
            state, changed, run_version, job_version, completed,
        )

    def reconcile_current(self, transaction: object, *, job_id: uuid.UUID,
                          fencing_token: int,
                          worker_ref: str) -> ReconciledRAGRetrievalCancel:
        session = _session(transaction)
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == job_id,
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        return self._reconcile(
            session, job=job, now=now, expired=False,
            fencing_token=fencing_token, worker_ref=worker_ref,
        )

    def reconcile_current_if_requested(
        self, transaction: object, *, job_id: uuid.UUID,
        fencing_token: int, worker_ref: str,
    ) -> ReconciledRAGRetrievalCancel | None:
        session = _session(transaction)
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(JobRow).where(
            JobRow.job_id == job_id,
            JobRow.owner_module == "rag",
            JobRow.job_type == "RAG_RETRIEVAL",
            JobRow.scope == "PROJECT",
        ).with_for_update(of=JobRow).execution_options(populate_existing=True))
        if job is None:
            raise RAGRetrievalCancelError("STALE_LEASE")
        if job.state != "CANCEL_REQUESTED":
            return None
        return self._reconcile(
            session, job=job, now=now, expired=False,
            fencing_token=fencing_token, worker_ref=worker_ref,
        )

    def reconcile_expired_next(self, transaction: object
                               ) -> ReconciledRAGRetrievalCancel | None:
        session = _session(transaction)
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(JobRow).where(
            JobRow.owner_module == "rag",
            JobRow.job_type == "RAG_RETRIEVAL",
            JobRow.scope == "PROJECT",
            JobRow.state == "CANCEL_REQUESTED",
            JobRow.lease_expires_at.is_not(None),
            JobRow.lease_expires_at <= now,
        ).order_by(JobRow.lease_expires_at, JobRow.job_id).limit(1)
            .with_for_update(of=JobRow, skip_locked=True)
            .execution_options(populate_existing=True))
        if job is None:
            return None
        return self._reconcile(
            session, job=job, now=now, expired=True,
            fencing_token=job.fencing_token, worker_ref=None,
        )

    def _reconcile(self, session, *, job, now, expired: bool,
                   fencing_token: int, worker_ref: str | None
                   ) -> ReconciledRAGRetrievalCancel:
        if job is None or now is None:
            raise RAGRetrievalCancelError("STALE_LEASE")
        lease = session.scalar(select(JobLeaseRow).where(
            JobLeaseRow.job_id == job.job_id,
            JobLeaseRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobLeaseRow).execution_options(populate_existing=True))
        attempt = session.scalar(select(JobAttemptRow).where(
            JobAttemptRow.job_id == job.job_id,
            JobAttemptRow.fencing_token == job.fencing_token,
        ).with_for_update(of=JobAttemptRow).execution_options(populate_existing=True))
        run = session.scalar(select(RetrievalRunRow).where(
            RetrievalRunRow.job_id == job.job_id,
        ).with_for_update(of=RetrievalRunRow).execution_options(populate_existing=True))
        if (lease is None or attempt is None or run is None
                or (job.owner_module, job.job_type, job.scope)
                != ("rag", "RAG_RETRIEVAL", "PROJECT")
                or job.state != "CANCEL_REQUESTED"
                or job.lock_version != 2 or job.max_attempts != 1
                or job.attempt_count != 1 or job.fencing_token != 1
                or job.fencing_token != fencing_token
                or job.completed_at is not None
                or any(value is None for value in (
                    job.cancel_requested_by, job.cancel_requested_at,
                    job.cancel_reason,
                ))
                or lease.state != "ACTIVE"
                or lease.lease_expires_at != job.lease_expires_at
                or attempt.attempt_no != 1
                or attempt.worker_ref != lease.worker_ref
                or attempt.completed_at is not None
                or attempt.error_code is not None
                or run.retrieval_state != "RUNNING"
                or run.lock_version != 0 or run.project_id != job.project_id
                or run.actor_ref != job.actor_ref
                or str(run.trace_id) != job.trace_id
                or job.payload_refs != {
                    "retrieval_run_id": str(run.retrieval_run_id),
                }):
            raise RAGRetrievalCancelError("STALE_LEASE")
        if expired:
            if lease.lease_expires_at > now:
                raise RAGRetrievalCancelError("STALE_LEASE")
            lease.state = "EXPIRED"
        else:
            if (worker_ref != lease.worker_ref
                    or lease.lease_expires_at <= now):
                raise RAGRetrievalCancelError("STALE_LEASE")
            lease.state = "RELEASED"
        attempt.completed_at = now
        attempt.error_code = "JOB_CANCELLED"
        job.state = "CANCELLED"
        job.lease_expires_at = None
        job.completed_at = now
        run.retrieval_state = "CANCELLED"
        run.rerank_state = "NOT_APPLICABLE"
        run.egress_state = "NOT_APPLICABLE"
        run.quality_flags = []
        run.degraded = False
        run.error_code = None
        run.completed_at = now
        run.lock_version = 1
        session.flush()
        self._validate_constraints(session)
        try:
            trace_id = uuid.UUID(job.trace_id)
        except (TypeError, ValueError):
            raise RAGRetrievalCancelError() from None
        return ReconciledRAGRetrievalCancel(
            run.retrieval_run_id, job.job_id, job.project_id, job.actor_ref,
            trace_id, lease.state, now,
        )

    @staticmethod
    def _validate_constraints(session) -> None:
        session.execute(text(f"SET CONSTRAINTS {_CONSTRAINTS} IMMEDIATE"))
        session.execute(text(f"SET CONSTRAINTS {_CONSTRAINTS} DEFERRED"))
