"""Licensed current submission, immutable first refs, one atomic UOW."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from typing import Protocol
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError,IdempotencyScope,IdempotencyResult,validate_idempotency_key,
)
from plm_assistant.modules.jobs.application.audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from .export_contract import AuditExportSpec,EXPORT_FORMAT,EXPORT_POLICY_VERSION,EXPORT_PROJECTION_VERSION
from .export_submit_authorization import AuditExportSubmitAuthorizationRequest,AuthorizedAuditExportSubmit,AuditExportSubmitAuthorizationError
from .public import AuditEventDraft


class AuditExportSubmitError(RuntimeError):
    def __init__(self,code="AUDIT_UNAVAILABLE"):
        self.code=code
        super().__init__(code)


def _id(value):return type(value) is UUID and value.int!=0
def _time(value):return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True,slots=True)
class AuditExportIntent:
    export_id: UUID
    actor_id: UUID
    trace_id: UUID
    requested_at: datetime
    spec: AuditExportSpec
    intent_hash: str
    policy_version: str = EXPORT_POLICY_VERSION
    projection_version: str = EXPORT_PROJECTION_VERSION
    format_version: str = EXPORT_FORMAT

    def __post_init__(self):
        if (not all(_id(v) for v in (self.export_id,self.actor_id,self.trace_id)) or not _time(self.requested_at)
                or type(self.spec) is not AuditExportSpec
                or (self.policy_version,self.projection_version,self.format_version)!=(EXPORT_POLICY_VERSION,EXPORT_PROJECTION_VERSION,EXPORT_FORMAT)
                or self.intent_hash!=self.spec.fingerprint()):
            raise AuditExportSubmitError()


@dataclass(frozen=True,slots=True)
class AcceptedAuditExport:
    """Original fixed response, not current Job status/authority or file result."""
    intent: AuditExportIntent
    job_id: UUID
    event_id: UUID
    request_audit_event_id: UUID
    accepted_at: datetime

    def __post_init__(self):
        if (type(self.intent) is not AuditExportIntent or not all(_id(v) for v in (self.job_id,self.event_id,self.request_audit_event_id))
                or not _time(self.accepted_at) or self.accepted_at<self.intent.requested_at):
            raise AuditExportSubmitError()
        self.intent.__post_init__()


class AuditExportSubmitRepositoryPort(Protocol):
    def create_intent(self,tx:object,*,actor_id:UUID,spec:AuditExportSpec,trace_id:UUID)->AuditExportIntent: ...
    def get_created(self,tx:object,*,export_id:UUID)->AuditExportIntent|None: ...
    def record_acceptance(self,tx:object,*,intent:AuditExportIntent,queue_ref:AuditExportJobRef,audit_event_id:UUID)->AcceptedAuditExport: ...
    def get_accepted(self,tx:object,*,intent:AuditExportIntent)->AcceptedAuditExport|None: ...
    def is_retryable_deadlock(self,error:Exception)->bool: ...


class AuditExportSubmitService:
    def __init__(self,*,unit_of_work,authorization,repository:AuditExportSubmitRepositoryPort,receipts,queue,audit):
        if any(v is None for v in (unit_of_work,authorization,repository,receipts,queue,audit)):
            raise ValueError("Audit export submit dependencies required")
        self._uow,self._authorization,self._repository=unit_of_work,authorization,repository
        self._receipts,self._queue,self._audit=receipts,queue,audit

    def submit_idempotent(self,command,*,idempotency_key):
        if (type(command) is not AuditExportSubmitAuthorizationRequest or type(command.spec) is not AuditExportSpec
                or not _id(command.trace_id) or any(type(v) is not bytes or len(v)!=32 for v in (command.session_token,command.csrf_token))):
            raise AuditExportSubmitError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint=bytes.fromhex(command.spec.fingerprint())
        except IdempotencyError as exc:raise AuditExportSubmitError(exc.code) from None
        except ValueError:raise AuditExportSubmitError("AUDIT_EXPORT_SCOPE_INVALID") from None
        for attempt in range(3):
            try:return self._submit(command,idempotency_key,fingerprint)
            except Exception as exc:
                classifier=getattr(self._repository,"is_retryable_deadlock",None)
                if callable(classifier) and classifier(exc) is True:
                    if attempt<2:continue
                    raise AuditExportSubmitError() from None
                if isinstance(exc,AuditExportSubmitError):raise
                if isinstance(exc,(IdempotencyError,AuditExportSubmitAuthorizationError)):
                    raise AuditExportSubmitError(exc.code) from None
                # Queue/storage details are never returned to a future API caller.
                raise AuditExportSubmitError() from None

    @staticmethod
    def _bound(intent,command,actor,fingerprint):
        if type(intent) is not AuditExportIntent:raise AuditExportSubmitError()
        intent.__post_init__()
        if (intent.actor_id!=actor or intent.spec.scope!=command.spec.scope or intent.spec.project_id!=command.spec.project_id
                or bytes.fromhex(intent.intent_hash)!=fingerprint):raise AuditExportSubmitError()

    @staticmethod
    def _queue_request(intent):
        return AuditExportJobRequest(intent.export_id,intent.actor_id,intent.spec.scope,intent.spec.project_id,intent.trace_id,intent.policy_version)

    @staticmethod
    def _accepted(result,intent):
        if type(result) is not AcceptedAuditExport or result.intent!=intent:raise AuditExportSubmitError()
        result.__post_init__()

    def _submit(self,c,key,fingerprint):
        with self._uow() as tx:
            proof=self._authorization.require_in_transaction(tx,request=c)
            if (type(proof) is not AuthorizedAuditExportSubmit or not _id(proof.actor_id)
                    or (proof.scope,proof.project_id,proof.intent_hash)!=(c.spec.scope,c.spec.project_id,c.spec.fingerprint())
                    or bytes.fromhex(proof.intent_hash)!=fingerprint):raise AuditExportSubmitError()
            operation="V1_AUDIT_EXPORT_"+c.spec.scope+"_SUBMIT"
            scope=IdempotencyScope.from_key(actor_id=proof.actor_id,project_id=proof.project_id,operation=operation,key=key)
            replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
            if replay is not None:
                if type(replay) is not IdempotencyResult or replay.ref_type!="V1_AUDIT_EXPORT" or replay.status_code!=202:raise AuditExportSubmitError()
                replay.__post_init__()
                intent=self._repository.get_created(tx,export_id=replay.ref_id)
                self._bound(intent,c,proof.actor_id,fingerprint)
                if intent.export_id!=replay.ref_id:raise AuditExportSubmitError()
                accepted=self._repository.get_accepted(tx,intent=intent)
                self._accepted(accepted,intent)
                queued=self._queue.find_export(tx,request=self._queue_request(intent))
                if type(queued) is not AuditExportJobRef or (queued.job_id,queued.event_id)!=(accepted.job_id,accepted.event_id):raise AuditExportSubmitError()
                queued.__post_init__()
                return accepted  # No replay writes/commit or accidental terminal revival.
            intent=self._repository.create_intent(tx,actor_id=proof.actor_id,spec=c.spec,trace_id=c.trace_id)
            self._bound(intent,c,proof.actor_id,fingerprint)
            if intent.trace_id!=c.trace_id:raise AuditExportSubmitError()
            queued=self._queue.enqueue_export(tx,request=self._queue_request(intent))
            if type(queued) is not AuditExportJobRef:raise AuditExportSubmitError()
            queued.__post_init__()
            audit_id=self._audit.append(tx,AuditEventDraft(trace_id=intent.trace_id,event_scope=intent.spec.scope,target_project_id=intent.spec.project_id,
                actor_type="USER",actor_id=intent.actor_id,original_actor_id=None,actor_hint_digest=None,
                action="AUDIT_EXPORT_REQUESTED",outcome="SUCCESS",target_owner_module="jobs",target_object_type="JOB-01",
                target_object_id=queued.job_id,reason_code=intent.spec.purpose,after_state="PENDING"))
            if not _id(audit_id):raise AuditExportSubmitError()
            accepted=self._repository.record_acceptance(tx,intent=intent,queue_ref=queued,audit_event_id=audit_id)
            self._accepted(accepted,intent)
            if (accepted.job_id,accepted.event_id,accepted.request_audit_event_id)!=(queued.job_id,queued.event_id,audit_id):raise AuditExportSubmitError()
            self._receipts.complete(tx,scope=scope,result=IdempotencyResult("V1_AUDIT_EXPORT",intent.export_id,202))
            tx.commit()
            return accepted
