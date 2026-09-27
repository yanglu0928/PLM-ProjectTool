"""Current DeploymentAdmin-only user metadata, never credential secrets."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


class UserReadError(RuntimeError):
    def __init__(self, code='AUTH_READ_UNAVAILABLE'):
        self.code=code
        super().__init__(code)


def _id(value):return type(value) is UUID and bool(value.int)
def _time(value):return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


@dataclass(frozen=True, slots=True)
class UserGetQuery:
    session_token:bytes=field(repr=False)
    user_id:UUID
    trace_id:UUID
    def __post_init__(self):
        if (type(self.session_token) is not bytes or len(self.session_token)!=32
            or not _id(self.user_id) or not _id(self.trace_id)):raise UserReadError('VALIDATION_FAILED')


@dataclass(frozen=True, slots=True)
class UserReadView:
    user_id:UUID
    username_display:str
    account_state:str
    deployment_role:str
    credential_version:int
    created_at:datetime
    updated_at:datetime
    lock_version:int
    def __post_init__(self):
        if (not _id(self.user_id) or type(self.username_display) is not str or not 1<=len(self.username_display)<=255
            or type(self.account_state) is not str or self.account_state not in ('ENABLED','DISABLED')
            or type(self.deployment_role) is not str or self.deployment_role not in ('NONE','DEPLOYMENT_ADMIN')
            or any(type(v) is not int or not 0<=v<=9223372036854775807 for v in (self.credential_version,self.lock_version))
            or self.account_state=='ENABLED' and self.credential_version==0
            or not _time(self.created_at) or not _time(self.updated_at) or self.updated_at<self.created_at):
            raise UserReadError()


class AuthorizedUserReadService:
    def __init__(self, *, unit_of_work, access, repository, license_guard, clock=None):
        if any(v is None for v in (unit_of_work,access,repository,license_guard)):
            raise ValueError('Actual current User read dependencies required')
        self._uow,self._access,self._repo,self._guard=unit_of_work,access,repository,license_guard
        self._clock=clock or (lambda:datetime.now(timezone.utc))

    def get(self,query):
        if type(query) is not UserGetQuery:raise UserReadError('VALIDATION_FAILED')
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now=self._clock()
                if not _time(now):raise UserReadError()
                actor=self._access.authorized_admin(tx,session_token=query.session_token,now=now)
                if not _id(actor):raise UserReadError('AUTH_ACCESS_DENIED')
                view=self._repo.get(tx,user_id=query.user_id)
                if view is None:raise UserReadError('RESOURCE_NOT_FOUND')
                if type(view) is not UserReadView:raise UserReadError()
                view.__post_init__()
                if view.user_id!=query.user_id:raise UserReadError()
                self._guard.require_valid(trace_id=query.trace_id)
                return view
        except UserReadError:raise
        except RuntimeLicenseError:raise UserReadError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise UserReadError() from None
