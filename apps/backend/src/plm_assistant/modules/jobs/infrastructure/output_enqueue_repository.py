"""Jobs-owned Output Job/Outbox writes in caller transaction."""
from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from plm_assistant.modules.jobs.infrastructure.orm import JobRow,OutboxEventRow
class SqlAlchemyOutputJobQueueRepository:
    def enqueue_output(self,transaction:object,*,project_id:uuid.UUID,output_request_id:uuid.UUID,
        context_snapshot_id:uuid.UUID,actor_id:uuid.UUID,trace_id:uuid.UUID)->uuid.UUID:
        session=self._session(transaction);job_id,event_id=uuid.uuid4(),uuid.uuid4();key=str(output_request_id)
        session.add(JobRow(job_id=job_id,owner_module="output",job_type="OUTPUT_GENERATE",
            scope="PROJECT",project_id=project_id,actor_ref=actor_id,trace_id=str(trace_id),
            payload_refs={"output_request_id":str(output_request_id),
                          "context_snapshot_id":str(context_snapshot_id)},
            idempotency_key=key,max_attempts=3))
        session.add(OutboxEventRow(event_id=event_id,event_type="OUTPUT_REQUESTED",
            owner_module="output",scope="PROJECT",project_id=project_id,
            aggregate_ref=output_request_id,aggregate_version=1,
            payload_refs={"job_id":str(job_id),"output_request_id":str(output_request_id)},
            idempotency_key=key,trace_id=str(trace_id)))
        session.flush();return job_id
    @staticmethod
    def _session(transaction:object)->Session:
        try:session=transaction.session
        except (AttributeError,RuntimeError):raise RuntimeError("JOB_STORE_UNAVAILABLE") from None
        if not isinstance(session,Session) or not session.in_transaction():
            raise RuntimeError("JOB_STORE_UNAVAILABLE")
        return session
