"""Current read proof selects Owner; actual mutation reauthorizes in Owner UOW."""
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from .authorized_read import JobGetQuery, JobDetail, JobReadError
from plm_assistant.modules.platform.application.idempotency import validate_idempotency_key, IdempotencyError
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

class JobRetryError(RuntimeError):
    def __init__(self,code='JOB_UNAVAILABLE'):self.code=code;super().__init__(code)

@dataclass(frozen=True, slots=True)
class RequestJobRetry:
    job_id: UUID
    project_id: UUID|None
    session_token: bytes=field(repr=False)
    csrf_token: bytes=field(repr=False)
    trace_id: UUID
    expected_version: int
    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.job_id,self.trace_id))
            or self.project_id is not None and (type(self.project_id) is not UUID or not self.project_id.int)
            or any(type(v) is not bytes or len(v)!=32 for v in (self.session_token,self.csrf_token))
            or type(self.expected_version) is not int or not 0<=self.expected_version<=9223372036854775807):
            raise JobRetryError('VALIDATION_FAILED')

@dataclass(frozen=True, slots=True)
class JobRetryResult:
    source_job_id: UUID
    job_id: UUID
    project_id: UUID|None
    scope: str
    accepted_at: datetime
    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.source_job_id,self.job_id))
            or self.source_job_id==self.job_id or type(self.scope) is not str or self.scope not in ('PROJECT','DEPLOYMENT','GLOBAL')
            or self.scope=='PROJECT' and (type(self.project_id) is not UUID or not self.project_id.int)
            or self.scope!='PROJECT' and self.project_id is not None
            or type(self.accepted_at) is not datetime or self.accepted_at.tzinfo is None or self.accepted_at.utcoffset() is None):
            raise JobRetryError()

class JobRetryRequests:
    def __init__(self,*,reads,sessions,license_guard,owners):
        if any(v is None for v in (reads,sessions,license_guard)):raise ValueError('Actual current retry dependencies required')
        if (type(owners) is not dict or not owners or any(type(k) is not tuple or len(k)!=2
            or any(type(x) is not str or not x for x in k) or not callable(getattr(v,'retry',None)) for k,v in owners.items())):
            raise ValueError('Explicit retry Owner registry required')
        self._reads,self._sessions,self._guard,self._owners=reads,sessions,license_guard,dict(owners)
    def retry(self,c,*,idempotency_key):
        if type(c) is not RequestJobRetry:raise JobRetryError('VALIDATION_FAILED')
        c.__post_init__()
        try:
            validate_idempotency_key(idempotency_key)
            self._guard.require_valid(trace_id=c.trace_id)
            self._sessions.validate(c.session_token,csrf_token=c.csrf_token,require_csrf=True)
            detail=self._reads.get(JobGetQuery(c.session_token,c.project_id,c.trace_id,c.job_id))
            if type(detail) is not JobDetail:raise JobRetryError()
            detail.__post_init__()
            if detail.facts.job_id!=c.job_id or detail.facts.project_id!=c.project_id:raise JobRetryError()
            owner=self._owners.get((detail.facts.owner_module,detail.facts.job_type))
            if owner is None:raise JobRetryError('JOB_NOT_RETRYABLE')
            result=owner.retry(c,idempotency_key=idempotency_key)
            if type(result) is not JobRetryResult or (result.source_job_id,result.project_id,result.scope)!=(
                c.job_id,c.project_id,detail.facts.scope):raise JobRetryError()
            result.__post_init__();return result
        except JobRetryError:raise
        except IdempotencyError as exc:raise JobRetryError(exc.code) from None
        except SessionError as exc:
            raise JobRetryError({'AUTH_ACCESS_DENIED':'AUTH_CSRF_INVALID','AUTH_SESSION_EXPIRED':'AUTH_SESSION_EXPIRED'}.get(exc.code,'JOB_UNAVAILABLE')) from None
        except RuntimeLicenseError:raise JobRetryError('LICENSE_OPERATION_DENIED') from None
        except JobReadError as exc:
            raise JobRetryError({'AUTH_ACCESS_DENIED':'AUTH_SESSION_EXPIRED','RESOURCE_NOT_FOUND':'RESOURCE_NOT_FOUND',
                'LICENSE_OPERATION_DENIED':'LICENSE_OPERATION_DENIED'}.get(exc.code,'JOB_UNAVAILABLE')) from None
        except Exception:raise JobRetryError() from None
