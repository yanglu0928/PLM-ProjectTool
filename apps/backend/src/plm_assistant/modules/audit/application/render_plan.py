"""Immutable own planning DTO, not file existence or current authority."""
from dataclasses import dataclass
from datetime import datetime,timedelta
from re import fullmatch
from uuid import UUID
from typing import Protocol
from .worker_capture import AuditExportWorkerCapture,AuditExportWorkerError
from ..domain.capture_membership import MEMBERSHIP_VERSION


@dataclass(frozen=True,slots=True)
class AuditRenderPlan:
    render_attempt_id: UUID
    export_id: UUID
    job_id: UUID
    fencing_token: int
    attempt_no: int
    worker_ref: str
    file_id: UUID
    member_count: int
    membership_hash: str
    membership_version: str
    created_at: datetime

    def __post_init__(self):
        if any(type(v) is not UUID or not v.int for v in (self.render_attempt_id,self.export_id,self.job_id,self.file_id)):
            raise AuditExportWorkerError()
        if (type(self.fencing_token) is not int or not 0<self.fencing_token<2**63
                or type(self.attempt_no) is not int or not 0<self.attempt_no<2**31
                or type(self.worker_ref) is not str or not fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",self.worker_ref)
                or type(self.member_count) is not int or not 0<=self.member_count<=100000
                or type(self.membership_hash) is not str or not fullmatch(r"[0-9a-f]{64}",self.membership_hash)
                or self.membership_version!=MEMBERSHIP_VERSION
                or type(self.created_at) is not datetime or self.created_at.tzinfo is None
                or self.created_at.utcoffset()!=timedelta(0)):
            raise AuditExportWorkerError()


class AuditRenderPlanRepositoryPort(Protocol):
    def register(self,tx:object,*,intent,capture,claim,worker_ref:str)->AuditRenderPlan: ...


class AuditExportWorkerRenderPlan(AuditExportWorkerCapture):
    """Shared capture worker checks; plan is a separate short, DB-only operation."""
    def __init__(self,*,plans:AuditRenderPlanRepositoryPort,**dependencies):
        if plans is None:raise ValueError("Render plan repository required")
        super().__init__(**dependencies)
        self._plans=plans

    def plan(self,command)->AuditRenderPlan:
        return self._run(command,self._plan)

    def _plan(self,c):
        with self._uow() as tx:
            intent,request,claim,capture,result=self._prepared(tx,c)
            if self._authority.assert_current(tx,request=request) is not None:raise AuditExportWorkerError()
            if self._lease(tx,c,intent)!=claim:raise AuditExportWorkerError()
            tx.commit()
            return result

    def _prepared(self,tx,c):
        intent,request,claim=self._authorized(tx,c,"RENDER")
        capture=self._captures.read_capture(tx,request=request)
        self._result(capture,intent)
        result=self._plans.register(tx,intent=intent,capture=capture,claim=claim,worker_ref=c.worker_ref)
        if type(result) is not AuditRenderPlan:raise AuditExportWorkerError()
        result.__post_init__()
        if ((result.export_id,result.job_id,result.fencing_token,result.attempt_no,result.worker_ref,
             result.member_count,result.membership_hash,result.membership_version)
                !=(intent.export_id,c.job_id,c.fencing_token,claim.attempt_no,c.worker_ref,
                   capture.member_count,capture.membership_hash,capture.membership_version)
                or result.created_at<capture.captured_at):raise AuditExportWorkerError()
        return intent,request,claim,capture,result
