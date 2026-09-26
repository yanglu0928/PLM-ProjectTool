"""Minimal cross-owner Audit enqueue; coordinates never prove authorization."""
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

AUDIT_EXPORT_POLICY_VERSION = "AUDIT-EXPORT-POLICY-V1"


class AuditExportEnqueueError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)


@dataclass(frozen=True,slots=True)
class AuditExportJobRequest:
    export_id: UUID
    actor_id: UUID
    scope: str
    project_id: UUID|None
    trace_id: UUID  # Immutable original Export trace, not current replay HTTP trace.
    policy_version: str = AUDIT_EXPORT_POLICY_VERSION

    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.export_id,self.actor_id,self.trace_id))
                or type(self.scope) is not str or self.scope not in {"DEPLOYMENT","PROJECT"}
                or self.scope=="DEPLOYMENT" and self.project_id is not None
                or self.scope=="PROJECT" and (type(self.project_id) is not UUID or not self.project_id.int)
                or type(self.policy_version) is not str or self.policy_version!=AUDIT_EXPORT_POLICY_VERSION):
            raise AuditExportEnqueueError("VALIDATION_FAILED")


@dataclass(frozen=True,slots=True)
class AuditExportJobRef:
    job_id: UUID
    event_id: UUID

    def __post_init__(self):
        if any(type(v) is not UUID or not v.int for v in (self.job_id,self.event_id)):
            raise AuditExportEnqueueError("JOB_STORE_UNAVAILABLE")


class AuditExportJobQueuePort(Protocol):
    def enqueue_export(self,transaction:object,*,request:AuditExportJobRequest)->AuditExportJobRef: ...
    def find_export(self,transaction:object,*,request:AuditExportJobRequest)->AuditExportJobRef|None: ...


class AuditExportJobQueue:
    """Trusted caller MUST authorize/root-bind first, then owns entire UOW."""
    def __init__(self,repository:AuditExportJobQueuePort):
        if repository is None:raise ValueError("Audit export queue repository required")
        self._repository=repository

    @staticmethod
    def _request(request):
        if type(request) is not AuditExportJobRequest:raise AuditExportEnqueueError("VALIDATION_FAILED")
        request.__post_init__()

    @staticmethod
    def _result(value,*,optional=False):
        if optional and value is None:return None
        if type(value) is not AuditExportJobRef:raise AuditExportEnqueueError("JOB_STORE_UNAVAILABLE")
        value.__post_init__();return value

    def enqueue_export(self,transaction,*,request):
        self._request(request)
        return self._result(self._repository.enqueue_export(transaction,request=request))

    def find_export(self,transaction,*,request):
        self._request(request)
        return self._result(self._repository.find_export(transaction,request=request),optional=True)
