"""Transactional internal OutputRequest create Owner; no HTTP/plugin execution."""
from __future__ import annotations
import re, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Protocol
from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
_REF=re.compile(r"[A-Za-z][A-Za-z0-9._:/-]{0,127}$",re.ASCII)
_TYPES=frozenset({"DOCX","PPTX","PNG","JPEG"})
class OutputRequestError(RuntimeError):
    def __init__(self,code:str)->None:self.code=code;super().__init__(code)
@dataclass(frozen=True,slots=True)
class CreateOutputRequest:
    session_token:bytes=field(repr=False)
    csrf_token:bytes=field(repr=False)
    trace_id:uuid.UUID
    project_id:uuid.UUID
    output_type:str
    template_version_ref:uuid.UUID
    source_version_refs:tuple[uuid.UUID,...]
    output_policy_ref:str
    plugin_operation:str
@dataclass(frozen=True,slots=True)
class ResolvedOutputContext:
    source_version_refs:tuple[uuid.UUID,...]
    context_payload:dict=field(repr=False)
    context_fingerprint:bytes=field(repr=False)
    def __post_init__(self):
        if (type(self.source_version_refs) is not tuple or not self.source_version_refs
            or any(type(v) is not uuid.UUID or not v.int for v in self.source_version_refs)
            or len(set(self.source_version_refs))!=len(self.source_version_refs)
            or type(self.context_payload) is not dict or type(self.context_fingerprint) is not bytes
            or len(self.context_fingerprint)!=32):
            raise OutputRequestError("VALIDATION_FAILED")
        try:
            if canonical_payload_fingerprint(self.context_payload)!=self.context_fingerprint:
                raise OutputRequestError("VALIDATION_FAILED")
        except IdempotencyError:raise OutputRequestError("VALIDATION_FAILED") from None
@dataclass(frozen=True,slots=True)
class CreatedOutputRequest:
    output_request_id:uuid.UUID
    project_id:uuid.UUID
    job_id:uuid.UUID
    request_state:str
    status_code:int=202
class OutputRequestAccessPort(Protocol):
    def authorized_creator(self,transaction:object,*,project_id:uuid.UUID,session_token:bytes,
        csrf_token:bytes,trace_id:uuid.UUID,now:datetime)->uuid.UUID|None:...
class OutputRequestLicensePort(Protocol):
    def require_valid(self,*,trace_id:uuid.UUID)->object:...
class OutputContextResolverPort(Protocol):
    def resolve(self,transaction:object,*,actor_id:uuid.UUID,
        command:CreateOutputRequest)->ResolvedOutputContext:...
class OutputRequestRepositoryPort(Protocol):
    def lock_generation(self,transaction:object,*,project_id:uuid.UUID,identity_fingerprint:bytes)->None:...
    def find_generation(self,transaction:object,*,project_id:uuid.UUID,output_type:str,
        input_fingerprint:bytes,template_version_ref:uuid.UUID,output_policy_ref:str,
        generation_no:int)->CreatedOutputRequest|None:...
    def create(self,transaction:object,*,command:CreateOutputRequest,actor_id:uuid.UUID,
        context:ResolvedOutputContext,input_fingerprint:bytes)->uuid.UUID:...
    def snapshot_id(self,transaction:object,*,project_id:uuid.UUID,
        output_request_id:uuid.UUID)->uuid.UUID:...
    def attach_job(self,transaction:object,*,project_id:uuid.UUID,
        output_request_id:uuid.UUID,job_id:uuid.UUID)->None:...
    def get(self,transaction:object,*,project_id:uuid.UUID,
        output_request_id:uuid.UUID)->CreatedOutputRequest|None:...
class OutputJobQueuePort(Protocol):
    def enqueue_output(self,transaction:object,*,project_id:uuid.UUID,output_request_id:uuid.UUID,
        context_snapshot_id:uuid.UUID,actor_id:uuid.UUID,trace_id:uuid.UUID)->uuid.UUID:...
class OutputRequestReceiptPort(Protocol):
    def reserve(self,transaction:object,*,scope:IdempotencyScope,
        request_fingerprint:bytes)->IdempotencyResult|None:...
    def complete(self,transaction:object,*,scope:IdempotencyScope,result:IdempotencyResult)->None:...
class OutputRequestService:
    """Create fixed, authorized Output work in the caller-owned transaction."""
    def __init__(self,*,unit_of_work:Callable[[],object],access:OutputRequestAccessPort,
        license_guard:OutputRequestLicensePort,resolver:OutputContextResolverPort,
        repository:OutputRequestRepositoryPort,jobs:OutputJobQueuePort,
        receipts:OutputRequestReceiptPort,audit:AuditService,
        clock:Callable[[],datetime]|None=None):
        if any(v is None for v in (unit_of_work,access,license_guard,resolver,repository,jobs,receipts,audit)):
            raise ValueError("OutputRequest create dependencies are required")
        self._uow,self._access,self._license=unit_of_work,access,license_guard
        self._resolver,self._repo,self._jobs=resolver,repository,jobs
        self._receipts,self._audit=receipts,audit
        self._clock=clock or (lambda:datetime.now(timezone.utc))
    def create(self,command:CreateOutputRequest,*,idempotency_key:str)->CreatedOutputRequest:
        self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            self._license.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor=self._access.authorized_creator(tx,project_id=command.project_id,
                    session_token=command.session_token,csrf_token=command.csrf_token,
                    trace_id=command.trace_id,now=self._clock())
                if type(actor) is not uuid.UUID or not actor.int:raise OutputRequestError("FORBIDDEN")
                context=self._resolver.resolve(tx,actor_id=actor,command=command)
                if type(context) is not ResolvedOutputContext or context.source_version_refs!=command.source_version_refs:
                    raise OutputRequestError("VALIDATION_FAILED")
                fingerprint=canonical_payload_fingerprint({
                    "project_id":str(command.project_id),"output_type":command.output_type,
                    "template_version_ref":str(command.template_version_ref),
                    "source_version_refs":[str(x) for x in context.source_version_refs],
                    "output_policy_ref":command.output_policy_ref,"plugin_operation":command.plugin_operation,
                    "context_fingerprint":context.context_fingerprint.hex()})
                scope=IdempotencyScope.from_key(actor_id=actor,project_id=command.project_id,
                    operation="V1_OUTPUT_REQUEST_CREATE",key=idempotency_key)
                replay=self._receipts.reserve(tx,scope=scope,request_fingerprint=fingerprint)
                if replay is not None:
                    if replay.ref_type!="V1_OUTPUT_REQUEST" or replay.status_code!=202:
                        raise OutputRequestError("SYSTEM_UNAVAILABLE")
                    result=self._repo.get(tx,project_id=command.project_id,output_request_id=replay.ref_id)
                    if result is None:raise OutputRequestError("SYSTEM_UNAVAILABLE")
                    tx.commit();return result
                identity=canonical_payload_fingerprint({
                    "project_id":str(command.project_id),"output_type":command.output_type,
                    "input_fingerprint":fingerprint.hex(),
                    "template_version_ref":str(command.template_version_ref),
                    "output_policy_ref":command.output_policy_ref})
                self._repo.lock_generation(tx,project_id=command.project_id,identity_fingerprint=identity)
                existing=self._repo.find_generation(tx,project_id=command.project_id,
                    output_type=command.output_type,input_fingerprint=fingerprint,
                    template_version_ref=command.template_version_ref,
                    output_policy_ref=command.output_policy_ref,generation_no=1)
                if existing is not None:
                    self._receipts.complete(tx,scope=scope,result=IdempotencyResult(
                        "V1_OUTPUT_REQUEST",existing.output_request_id,202))
                    tx.commit();return existing
                request_id=self._repo.create(tx,command=command,actor_id=actor,
                    context=context,input_fingerprint=fingerprint)
                context_id=self._repo.snapshot_id(tx,project_id=command.project_id,
                    output_request_id=request_id)
                job_id=self._jobs.enqueue_output(tx,project_id=command.project_id,
                    output_request_id=request_id,context_snapshot_id=context_id,
                    actor_id=actor,trace_id=command.trace_id)
                self._repo.attach_job(tx,project_id=command.project_id,
                    output_request_id=request_id,job_id=job_id)
                self._audit.append(tx,AuditEventDraft(trace_id=command.trace_id,
                    event_scope="PROJECT",target_project_id=command.project_id,
                    actor_type="USER",actor_id=actor,original_actor_id=None,
                    actor_hint_digest=None,action="OUTPUT_REQUEST_CREATE",outcome="SUCCESS",
                    target_owner_module="output",target_object_type="OUT-01",
                    target_object_id=request_id,after_state="QUEUED"))
                self._receipts.complete(tx,scope=scope,result=IdempotencyResult(
                    "V1_OUTPUT_REQUEST",request_id,202))
                result=self._repo.get(tx,project_id=command.project_id,output_request_id=request_id)
                if result is None:raise OutputRequestError("SYSTEM_UNAVAILABLE")
                tx.commit();return result
        except IdempotencyError as exc:raise OutputRequestError(exc.code) from None
        except OutputRequestError:raise
        except Exception:raise OutputRequestError("SYSTEM_UNAVAILABLE") from None
    @staticmethod
    def _validate(command:object)->None:
        if (type(command) is not CreateOutputRequest
            or any(type(v) is not uuid.UUID or not v.int for v in
                   (command.trace_id,command.project_id,command.template_version_ref))
            or type(command.session_token) is not bytes or not command.session_token
            or type(command.csrf_token) is not bytes or not command.csrf_token
            or type(command.output_type) is not str or command.output_type not in _TYPES
            or type(command.source_version_refs) is not tuple or not command.source_version_refs
            or any(type(v) is not uuid.UUID or not v.int for v in command.source_version_refs)
            or len(set(command.source_version_refs))!=len(command.source_version_refs)
            or type(command.output_policy_ref) is not str or _REF.fullmatch(command.output_policy_ref) is None
            or type(command.plugin_operation) is not str or _REF.fullmatch(command.plugin_operation) is None):
            raise OutputRequestError("VALIDATION_FAILED")
