"""Job-owned durable enqueue; no document table access or autonomous commit."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from plm_assistant.modules.jobs.application.parse_enqueue import (
    ParseEnqueueError, ParseJobRef, ParseJobRequest,ParseJobBinding,_validate_read_request,
)
from plm_assistant.modules.jobs.infrastructure.orm import JobRow, OutboxEventRow


class SqlAlchemyParseJobQueueRepository:
    @staticmethod
    def _uuid(value):
        if type(value) is not str:raise ParseEnqueueError('CONFLICT_STATE')
        try:result=uuid.UUID(value)
        except ValueError:raise ParseEnqueueError('CONFLICT_STATE') from None
        if not result.int or str(result)!=value:raise ParseEnqueueError('CONFLICT_STATE')
        return result

    def _binding(self,session,job,*,lock):
        if (job.owner_module,job.job_type)!=('document','DOCUMENT_PARSE'):return None
        if type(job.payload_refs) is not dict or set(job.payload_refs)!={'document_id','document_version_id'}:
            raise ParseEnqueueError('CONFLICT_STATE')
        upload=self._uuid(job.idempotency_key)
        document=self._uuid(job.payload_refs['document_id']);version=self._uuid(job.payload_refs['document_version_id'])
        trace=self._uuid(job.trace_id)
        query=select(OutboxEventRow).where(OutboxEventRow.owner_module=='document',OutboxEventRow.event_type=='DOCUMENT_VERSION_COMMITTED',
            OutboxEventRow.scope==job.scope,OutboxEventRow.project_id==job.project_id,OutboxEventRow.idempotency_key==job.idempotency_key)
        if lock:query=query.with_for_update(of=OutboxEventRow).execution_options(populate_existing=True)
        event=session.execute(query).scalar_one_or_none()
        if (event is None or event.aggregate_ref!=version or event.trace_id!=job.trace_id
            or event.payload_refs!={'job_id':str(job.job_id),'document_version_id':str(version)}):
            raise ParseEnqueueError('CONFLICT_STATE')
        request=ParseJobRequest(upload,document,version,event.aggregate_version,job.scope,job.project_id,job.actor_ref,trace)
        return ParseJobBinding(request,ParseJobRef(job.job_id,event.event_id))

    def peek_parse_for_job(self,transaction,*,job_id):
        if type(job_id) is not uuid.UUID or not job_id.int:raise ParseEnqueueError('VALIDATION_FAILED')
        session=self._session(transaction)
        job=session.execute(select(JobRow).where(JobRow.job_id==job_id)).scalar_one_or_none()
        return None if job is None else self._binding(session,job,lock=False)

    def find_parse(self,transaction,*,request):
        _validate_read_request(request);session=self._session(transaction)
        job=session.execute(select(JobRow).where(JobRow.owner_module=='document',JobRow.job_type=='DOCUMENT_PARSE',
            JobRow.scope==request.scope,JobRow.project_id==request.project_id,JobRow.idempotency_key==str(request.upload_id))
            .with_for_update(of=JobRow).execution_options(populate_existing=True)).scalar_one_or_none()
        if job is None:return None
        binding=self._binding(session,job,lock=True)
        if binding.request!=request:raise ParseEnqueueError('CONFLICT_STATE')
        return binding.refs

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
                    or event.aggregate_ref != request.document_version_id
                    or event.aggregate_version != request.version_no
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
