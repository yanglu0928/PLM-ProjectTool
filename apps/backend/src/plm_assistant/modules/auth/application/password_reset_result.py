"""Immutable reset first coordinates, never current Admin authority."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from .user_read import _id,_time


@dataclass(frozen=True,slots=True)
class PasswordResetResult:
    result_id:UUID
    user_id:UUID
    actor_id:UUID
    before_credential_id:UUID
    credential_id:UUID
    before_credential_version:int
    credential_version:int
    before_user_version:int
    user_version:int
    target_state:str
    audit_event_id:UUID
    trace_id:UUID
    revoked_session_count:int
    changed_at:datetime
    accepted_at:datetime

    def __post_init__(self):
        try:
            if (any(not _id(v) for v in (self.result_id,self.user_id,self.actor_id,self.before_credential_id,
                self.credential_id,self.audit_event_id,self.trace_id))
                or self.before_credential_id==self.credential_id
                or any(type(v) is not int for v in (self.before_credential_version,self.credential_version,
                    self.before_user_version,self.user_version,self.revoked_session_count))
                or not 1<=self.before_credential_version<9223372036854775807
                or self.credential_version!=self.before_credential_version+1
                or not 0<=self.before_user_version<9223372036854775807
                or self.user_version!=self.before_user_version+1
                or not 0<=self.revoked_session_count<=9223372036854775807
                or type(self.target_state) is not str or self.target_state not in ('ENABLED','DISABLED')
                or not _time(self.changed_at) or not _time(self.accepted_at) or self.accepted_at<self.changed_at):
                raise ValueError()
        except Exception:raise ValueError('AUTH_PASSWORD_RESET_RESULT_UNAVAILABLE') from None

    def public_data(self):
        self.__post_init__()
        return {'credential_version':self.credential_version}
