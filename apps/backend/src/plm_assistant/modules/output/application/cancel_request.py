"""Authorized OutputRequest cancellation; Output and Jobs share one caller UOW."""
from __future__ import annotations
import unicodedata, uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.jobs.application.output_cancel import (
    OutputJobCancelError, OutputJobCancelResult, OutputJobCancellation,
)
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
class OutputRequestCancelError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code=code
        super().__init__(code)
@dataclass(frozen=True,slots=True)
class CancelOutputRequest:
    session_token: bytes=field(repr=False)
    csrf_token: bytes=field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    output_request_id: uuid.UUID
    reason: str=field(repr=False)
    expected_version: int
@dataclass(frozen=True,slots=True)
class OutputRequestCancelFacts:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    requested_by: uuid.UUID
    job_id: uuid.UUID
    context_snapshot_id: uuid.UUID
    state: str
    lock_version: int
@dataclass(frozen=True,slots=True)
class OutputRequestCancelResult:
    output_request_id: uuid.UUID
    project_id: uuid.UUID
    state: str
    changed: bool
    lock_version: int
    status_code: int=200
class OutputRequestCancelAccessPort(Protocol):
    def authenticated_user(self,transaction:object,*,session_token:bytes,
                           csrf_token:bytes,now:datetime)->uuid.UUID|None: ...
    def require_canceller(self,transaction:object,*,user_id:uuid.UUID,
                          project_id:uuid.UUID,requester_id:uuid.UUID)->bool: ...
class OutputRequestCancelLicensePort(Protocol):
    def require_valid(self,*,trace_id:uuid.UUID)->object: ...
class OutputRequestCancelRepositoryPort(Protocol):
    def get_for_update(self,transaction:object,*,project_id:uuid.UUID,
                       output_request_id:uuid.UUID)->OutputRequestCancelFacts|None: ...
    def set_state(self,transaction:object,*,facts:OutputRequestCancelFacts,
                  state:str,completed_at:datetime|None)->int: ...
class OutputRequestCancelReceiptsPort(Protocol):
    def reserve(self,transaction:object,*,scope:IdempotencyScope,
                request_fingerprint:bytes)->IdempotencyResult|None: ...
    def complete(self,transaction:object,*,scope:IdempotencyScope,
                 result:IdempotencyResult)->None: ...
class OutputRequestCancelService:
    def __init__(self,*,unit_of_work:Callable[[],object],
                 access:OutputRequestCancelAccessPort,
                 license_guard:OutputRequestCancelLicensePort,
                 repository:OutputRequestCancelRepositoryPort,
                 jobs:OutputJobCancellation,receipts:OutputRequestCancelReceiptsPort,
                 audit:AuditService,clock:Callable[[],datetime]|None=None):
        if any(v is None for v in (unit_of_work,access,license_guard,repository,jobs,receipts,audit)):
            raise ValueError("OutputRequest cancel dependencies are required")
        self._uow,self._access,self._guard=unit_of_work,access,license_guard
        self._repo,self._jobs,self._receipts,self._audit=repository,jobs,receipts,audit
        self._clock=clock or (lambda:datetime.now(timezone.utc))
    def cancel(self,command:CancelOutputRequest,*,idempotency_key:str)->OutputRequestCancelResult:
        self._validate(command)
        try: validate_idempotency_key(idempotency_key)
        except IdempotencyError as exc: raise OutputRequestCancelError(exc.code) from None
        try:
            with self._uow() as tx:
                self._guard.require_valid(trace_id=command.trace_id)
                now=self._clock()
                if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
                    raise OutputRequestCancelError("SYSTEM_UNAVAILABLE")
                actor=self._access.authenticated_user(tx,session_token=command.session_token,
                    csrf_token=command.csrf_token,now=now.astimezone(timezone.utc))
                if type(actor) is not uuid.UUID or not actor.int:
                    raise OutputRequestCancelError("AUTH_ACCESS_DENIED")
                facts=self._repo.get_for_update(tx,project_id=command.project_id,
                    output_request_id=command.output_request_id)
                if type(facts) is not OutputRequestCancelFacts:
                    raise OutputRequestCancelError("RESOURCE_NOT_FOUND")
                if (facts.output_request_id!=command.output_request_id or facts.project_id!=command.project_id
                        or not self._access.require_canceller(tx,user_id=actor,
                            project_id=command.project_id,requester_id=facts.requested_by)):
                    raise OutputRequestCancelError("RESOURCE_NOT_FOUND")
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=command.project_id,
                    operation="V1_OUTPUT_REQUEST_CANCEL",key=idempotency_key)
                fingerprint=canonical_payload_fingerprint({
                    "output_request_id":str(command.output_request_id),
                    "reason":command.reason,"expected_version":command.expected_version})
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type!="V1_OUTPUT_REQUEST" or replay.ref_id!=command.output_request_id or replay.status_code!=200:
                        raise OutputRequestCancelError("SYSTEM_UNAVAILABLE")
                    tx.commit()
                    return self._result(facts,changed=False)
                if facts.lock_version!=command.expected_version:
                    raise OutputRequestCancelError("CONFLICT_VERSION")
                job=self._jobs.cancel_output(tx,project_id=command.project_id,job_id=facts.job_id,
                    output_request_id=facts.output_request_id,
                    context_snapshot_id=facts.context_snapshot_id,actor_id=actor,reason=command.reason)
                if type(job) is not OutputJobCancelResult or job.job_id!=facts.job_id:
                    raise OutputRequestCancelError("SYSTEM_UNAVAILABLE")
                job.__post_init__()
                if job.state not in {"CANCEL_REQUESTED","CANCELLED","SUCCEEDED","FAILED"}:
                    raise OutputRequestCancelError("CONFLICT_STATE")
                changed=job.changed
                if job.state in {"CANCEL_REQUESTED","CANCELLED"}:
                    if facts.state not in {"REQUESTED","QUEUED","GENERATING","VALIDATING",
                                           "CANCEL_REQUESTED","CANCELLED"}:
                        raise OutputRequestCancelError("CONFLICT_STATE")
                    if facts.state!=job.state:
                        version=self._repo.set_state(tx,facts=facts,state=job.state,
                            completed_at=now if job.state=="CANCELLED" else None)
                        facts=OutputRequestCancelFacts(facts.output_request_id,facts.project_id,
                            facts.requested_by,facts.job_id,facts.context_snapshot_id,job.state,version)
                        changed=True
                else:
                    if facts.state!=job.state:
                        raise OutputRequestCancelError("CONFLICT_STATE")
                self._audit.append(tx,AuditEventDraft(trace_id=command.trace_id,
                    event_scope="PROJECT",target_project_id=command.project_id,actor_type="USER",
                    actor_id=actor,original_actor_id=None,actor_hint_digest=None,
                    action="OUTPUT_REQUEST_CANCEL",outcome="SUCCESS",target_owner_module="output",
                    target_object_type="OUT-01",target_object_id=command.output_request_id,
                    after_state=job.state))
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult(
                    "V1_OUTPUT_REQUEST",command.output_request_id,200))
                result=self._result(facts,changed=changed)
                tx.commit()
                return result
        except OutputRequestCancelError: raise
        except OutputJobCancelError as exc:
            raise OutputRequestCancelError(exc.code if exc.code in {
                "RESOURCE_NOT_FOUND","CONFLICT_STATE","VALIDATION_FAILED"} else "SYSTEM_UNAVAILABLE") from None
        except RuntimeLicenseError:
            raise OutputRequestCancelError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as exc:
            raise OutputRequestCancelError(exc.code) from None
        except Exception:
            raise OutputRequestCancelError("SYSTEM_UNAVAILABLE") from None
    @staticmethod
    def _result(facts:OutputRequestCancelFacts,*,changed:bool)->OutputRequestCancelResult:
        return OutputRequestCancelResult(facts.output_request_id,facts.project_id,
            facts.state,changed,facts.lock_version)
    @staticmethod
    def _validate(command:object)->None:
        if (type(command) is not CancelOutputRequest
            or any(type(v) is not uuid.UUID or not v.int for v in
                   (command.trace_id,command.project_id,command.output_request_id))
            or type(command.session_token) is not bytes or len(command.session_token)!=32
            or type(command.csrf_token) is not bytes or len(command.csrf_token)!=32
            or type(command.expected_version) is not int or not 0<=command.expected_version<=2**63-1
            or type(command.reason) is not str or not 1<=len(command.reason)<=1024
            or command.reason.strip()!=command.reason
            or any(unicodedata.category(c).startswith("C") for c in command.reason)):
            raise OutputRequestCancelError("VALIDATION_FAILED")
