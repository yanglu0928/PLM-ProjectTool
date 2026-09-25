"""Job-owned durable enqueue; no document table access or autonomous commit."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseEnqueueError, ParseJobRef, ParseJobRequest,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow


class SqlAlchemyParseJobQueueRepository:
    def enqueue_parse(self, transaction: object, *, request: ParseJobRequest) -> ParseJobRef:
        session = self._session(transaction)
        key = str(request.upload_id)
        payload = {
            "document_id": str(request.document_id),
            "document_version_id": str(request.document_version_id),
        }
        existing = session.execute(select(JobRow).where(
            JobRow.owner_module == "document",
            JobRow.scope == request.scope,
            JobRow.project_id == request.project_id,
            JobRow.job_type == "DOCUMENT_PARSE",
            JobRow.idempotency_key == key,
        ).with_for_update(of=JobRow)).scalar_one_or_none()
        if existing is not None:
            event = session.execute(select(OutboxEventRow).where(
                OutboxEventRow.owner_module == "document",
                OutboxEventRow.scope == request.scope,
                OutboxEventRow.project_id == request.project_id,
                OutboxEventRow.event_type == "DOCUMENT_VERSION_COMMITTED",
                OutboxEventRow.idempotency_key == key,
            ).with_for_update(of=OutboxEventRow)).scalar_one_or_none()
            if (event is None or existing.payload_refs != payload
                    or existing.actor_ref != request.actor_id
                    or existing.trace_id != str(request.trace_id)
                    or event.aggregate_ref != request.document_version_id
                    or event.aggregate_version != request.version_no
                    or event.trace_id != str(request.trace_id)
                    or event.payload_refs != {"job_id": str(existing.job_id),
                                              "document_version_id": str(request.document_version_id)}):
                raise ParseEnqueueError("CONFLICT_STATE")
            return ParseJobRef(existing.job_id, event.event_id)
        job_id, event_id = uuid.uuid4(), uuid.uuid4()
        session.add(JobRow(
            job_id=job_id, owner_module="document", job_type="DOCUMENT_PARSE",
            scope=request.scope, project_id=request.project_id,
            actor_ref=request.actor_id, trace_id=str(request.trace_id),
            payload_refs=payload, idempotency_key=key, max_attempts=3,
        ))
        session.add(OutboxEventRow(
            event_id=event_id, event_type="DOCUMENT_VERSION_COMMITTED",
            owner_module="document", scope=request.scope,
            project_id=request.project_id,
            aggregate_ref=request.document_version_id,
            aggregate_version=request.version_no,
            payload_refs={"job_id": str(job_id),
                          "document_version_id": str(request.document_version_id)},
            idempotency_key=key, trace_id=str(request.trace_id),
        ))
        session.flush()
        return ParseJobRef(job_id, event_id)

    @staticmethod
    def _session(transaction: object) -> Session:
        try:
            session = transaction.session  # type: ignore[attr-defined]
        except (AttributeError, RuntimeError):
            raise ParseEnqueueError("JOB_STORE_UNAVAILABLE") from None
        if not isinstance(session, Session) or not session.in_transaction():
            raise ParseEnqueueError("JOB_STORE_UNAVAILABLE")
        return session
