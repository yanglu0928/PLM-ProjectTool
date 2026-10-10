"""Strict immutable first state response; never current authorization."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from .user_read import UserReadView, _id, _time


class UserStateResultError(ValueError):
    def __init__(self):
        super().__init__('AUTH_STATE_RESULT_UNAVAILABLE')


@dataclass(frozen=True, slots=True)
class UserStateResult:
    result_id: UUID
    first_view: UserReadView
    actor_id: UUID
    audit_event_id: UUID
    trace_id: UUID
    operation: str
    expected_version: int
    revoked_session_count: int
    accepted_at: datetime

    def __post_init__(self):
        try:
            if type(self.first_view) is not UserReadView:
                raise UserStateResultError()
            self.first_view.__post_init__()
            view = self.first_view
            if (any(not _id(v) for v in (self.result_id,self.actor_id,self.audit_event_id,self.trace_id))
                or type(self.operation) is not str or self.operation not in ('ENABLE','DISABLE')
                or type(self.expected_version) is not int or not 0 <= self.expected_version < 9223372036854775807
                or view.lock_version != self.expected_version+1
                or view.credential_version == 0
                or view.account_state != ('ENABLED' if self.operation=='ENABLE' else 'DISABLED')
                or type(self.revoked_session_count) is not int or not 0 <= self.revoked_session_count <= 9223372036854775807
                or self.operation=='ENABLE' and self.revoked_session_count!=0
                or not _time(self.accepted_at) or self.accepted_at < view.updated_at):
                raise UserStateResultError()
        except Exception:
            raise UserStateResultError() from None
