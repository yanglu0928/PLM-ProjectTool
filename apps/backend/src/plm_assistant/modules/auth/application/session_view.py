"""Public-safe login identity projection; project ownership stays outside Auth."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from plm_assistant.modules.project.application.public import ProjectAccessSummary


AuthorizedProjectSummary = ProjectAccessSummary


@dataclass(frozen=True, slots=True)
class LoginSessionView:
    user_id: uuid.UUID
    username_display: str
    deployment_role: str
    authorized_projects: tuple[AuthorizedProjectSummary, ...]
    password_change_required: bool = False

    def public_data(self) -> dict[str, object]:
        if type(self.password_change_required) is not bool:
            raise ValueError('Current password state unavailable')
        return {
            "user": {"user_id": str(self.user_id), "username_display": self.username_display},
            "deployment_role": "NONE" if self.password_change_required else self.deployment_role,
            "password_change_required": self.password_change_required,
            "authorized_projects": [
                {"project_id": str(item.project_id), "name": item.name, "role": item.role}
                for item in (() if self.password_change_required else self.authorized_projects)
            ],
        }


class SessionViewPort(Protocol):
    def resolve(self, user_id: uuid.UUID) -> LoginSessionView: ...


def resolve_session_view(views, user_id, session_token):
    """Production source binds token; legacy opt-in projections retain their API."""
    bound = getattr(views, 'resolve_for_session', None)
    if bound is not None:
        if not callable(bound):
            raise ValueError('Session projection unavailable')
        return bound(user_id=user_id, session_token=session_token)
    return views.resolve(user_id)
