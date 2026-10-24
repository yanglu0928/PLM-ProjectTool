"""Private locked pre-change actor, valid for normal and restricted identity."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from .user_read import UserReadView,_id,_time


@dataclass(frozen=True,slots=True)
class PasswordChangeActorProof:
    user_view: UserReadView
    credential_id: UUID
    password_change_required: bool
    session_id: UUID
    session_version: int
    session_created_at: datetime
    session_idle_expires_at: datetime
    session_absolute_expires_at: datetime

    def __post_init__(self):
        try:
            if type(self.user_view) is not UserReadView:raise ValueError()
            self.user_view.__post_init__()
            if (self.user_view.account_state!='ENABLED' or not _id(self.credential_id) or not _id(self.session_id)
                or type(self.password_change_required) is not bool or type(self.session_version) is not int
                or not 0<=self.session_version<=9223372036854775807
                or any(not _time(v) for v in (self.session_created_at,self.session_idle_expires_at,self.session_absolute_expires_at))
                or not self.session_created_at<self.session_idle_expires_at<=self.session_absolute_expires_at):
                raise ValueError()
        except Exception:raise ValueError('AUTH_PASSWORD_ACTOR_UNAVAILABLE') from None
