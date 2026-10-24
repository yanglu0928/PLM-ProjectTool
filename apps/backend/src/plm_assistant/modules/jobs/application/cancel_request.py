"""Explicit Owner dispatch; hints never replace current Owner write authority."""
from dataclasses import dataclass,field
from uuid import UUID
import unicodedata
from .authorized_read import JobReadFacts
from plm_assistant.modules.platform.application.idempotency import validate_idempotency_key,IdempotencyError
from plm_assistant.modules.auth.application.session_service import SessionError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

class JobCancelError(RuntimeError):
    def __init__(self,code='JOB_UNAVAILABLE'):self.code=code;super().__init__(code)

@dataclass(frozen=True,slots=True)
class RequestProjectJobCancel:
    job_id:UUID
    project_id:UUID
    session_token:bytes=field(repr=False)
    csrf_token:bytes=field(repr=False)
    trace_id:UUID
    reason:str=field(repr=False)
    expected_version:int
    def __post_init__(self):
        if (any(type(v) is not UUID or not v.int for v in (self.job_id,self.project_id,self.trace_id))
            or any(type(v) is not bytes or len(v)!=32 for v in (self.session_token,self.csrf_token))
            or type(self.reason) is not str or not 1<=len(self.reason)<=1024 or self.reason.strip()!=self.reason
            or any(unicodedata.category(c).startswith('C') for c in self.reason)
            or type(self.expected_version) is not int or not 0<=self.expected_version<=2**63-1):raise JobCancelError('VALIDATION_FAILED')

@dataclass(frozen=True,slots=True)
class JobCancelResult:
    job_id:UUID
    state:str
    changed:bool
    lock_version:int
    def __post_init__(self):
        if (type(self.job_id) is not UUID or not self.job_id.int or type(self.state) is not str
            or self.state not in ('CANCEL_REQUESTED','CANCELLED','SUCCEEDED','FAILED') or type(self.changed) is not bool
            or self.changed and self.state in ('SUCCEEDED','FAILED')
            or type(self.lock_version) is not int or not 0<=self.lock_version<=2**63-1):raise JobCancelError()

class ProjectJobCancellation:
    def __init__(self,*,unit_of_work,repository,sessions,license_guard,owners):
        if any(v is None for v in (unit_of_work,repository,sessions,license_guard)):
            raise ValueError('Current Job cancellation dependencies required')
        if type(owners) is not dict or not owners or any(type(k) is not tuple or len(k)!=2
            or any(type(x) is not str or not x for x in k) or not callable(getattr(v,'cancel',None)) for k,v in owners.items()):
            raise ValueError('Explicit cancellation Owner registry required')
        self._uow,self._repo,self._sessions,self._guard,self._owners=unit_of_work,repository,sessions,license_guard,dict(owners)
    def cancel(self,c,*,idempotency_key):
        if type(c) is not RequestProjectJobCancel:raise JobCancelError('VALIDATION_FAILED')
        c.__post_init__()
        try:
            validate_idempotency_key(idempotency_key)
            self._guard.require_valid(trace_id=c.trace_id)
            self._sessions.validate(c.session_token,csrf_token=c.csrf_token,require_csrf=True)
            with self._uow() as tx:
                facts=self._repo.get(tx,job_id=c.job_id)
                if facts is None:raise JobCancelError('RESOURCE_NOT_FOUND')
                if type(facts) is not JobReadFacts:raise JobCancelError()
                facts.__post_init__()
                if facts.job_id!=c.job_id:raise JobCancelError()
                if (facts.scope,facts.project_id)!=('PROJECT',c.project_id):raise JobCancelError('RESOURCE_NOT_FOUND')
                owner=self._owners.get((facts.owner_module,facts.job_type))
                if owner is None:raise JobCancelError('RESOURCE_NOT_FOUND')
            # Owner MUST reauthorize and bind actual sources inside its write UOW.
            result=owner.cancel(c,idempotency_key=idempotency_key)
            if type(result) is not JobCancelResult or result.job_id!=c.job_id:raise JobCancelError()
            result.__post_init__();return result
        except JobCancelError:raise
        except IdempotencyError as exc:raise JobCancelError(exc.code) from None
        except SessionError as exc:
            code={'AUTH_ACCESS_DENIED':'AUTH_CSRF_INVALID','AUTH_SESSION_EXPIRED':'AUTH_SESSION_EXPIRED'}.get(exc.code,'JOB_UNAVAILABLE')
            raise JobCancelError(code) from None
        except RuntimeLicenseError:raise JobCancelError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise JobCancelError() from None
