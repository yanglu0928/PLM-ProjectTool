"""Job owned pair persistence, no cross-module table access or own commit."""
import hashlib
from sqlalchemy import select,text,func
from sqlalchemy.orm import Session
from ..application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef,AuditExportEnqueueError
from .orm import JobRow,OutboxEventRow


def _lock_key(export_id):
    return int.from_bytes(hashlib.sha256(b"PLM-AUDIT-EXPORT-ENQUEUE-V1\x00"+export_id.bytes).digest()[:8],"big",signed=True)


class SqlAlchemyAuditExportJobQueueRepository:
    @staticmethod
    def _session(tx):
        try:session=tx.session
        except (AttributeError,RuntimeError):raise AuditExportEnqueueError("JOB_STORE_UNAVAILABLE") from None
        if not isinstance(session,Session) or not session.in_transaction():
            raise AuditExportEnqueueError("JOB_STORE_UNAVAILABLE")
        return session

    def _pair(self,tx,request):
        if type(request) is not AuditExportJobRequest:raise AuditExportEnqueueError("VALIDATION_FAILED")
        request.__post_init__()
        session=self._session(tx)
        connection=session.connection()
        if connection.dialect.name!="postgresql" or connection.get_isolation_level()!="READ COMMITTED":
            raise AuditExportEnqueueError("JOB_STORE_UNAVAILABLE")
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"),dict(lock_key=_lock_key(request.export_id)))
        key=str(request.export_id)
        # Deliberately find across scopes: the same Export must not fork to another project.
        jobs=list(session.scalars(select(JobRow).where(JobRow.owner_module=="audit",JobRow.job_type=="AUDIT_EXPORT",JobRow.idempotency_key==key).with_for_update(of=JobRow)))
        events=list(session.scalars(select(OutboxEventRow).where(OutboxEventRow.owner_module=="audit",OutboxEventRow.event_type=="AUDIT_EXPORT_REQUESTED",OutboxEventRow.idempotency_key==key).with_for_update(of=OutboxEventRow)))
        if not jobs and not events:return session,None
        if len(jobs)!=1 or len(events)!=1:raise AuditExportEnqueueError("CONFLICT_STATE")
        job,event=jobs[0],events[0]
        payload=dict(export_id=key,policy_version=request.policy_version)
        if ((job.scope,job.project_id,job.actor_ref,job.trace_id)!=(request.scope,request.project_id,request.actor_id,str(request.trace_id))
                or job.payload_refs!=payload or job.max_attempts!=3
                or (event.scope,event.project_id,event.aggregate_ref,event.aggregate_version,event.trace_id)!=(request.scope,request.project_id,request.export_id,1,str(request.trace_id))
                or event.payload_refs!=dict(payload,job_id=str(job.job_id)) or event.max_attempts!=5):
            raise AuditExportEnqueueError("CONFLICT_STATE")
        return session,AuditExportJobRef(job.job_id,event.event_id)

    def find_export(self,transaction,*,request):
        """No business row creation; locks live until caller transaction ends."""
        return self._pair(transaction,request)[1]

    def enqueue_export(self,transaction,*,request):
        session,existing=self._pair(transaction,request)
        if existing is not None:return existing
        job_id,event_id=session.execute(select(func.uuidv7(),func.uuidv7())).one()
        payload=dict(export_id=str(request.export_id),policy_version=request.policy_version)
        session.add(JobRow(job_id=job_id,owner_module="audit",job_type="AUDIT_EXPORT",scope=request.scope,project_id=request.project_id,
            actor_ref=request.actor_id,trace_id=str(request.trace_id),payload_refs=payload,idempotency_key=str(request.export_id),max_attempts=3))
        session.add(OutboxEventRow(event_id=event_id,owner_module="audit",event_type="AUDIT_EXPORT_REQUESTED",scope=request.scope,project_id=request.project_id,
            aggregate_ref=request.export_id,aggregate_version=1,trace_id=str(request.trace_id),payload_refs=dict(payload,job_id=str(job_id)),idempotency_key=str(request.export_id),max_attempts=5))
        session.flush()
        return AuditExportJobRef(job_id,event_id)
