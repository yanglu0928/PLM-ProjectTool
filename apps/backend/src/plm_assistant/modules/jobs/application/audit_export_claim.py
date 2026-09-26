"""Audit-only owned claim primitives; candidate is NOT authority or a claim."""
from dataclasses import dataclass
from uuid import UUID
from .lease import ClaimedJob,JobLeaseError,JobLeaseService


def validate_claim_input(worker_ref,lease_seconds):
    if type(worker_ref) is not str:raise JobLeaseError('INVALID_WORKER')
    JobLeaseService._validate_worker(worker_ref)
    if type(lease_seconds) is not int or not 3<=lease_seconds<=3600:raise JobLeaseError('INVALID_LEASE_DURATION')


@dataclass(frozen=True,slots=True)
class AuditExportClaimCandidate:
    job_id: UUID
    export_id: UUID
    current_fencing_token: int

    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.job_id,self.export_id))
                or type(self.current_fencing_token) is not int or not 0<=self.current_fencing_token<2**63-1):
            raise JobLeaseError('JOB_STORE_UNAVAILABLE')


class AuditExportClaims:
    def __init__(self,*,repository):
        if repository is None:raise ValueError('Owned claim repository required')
        self._repo=repository

    def peek_next(self,tx):
        try:
            candidate=self._repo.peek_next(tx)
            if candidate is not None:
                if type(candidate) is not AuditExportClaimCandidate:raise JobLeaseError('JOB_STORE_UNAVAILABLE')
                candidate.__post_init__()
            return candidate
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def claim_target(self,tx,*,job_id,worker_ref,lease_seconds):
        validate_claim_input(worker_ref,lease_seconds)
        if type(job_id) is not UUID or not job_id.int:raise JobLeaseError('VALIDATION_FAILED')
        try:
            claim=self._repo.claim_target(tx,job_id=job_id,worker_ref=worker_ref,lease_seconds=lease_seconds)
            if claim is not None and (type(claim) is not ClaimedJob or claim.job_id!=job_id):raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return claim
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None

    def check_target(self,tx,*,job_id,fencing_token,worker_ref):
        from .lease_checkpoint import validate_checkpoint
        validate_checkpoint(job_id=job_id,fencing_token=fencing_token,worker_ref=worker_ref)
        try:
            value=self._repo.check_target(tx,job_id=job_id,fencing_token=fencing_token,worker_ref=worker_ref)
            if type(value) is not ClaimedJob or (value.job_id,value.fencing_token)!=(job_id,fencing_token):raise JobLeaseError('JOB_STORE_UNAVAILABLE')
            return value
        except JobLeaseError:raise
        except Exception:raise JobLeaseError('JOB_STORE_UNAVAILABLE') from None
