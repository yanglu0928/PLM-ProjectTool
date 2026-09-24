"""Public-safe login identity projection; project ownership stays outside Auth."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AuthorizedProjectSummary:
    project_id: uuid.UUID
    name: str
    role: str


@dataclass(frozen=True, slots=True)
class LoginSessionView:
    user_id: uuid.UUID
    username_display: str
    deployment_role: str
    authorized_projects: tuple[AuthorizedProjectSummary, ...]

    def public_data(self) -> dict[str, object]:
        return {
            "user": {"user_id": str(self.user_id), "username_display": self.username_display},
            "deployment_role": self.deployment_role,
            "authorized_projects": [
                {"project_id": str(item.project_id), "name": item.name, "role": item.role}
                for item in self.authorized_projects
            ],
        }


class SessionViewPort(Protocol):
    def resolve(self, user_id: uuid.UUID) -> LoginSessionView: ...
