"""Owner-bound current-authorized cancellation with durable first response."""
from dataclasses import dataclass,field
from uuid import UUID
import unicodedata
from .export_cancel_authorization import AuditExportCancelAuthorizationRequest,AuthorizedAuditExportCancel
from .export_submit_authorization import AuditExportSubmitAuthorizationError
from .submit_export import AuditExportIntent,AcceptedAuditExport,AuditExportSubmitService
from .public import AuditEventDraft
from plm_assistant.modules.jobs.application.audit_export_cancel import AuditExportCancellationTarget,AuditExportCancellationError
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRef
from plm_assistant.modules.platform.application.idempotency import IdempotencyScope,IdempotencyResult,IdempotencyError,validate_idempotency_key,canonical_payload_fingerprint


class AuditExportCancelRequestError(RuntimeError):
    def __init__(self,code='AUDIT_UNAVAILABLE'):self.code=code;super().__init__(code)


@dataclass(frozen=True,slots=True)
class RequestAuditExportCancel:
    export_id: UUID
    scope: str
    project_id: UUID|None
    session_token: bytes=field(repr=False)
    csrf_token: bytes=field(repr=False)
    trace_id: UUID
    reason: str=field(repr=False)

    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.export_id,self.trace_id))
                or any(type(v) is not bytes or len(v)!=32 for v in (self.session_token,self.csrf_token))
                or type(self.scope) is not str or self.scope not in {'PROJECT','DEPLOYMENT'}
                or self.scope=='PROJECT' and (type(self.project_id) is not UUID or not self.project_id.int)
                or self.scope=='DEPLOYMENT' and self.project_id is not None
                or type(self.reason) is not str or not 1<=len(self.reason)<=1024 or self.reason.strip()!=self.reason
                or any(unicodedata.category(char).startswith('C') for char in self.reason)):
            raise AuditExportCancelRequestError('VALIDATION_FAILED')


@dataclass(frozen=True,slots=True)
class AuditExportCancelReceipt:
    job_id: UUID
    state: str
    changed: bool
    audit_event_id: UUID

    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.job_id,self.audit_event_id))
                or type(self.changed) is not bool or type(self.state) is not str or self.state not in {'CANCEL_REQUESTED','CANCELLED','SUCCEEDED','FAILED'}):
            raise AuditExportCancelRequestError()


class AuditExportCancelRequestService:
    def __init__(self,*,unit_of_work,repository,authorization,cancellations,receipts,sources,audit):
        if any(v is None for v in (unit_of_work,repository,authorization,cancellations,receipts,sources,audit)):
            raise ValueError('Owned cancel dependencies required')
        self._uow,self._repo,self._auth,self._cancel,self._receipts,self._sources,self._audit=unit_of_work,repository,authorization,cancellations,receipts,sources,audit

    def request(self,c,*,idempotency_key):
        if type(c) is not RequestAuditExportCancel:raise AuditExportCancelRequestError('VALIDATION_FAILED')
        c.__post_init__()
        try:validate_idempotency_key(idempotency_key)
        except IdempotencyError as exc:raise AuditExportCancelRequestError(exc.code) from None
        for attempt in range(3):
            try:return self._request(c,idempotency_key)
            except Exception as exc:
                if self._repo.is_retryable_deadlock(exc) is True:
                    if attempt<2:continue
                    raise AuditExportCancelRequestError() from None
                if isinstance(exc,AuditExportCancelRequestError):raise
                if isinstance(exc,(IdempotencyError,AuditExportSubmitAuthorizationError,AuditExportCancellationError)):
                    raise AuditExportCancelRequestError(exc.code) from None
                raise AuditExportCancelRequestError() from None

    def _request(self,c,key):
        with self._uow() as tx:
            intent=self._repo.peek_created(tx,export_id=c.export_id)
            if type(intent) is not AuditExportIntent or (intent.spec.scope,intent.spec.project_id)!=(c.scope,c.project_id):raise AuditExportCancelRequestError('RESOURCE_NOT_FOUND')
            intent.__post_init__()
            auth=AuditExportCancelAuthorizationRequest(c.session_token,c.csrf_token,c.trace_id,intent.spec,intent.actor_id)
            proof=self._auth.require_in_transaction(tx,request=auth)
            if (type(proof) is not AuthorizedAuditExportCancel or type(proof.actor_id) is not UUID or not proof.actor_id.int
                    or (proof.scope,proof.project_id,proof.original_actor_id,proof.intent_hash)!=(c.scope,c.project_id,intent.actor_id,intent.intent_hash)):
                raise AuditExportCancelRequestError()
            if self._repo.get_created(tx,export_id=c.export_id)!=intent:raise AuditExportCancelRequestError()
            accepted=self._repo.get_accepted(tx,intent=intent)
            if type(accepted) is not AcceptedAuditExport or accepted.intent!=intent:raise AuditExportCancelRequestError()
            accepted.__post_init__()
            target=AuditExportCancellationTarget(AuditExportSubmitService._queue_request(intent),AuditExportJobRef(accepted.job_id,accepted.event_id))
            before=self._cancel.read_facts(tx,target=target)
            if before.requested_by is not None:self._sources.first_request(tx,accepted=accepted,facts=before)
            idem=IdempotencyScope.from_key(actor_id=proof.actor_id,project_id=c.project_id,operation='V1_AUDIT_EXPORT_CANCEL_'+c.scope,key=key)
            fingerprint=canonical_payload_fingerprint(dict(export_id=str(c.export_id),intent_hash=intent.intent_hash,reason=c.reason))
            replay=self._receipts.reserve(tx,scope=idem,request_fingerprint=fingerprint)
            if replay is not None:
                if type(replay) is not IdempotencyResult or replay.ref_type!='V1_AUDIT_EXPORT_CANCEL' or replay.status_code!=200:raise AuditExportCancelRequestError()
                replay.__post_init__()
                result=self._sources.receipt(tx,accepted=accepted,actor_id=proof.actor_id,audit_event_id=replay.ref_id)
            else:
                mutation=self._cancel.request_cancel(tx,target=target,requested_by=proof.actor_id,reason=c.reason)
                if mutation.changed:
                    after=self._cancel.read_facts(tx,target=target)
                    if (after.requested_by,after.reason,after.state)!=(proof.actor_id,c.reason,mutation.state):raise AuditExportCancelRequestError()
                event_id=self._audit.append(tx,AuditEventDraft(trace_id=c.trace_id,event_scope=c.scope,target_project_id=c.project_id,
                    actor_type='USER',actor_id=proof.actor_id,original_actor_id=None,actor_hint_digest=None,
                    action='AUDIT_EXPORT_CANCEL_REQUESTED' if mutation.changed else 'AUDIT_EXPORT_CANCEL_CHECKED',outcome='SUCCESS',
                    target_owner_module='jobs',target_object_type='JOB-01',target_object_id=accepted.job_id,
                    reason_code='USER_REQUESTED',before_state=before.state,after_state=mutation.state))
                result=self._sources.receipt(tx,accepted=accepted,actor_id=proof.actor_id,audit_event_id=event_id)
                if (result.state,result.changed)!=(mutation.state,mutation.changed):raise AuditExportCancelRequestError()
                self._receipts.complete(tx,scope=idem,result=IdempotencyResult('V1_AUDIT_EXPORT_CANCEL',event_id,200))
            if type(result) is not AuditExportCancelReceipt or result.job_id!=accepted.job_id:raise AuditExportCancelRequestError()
            result.__post_init__()
            if self._auth.require_in_transaction(tx,request=auth)!=proof:raise AuditExportCancelRequestError('AUTH_ACCESS_DENIED')
            if replay is None:tx.commit()
            return result
