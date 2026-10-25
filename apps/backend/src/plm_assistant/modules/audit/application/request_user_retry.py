"""Current-authorized new generation, immutable original response and atomic receipt."""
from dataclasses import dataclass, field
from uuid import UUID
from .submit_export import AuditExportIntent, AcceptedAuditExport, AuditExportSubmitService
from .export_submit_authorization import AuditExportSubmitAuthorizationRequest, AuthorizedAuditExportSubmit, AuditExportSubmitAuthorizationError
from .user_retry_source import AuditUserRetrySource
from .retry_generation import AuditExportRetryGeneration
from .public import AuditEventDraft
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.jobs.application.lease import JobLeaseError
from plm_assistant.modules.platform.application.idempotency import IdempotencyScope, IdempotencyResult, IdempotencyError, validate_idempotency_key, canonical_payload_fingerprint

class AuditUserRetryError(RuntimeError):
    def __init__(self,code='AUDIT_UNAVAILABLE'):self.code=code;super().__init__(code)

@dataclass(frozen=True,slots=True)
class RequestAuditUserRetry:
    job_id: UUID
    scope: str
    project_id: UUID|None
    session_token: bytes=field(repr=False)
    csrf_token: bytes=field(repr=False)
    trace_id: UUID
    expected_version: int

    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.job_id,self.trace_id))
            or any(type(v) is not bytes or len(v)!=32 for v in (self.session_token,self.csrf_token))
            or type(self.scope) is not str or self.scope not in ('PROJECT','DEPLOYMENT')
            or self.scope=='PROJECT' and (type(self.project_id) is not UUID or not self.project_id.int)
            or self.scope=='DEPLOYMENT' and self.project_id is not None
            or type(self.expected_version) is not int or not 0<=self.expected_version<=9223372036854775807):
            raise AuditUserRetryError('VALIDATION_FAILED')

class AuditUserRetryService:
    def __init__(self,*,unit_of_work,repository,authorization,sources,generations,receipts,queue,audit):
        if any(v is None for v in (unit_of_work,repository,authorization,sources,generations,receipts,queue,audit)):
            raise ValueError('Actual user retry dependencies required')
        self._uow,self._repo,self._auth,self._sources,self._generations,self._receipts,self._queue,self._audit=unit_of_work,repository,authorization,sources,generations,receipts,queue,audit

    def retry(self,c,*,idempotency_key):
        if type(c) is not RequestAuditUserRetry:raise AuditUserRetryError('VALIDATION_FAILED')
        c.__post_init__()
        try:validate_idempotency_key(idempotency_key)
        except IdempotencyError as exc:raise AuditUserRetryError(exc.code) from None
        for attempt in range(3):
            try:return self._retry(c,idempotency_key)
            except Exception as exc:
                if self._repo.is_retryable_deadlock(exc) is True:
                    if attempt<2:continue
                    raise AuditUserRetryError() from None
                if isinstance(exc,AuditUserRetryError):raise
                if isinstance(exc,(IdempotencyError,AuditExportSubmitAuthorizationError)):
                    raise AuditUserRetryError(exc.code) from None
                if isinstance(exc,JobLeaseError):
                    code=exc.code if exc.code in ('VERSION_CONFLICT','JOB_NOT_RETRYABLE','RESOURCE_NOT_FOUND','VALIDATION_FAILED') else 'AUDIT_UNAVAILABLE'
                    raise AuditUserRetryError(code) from None
                raise AuditUserRetryError() from None

    def _retry(self,c,key):
        with self._uow() as tx:
            old=self._repo.peek_created_for_job(tx,job_id=c.job_id)
            if type(old) is not AuditExportIntent or (old.spec.scope,old.spec.project_id)!=(c.scope,c.project_id):
                raise AuditUserRetryError('RESOURCE_NOT_FOUND')
            old.__post_init__()
            auth=AuditExportSubmitAuthorizationRequest(c.session_token,c.csrf_token,c.trace_id,old.spec)
            proof=self._auth.require_in_transaction(tx,request=auth)
            if (type(proof) is not AuthorizedAuditExportSubmit or type(proof.actor_id) is not UUID or not proof.actor_id.int
                or (proof.scope,proof.project_id,proof.intent_hash)!=(c.scope,c.project_id,old.intent_hash)):
                raise AuditUserRetryError()
            if self._repo.get_created(tx,export_id=old.export_id)!=old:raise AuditUserRetryError()
            accepted=self._repo.get_accepted(tx,intent=old)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=old or accepted.job_id!=c.job_id:raise AuditUserRetryError()
            accepted.__post_init__()
            idem=IdempotencyScope.from_key(actor_id=proof.actor_id,project_id=c.project_id,
                operation='V1_AUDIT_EXPORT_'+c.scope+'_USER_RETRY',key=key)
            fingerprint=canonical_payload_fingerprint(dict(source_job_id=str(c.job_id),
                intent_hash=old.intent_hash,expected_version=c.expected_version))
            replay=self._receipts.reserve(tx,scope=idem,request_fingerprint=fingerprint)
            source=self._sources.read(tx,accepted=accepted,expected_version=c.expected_version)
            if type(source) is not AuditUserRetrySource or source.accepted!=accepted:raise AuditUserRetryError()
            source.__post_init__()
            if source.failure.lock_version!=c.expected_version:raise AuditUserRetryError()
            if replay is not None:
                if type(replay) is not IdempotencyResult or replay.ref_type!='V1_AUDIT_USER_RETRY' or replay.status_code!=202:raise AuditUserRetryError()
                replay.__post_init__()
                result=self._generations.get(tx,new_export_id=replay.ref_id)
            else:
                fresh=self._repo.create_intent(tx,actor_id=proof.actor_id,spec=old.spec,trace_id=c.trace_id)
                if (type(fresh) is not AuditExportIntent or fresh.spec!=old.spec or fresh.actor_id!=proof.actor_id
                    or fresh.trace_id!=c.trace_id or fresh.export_id==old.export_id):raise AuditUserRetryError()
                fresh.__post_init__()
                refs=self._queue.enqueue_export(tx,request=AuditExportSubmitService._queue_request(fresh))
                if type(refs) is not AuditExportJobRef or refs.job_id==c.job_id:raise AuditUserRetryError()
                refs.__post_init__()
                request_event=self._audit.append(tx,AuditEventDraft(trace_id=fresh.trace_id,event_scope=c.scope,target_project_id=c.project_id,
                    actor_type='USER',actor_id=proof.actor_id,original_actor_id=None,actor_hint_digest=None,
                    action='AUDIT_EXPORT_REQUESTED',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',
                    target_object_id=refs.job_id,reason_code=fresh.spec.purpose,after_state='PENDING'))
                new_accepted=self._repo.record_acceptance(tx,intent=fresh,queue_ref=refs,audit_event_id=request_event)
                if (type(new_accepted) is not AcceptedAuditExport or new_accepted.intent!=fresh
                    or (new_accepted.job_id,new_accepted.event_id,new_accepted.request_audit_event_id)!=(refs.job_id,refs.event_id,request_event)):
                    raise AuditUserRetryError()
                new_accepted.__post_init__()
                retry_event=self._audit.append(tx,AuditEventDraft(trace_id=fresh.trace_id,event_scope=c.scope,target_project_id=c.project_id,
                    actor_type='USER',actor_id=proof.actor_id,original_actor_id=None,actor_hint_digest=None,
                    action='AUDIT_EXPORT_USER_RETRY_REQUESTED',outcome='SUCCESS',target_owner_module='jobs',target_object_type='JOB-01',
                    target_object_id=refs.job_id,reason_code='USER_RETRY',before_state='FAILED',after_state='PENDING'))
                result=self._generations.record(tx,source=source,new_accepted=new_accepted,retry_audit_event_id=retry_event)
            if type(result) is not AuditExportRetryGeneration:raise AuditUserRetryError()
            result.__post_init__()
            if (result.source_export_id,result.source_job_id,result.source_failure_event_id,result.expected_source_version)!=(
                old.export_id,c.job_id,source.failure_event_id,c.expected_version):raise AuditUserRetryError()
            fresh=self._repo.get_created(tx,export_id=result.new_export_id)
            if type(fresh) is not AuditExportIntent or fresh.spec!=old.spec or fresh.actor_id!=proof.actor_id:raise AuditUserRetryError()
            fresh.__post_init__()
            new_accepted=self._repo.get_accepted(tx,intent=fresh)
            if (type(new_accepted) is not AcceptedAuditExport or new_accepted.intent!=fresh
                or (new_accepted.job_id,new_accepted.event_id)!=(result.new_job_id,result.new_event_id)):
                raise AuditUserRetryError()
            new_accepted.__post_init__()
            refs=self._queue.find_export(tx,request=AuditExportSubmitService._queue_request(fresh))
            if type(refs) is not AuditExportJobRef or (refs.job_id,refs.event_id)!=(result.new_job_id,result.new_event_id):raise AuditUserRetryError()
            if replay is None:
                self._receipts.complete(tx,scope=idem,result=IdempotencyResult('V1_AUDIT_USER_RETRY',result.new_export_id,202))
            if self._auth.require_in_transaction(tx,request=auth)!=proof:raise AuditUserRetryError('AUTH_ACCESS_DENIED')
            if replay is None:tx.commit()
            return result
