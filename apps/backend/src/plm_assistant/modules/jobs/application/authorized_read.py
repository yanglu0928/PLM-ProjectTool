"""Current same-UOW Job metadata; explicit Owner policy, no raw payload/Lease."""
from dataclasses import dataclass,field
from datetime import datetime,timezone
from uuid import UUID
from typing import Protocol
from plm_assistant.modules.project.application.authorization import AuthorizedProjectAction,ProjectAuthorizationError,ALL_MEMBERS
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError

class JobReadError(RuntimeError):
    def __init__(self,code='JOB_UNAVAILABLE'):
        self.code=code
        super().__init__(code)

def _id(v):return type(v) is UUID and bool(v.int)
def _time(v):return type(v) is datetime and v.tzinfo is not None and v.utcoffset() is not None

@dataclass(frozen=True,slots=True)
class JobGetQuery:
    session_token:bytes=field(repr=False)
    project_id:UUID|None
    trace_id:UUID
    job_id:UUID
    def __post_init__(self):
        if (type(self.session_token) is not bytes or len(self.session_token)!=32
            or not _id(self.trace_id) or not _id(self.job_id)
            or self.project_id is not None and not _id(self.project_id)):raise JobReadError('VALIDATION_FAILED')

@dataclass(frozen=True,slots=True)
class JobReadFacts:
    job_id:UUID
    owner_module:str
    job_type:str
    scope:str
    project_id:UUID|None
    actor_id:UUID|None
    state:str
    attempt_count:int
    created_at:datetime
    completed_at:datetime|None
    def __post_init__(self):
        if (not _id(self.job_id) or any(type(v) is not str or not v or len(v)>64 or not v.isascii()
            or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in v)
            for v in (self.owner_module,self.job_type))
            or type(self.scope) is not str or self.scope not in ('PROJECT','DEPLOYMENT','GLOBAL')
            or (self.scope=='PROJECT' and not _id(self.project_id))
            or (self.scope!='PROJECT' and self.project_id is not None)
            or self.actor_id is not None and not _id(self.actor_id)
            or type(self.state) is not str or self.state not in ('PENDING','RUNNING','RETRY_WAIT','SUCCEEDED','FAILED','CANCEL_REQUESTED','CANCELLED')
            or type(self.attempt_count) is not int or not 0<=self.attempt_count<=2147483647
            or not _time(self.created_at) or self.completed_at is not None and (not _time(self.completed_at) or self.completed_at<self.created_at)
            or (self.state in ('SUCCEEDED','FAILED','CANCELLED'))!=(self.completed_at is not None)):
            raise JobReadError()

@dataclass(frozen=True,slots=True)
class JobOwnerProjection:
    """Explicit Owner result; policy implementation trusted, never client input."""
    job_id:UUID
    retryable:bool
    result_type:str|None=None
    result_id:UUID|None=None
    def __post_init__(self):
        if (not _id(self.job_id) or type(self.retryable) is not bool
            or (self.result_type,self.result_id)!=(None,None)
            and (type(self.result_type) is not str or self.result_type!='AUDIT_EXPORT' or not _id(self.result_id))):raise JobReadError()

@dataclass(frozen=True,slots=True)
class JobDetail:
    facts:JobReadFacts
    owner:JobOwnerProjection
    def __post_init__(self):
        if type(self.facts) is not JobReadFacts or type(self.owner) is not JobOwnerProjection:raise JobReadError()
        self.facts.__post_init__();self.owner.__post_init__()
        if self.facts.job_id!=self.owner.job_id or self.owner.result_id is not None and self.facts.state!='SUCCEEDED':raise JobReadError()

class JobReadRepositoryPort(Protocol):
    def get(self,tx:object,*,job_id:UUID)->JobReadFacts|None: ...

class JobReadOwnerPort(Protocol):
    def project(self,tx:object,*,facts:JobReadFacts,actor_id:UUID,project_role:str|None)->JobOwnerProjection:
        """Recheck original resource/actor bindings in this UOW; no writes or content."""
        ...

class AuthorizedJobReadService:
    def __init__(self,*,unit_of_work,project_access,deployment_access,projects,license_guard,repository,owners,clock=None):
        if any(v is None for v in (unit_of_work,project_access,deployment_access,projects,license_guard,repository)):
            raise ValueError('Current read dependencies required')
        if type(owners) is not dict or not owners or any(type(k) is not tuple or len(k)!=2
            or any(type(x) is not str or not x for x in k) or not callable(getattr(v,'project',None)) for k,v in owners.items()):
            raise ValueError('Explicit Owner policy registry required')
        self._uow,self._project,self._deployment,self._projects,self._guard,self._repo=unit_of_work,project_access,deployment_access,projects,license_guard,repository
        self._owners=dict(owners);self._clock=clock or (lambda:datetime.now(timezone.utc))
    def get(self,q):
        if type(q) is not JobGetQuery:raise JobReadError('VALIDATION_FAILED')
        q.__post_init__()
        try:
            self._guard.require_valid(trace_id=q.trace_id)
            with self._uow() as tx:
                now=self._clock()
                if not _time(now):raise JobReadError()
                actor=(self._deployment.authorized_admin if q.project_id is None else self._project.authenticated_user)(tx,session_token=q.session_token,now=now)
                if not _id(actor):raise JobReadError('AUTH_ACCESS_DENIED')
                role=None
                if q.project_id is not None:
                    proof=self._projects.require_in_transaction(tx,user_id=actor,project_id=q.project_id,operation='JOB_PROJECT_GET')
                    if (type(proof) is not AuthorizedProjectAction or (proof.user_id,proof.project_id,proof.operation)!=(actor,q.project_id,'JOB_PROJECT_GET')
                        or proof.project_role not in ALL_MEMBERS):raise JobReadError('RESOURCE_NOT_FOUND')
                    role=proof.project_role
                facts=self._repo.get(tx,job_id=q.job_id)
                if facts is None:raise JobReadError('RESOURCE_NOT_FOUND')
                if type(facts) is not JobReadFacts:raise JobReadError()
                facts.__post_init__()
                if facts.job_id!=q.job_id:raise JobReadError()
                if facts.project_id!=q.project_id or (q.project_id is None and facts.scope=='PROJECT'):raise JobReadError('RESOURCE_NOT_FOUND')
                if role not in (None,'PROJECT_MANAGER','IMPLEMENTATION_MEMBER') and facts.actor_id!=actor:raise JobReadError('RESOURCE_NOT_FOUND')
                owner=self._owners.get((facts.owner_module,facts.job_type))
                if owner is None:raise JobReadError('RESOURCE_NOT_FOUND')
                projection=owner.project(tx,facts=facts,actor_id=actor,project_role=role)
                result=JobDetail(facts,projection);result.__post_init__()
                again=self._repo.get(tx,job_id=q.job_id)
                if type(again) is not JobReadFacts or again!=facts:raise JobReadError()
                again.__post_init__()
                self._guard.require_valid(trace_id=q.trace_id)
                return result
        except JobReadError:raise
        except ProjectAuthorizationError:raise JobReadError('RESOURCE_NOT_FOUND') from None
        except RuntimeLicenseError:raise JobReadError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise JobReadError() from None
