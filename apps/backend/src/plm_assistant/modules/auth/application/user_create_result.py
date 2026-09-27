"""Immutable first safe User view. Neither authorization nor password proof."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from plm_assistant.modules.auth.application.user_read import UserReadView, _id, _time


class UserCreateResultError(RuntimeError):
    def __init__(self):
        super().__init__('AUTH_CREATE_RESULT_UNAVAILABLE')


@dataclass(frozen=True, slots=True)
class UserCreateResult:
    first_view: UserReadView
    credential_id: UUID
    actor_id: UUID
    audit_event_id: UUID
    trace_id: UUID
    accepted_at: datetime

    def __post_init__(self):
        try:
            if type(self.first_view) is not UserReadView:
                raise UserCreateResultError()
            self.first_view.__post_init__()
            view = self.first_view
            if (
                any(not _id(v) for v in (self.credential_id, self.actor_id, self.audit_event_id, self.trace_id))
                or view.user_id == self.actor_id
                or view.account_state != 'ENABLED' or view.deployment_role != 'NONE'
                or view.credential_version != 1 or view.lock_version != 1
                or not _time(self.accepted_at) or self.accepted_at < view.updated_at
            ):
                raise UserCreateResultError()
        except Exception:
            raise UserCreateResultError() from None
