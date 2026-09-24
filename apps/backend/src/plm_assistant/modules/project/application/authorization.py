"""Project-owned operation policy; caller supplies an authenticated UserId."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


ALL_MEMBERS = frozenset({
    "PROJECT_MANAGER", "IMPLEMENTATION_MEMBER", "CUSTOMER_MANAGER", "CUSTOMER_MEMBER",
})
MANAGERS = frozenset({"PROJECT_MANAGER"})
MEMBER_READERS = frozenset({"PROJECT_MANAGER", "CUSTOMER_MANAGER"})


@dataclass(frozen=True, slots=True)
class _Policy:
    roles: frozenset[str]
    write: bool
    target: str | None = None


POLICIES: dict[str, _Policy] = {
    "PROJECT_GET": _Policy(ALL_MEMBERS, False),
    "PROJECT_PATCH": _Policy(MANAGERS, True),
    "PROJECT_ARCHIVE": _Policy(MANAGERS, True),
    "PROJECT_MEMBER_LIST": _Policy(MEMBER_READERS, False),
    "PROJECT_MEMBER_CREATE": _Policy(MANAGERS, True),
    "PROJECT_MEMBER_PATCH": _Policy(MANAGERS, True, "MEMBER"),
    "PROJECT_MEMBER_SUSPEND": _Policy(MANAGERS, True, "MEMBER"),
    "PROJECT_MEMBER_RESUME": _Policy(MANAGERS, True, "MEMBER"),
    "PROJECT_MEMBER_REMOVE": _Policy(MANAGERS, True, "MEMBER"),
    "PROJECT_DEPARTMENT_LIST": _Policy(ALL_MEMBERS, False),
    "PROJECT_DEPARTMENT_CREATE": _Policy(MANAGERS, True),
    "PROJECT_DEPARTMENT_PATCH": _Policy(MANAGERS, True, "DEPARTMENT"),
    "PROJECT_DEPARTMENT_DEACTIVATE": _Policy(MANAGERS, True, "DEPARTMENT"),
}


class ProjectAuthorizationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ProjectActorFacts:
    project_state: str
    project_role: str


@dataclass(frozen=True, slots=True)
class AuthorizedProjectAction:
    user_id: uuid.UUID
    project_id: uuid.UUID
    operation: str
    project_role: str


class ProjectAuthorizationRepositoryPort(Protocol):
    def actor_facts(self, transaction: object, *, user_id: uuid.UUID,
                    project_id: uuid.UUID) -> ProjectActorFacts | None: ...
    def owner_project_id(self, transaction: object, *, target: str,
                         resource_id: uuid.UUID) -> uuid.UUID | None: ...


class ProjectAuthorizationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 repository: ProjectAuthorizationRepositoryPort) -> None:
        if unit_of_work is None or repository is None:
            raise ValueError("Project authorization dependencies are required")
        self._uow, self._repository = unit_of_work, repository

    def require(self, *, user_id: uuid.UUID, project_id: uuid.UUID,
                operation: str, resource_id: uuid.UUID | None = None) -> AuthorizedProjectAction:
        policy = POLICIES.get(operation) if type(operation) is str else None
        if (policy is None or type(user_id) is not uuid.UUID or user_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or (policy.target is None and resource_id is not None)
                or (policy.target is not None and
                    (type(resource_id) is not uuid.UUID or resource_id.int == 0))):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        with self._uow() as tx:
            facts = self._repository.actor_facts(tx, user_id=user_id, project_id=project_id)
            if (type(facts) is not ProjectActorFacts
                    or facts.project_role not in policy.roles
                    or facts.project_state not in ("ACTIVE", "ARCHIVED")):
                raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
            if policy.target is not None:
                owner = self._repository.owner_project_id(
                    tx, target=policy.target, resource_id=resource_id,
                )
                if owner != project_id:
                    raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
            if policy.write and facts.project_state == "ARCHIVED":
                raise ProjectAuthorizationError("PROJECT_ARCHIVED")
            return AuthorizedProjectAction(user_id, project_id, operation, facts.project_role)
