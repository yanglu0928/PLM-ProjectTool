"""Bounded current Admin user metadata pages; positions are internal only."""
from dataclasses import dataclass, field
from datetime import datetime,timezone
from uuid import UUID
from .user_read import UserReadView,UserReadError,_id,_time
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError


def _position(value):
    return type(value) is tuple and len(value)==2 and _time(value[0]) and _id(value[1])


@dataclass(frozen=True,slots=True)
class UserListQuery:
    session_token:bytes=field(repr=False)
    trace_id:UUID
    page_size:int=50
    before:tuple[datetime,UUID]|None=field(default=None,repr=False)
    def __post_init__(self):
        if (type(self.session_token) is not bytes or len(self.session_token)!=32 or not _id(self.trace_id)
            or type(self.page_size) is not int or not 1<=self.page_size<=200
            or self.before is not None and not _position(self.before)):raise UserReadError('VALIDATION_FAILED')


@dataclass(frozen=True,slots=True)
class UserListPage:
    items:tuple[UserReadView,...]
    has_more:bool
    next_position:tuple[datetime,UUID]|None=field(default=None,repr=False)
    def __post_init__(self):
        if (type(self.items) is not tuple or len(self.items)>200 or type(self.has_more) is not bool
            or self.has_more!=(self.next_position is not None)
            or self.next_position is not None and not _position(self.next_position)):
            raise UserReadError()
        for item in self.items:
            if type(item) is not UserReadView:raise UserReadError()
            item.__post_init__()
        positions=[(item.created_at,item.user_id) for item in self.items]
        if (len({item.user_id for item in self.items})!=len(self.items)
            or any(a<=b for a,b in zip(positions,positions[1:]))
            or self.has_more and (not positions or self.next_position!=positions[-1])):raise UserReadError()


class AuthorizedUserListService:
    def __init__(self,*,unit_of_work,access,repository,license_guard,clock=None):
        if any(v is None for v in (unit_of_work,access,repository,license_guard)):
            raise ValueError('Actual current User list dependencies required')
        self._uow,self._access,self._repo,self._guard=unit_of_work,access,repository,license_guard
        self._clock=clock or (lambda:datetime.now(timezone.utc))
    def list(self,query):
        if type(query) is not UserListQuery:raise UserReadError('VALIDATION_FAILED')
        query.__post_init__()
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            with self._uow() as tx:
                now=self._clock()
                if not _time(now):raise UserReadError()
                actor=self._access.authorized_admin(tx,session_token=query.session_token,now=now)
                if not _id(actor):raise UserReadError('AUTH_ACCESS_DENIED')
                page=self._repo.list(tx,page_size=query.page_size,before=query.before)
                if type(page) is not UserListPage:raise UserReadError()
                page.__post_init__()
                if (len(page.items)>query.page_size or page.has_more and len(page.items)!=query.page_size
                    or query.before is not None and any((item.created_at,item.user_id)>=query.before for item in page.items)):
                    raise UserReadError()
                self._guard.require_valid(trace_id=query.trace_id)
                return page
        except UserReadError:raise
        except RuntimeLicenseError:raise UserReadError('LICENSE_OPERATION_DENIED') from None
        except Exception:raise UserReadError() from None
