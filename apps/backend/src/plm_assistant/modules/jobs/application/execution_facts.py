"""Internal execution hints only, NEVER lease authority or terminal receipt."""
from dataclasses import dataclass,field
from re import fullmatch
from .lease import ClaimedJob,JobLeaseError
from .lease_checkpoint import validate_checkpoint
from .audit_export_enqueue import AuditExportJobRequest,AuditExportJobRef
from .audit_export_complete import AuditExportJobCompletion


@dataclass(frozen=True,slots=True)
class AuditExportExecutionFacts:
    claim: ClaimedJob
    current_fencing_token: int
    state: str
    lease_state: str
    lease_alive: bool
    error_code: str|None=field(repr=False)

    def __post_init__(self):
        if (type(self.claim) is not ClaimedJob or type(self.current_fencing_token) is not int
                or type(self.claim.fencing_token) is not int or not 0<self.claim.fencing_token<=self.current_fencing_token
                or type(self.claim.attempt_no) is not int or not 1<=self.claim.attempt_no<=3
                or type(self.state) is not str or self.state not in {'RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED'}
                or type(self.lease_state) is not str or self.lease_state not in {'ACTIVE','RELEASED','EXPIRED'}
                or type(self.lease_alive) is not bool or (self.lease_alive and self.lease_state!='ACTIVE')
                or (self.error_code is not None and (type(self.error_code) is not str or fullmatch(r'[A-Z0-9_]{1,64}',self.error_code) is None))):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')
        current=self.claim.fencing_token==self.current_fencing_token
        if ((self.lease_state=='ACTIVE' and (not current or self.state not in {'RUNNING','CANCEL_REQUESTED'} or self.error_code is not None))
                or (current and self.lease_state!='ACTIVE' and self.state not in {'RETRY_WAIT','SUCCEEDED','FAILED','CANCELLED'})):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')

    @property
    def is_current(self):return self.claim.fencing_token==self.current_fencing_token


class AuditExportExecutionRead:
    def __init__(self,*,queue,leases):
        if queue is None or leases is None:raise ValueError('Owned execution fact dependencies required')
        self._queue,self._leases=queue,leases

    def read(self,transaction,*,request,refs,fencing_token,worker_ref):
        if type(request) is not AuditExportJobRequest or type(refs) is not AuditExportJobRef:raise JobLeaseError('VALIDATION_FAILED')
        try:
            request.__post_init__();refs.__post_init__()
            validate_checkpoint(job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            actual=self._queue.find_export(transaction,request=request)
            if type(actual) is not AuditExportJobRef or actual!=refs:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            actual.__post_init__()
            facts=self._leases.read_execution_facts(transaction,job_id=refs.job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            if type(facts) is not AuditExportExecutionFacts:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            facts.__post_init__();AuditExportJobCompletion._claim(facts.claim,request,refs,fencing_token)
            return facts
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
