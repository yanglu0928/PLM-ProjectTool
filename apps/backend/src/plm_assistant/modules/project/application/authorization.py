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
    lock_reads: bool = False


POLICIES: dict[str, _Policy] = {
    "PROJECT_GET": _Policy(ALL_MEMBERS, False),
    "WORKFLOW_START": _Policy(MANAGERS, True),
    "WORKFLOW_GET": _Policy(ALL_MEMBERS, False, lock_reads=True),
    "REVIEW_GET": _Policy(ALL_MEMBERS, False, lock_reads=True),
    "TRACE_LINK_CREATE": _Policy(frozenset({"PROJECT_MANAGER", "IMPLEMENTATION_MEMBER"}), True),
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
                    project_id: uuid.UUID, lock: bool = False) -> ProjectActorFacts | None: ...
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
        with self._uow() as tx:
            return self.require_in_transaction(
                tx, user_id=user_id, project_id=project_id,
                operation=operation, resource_id=resource_id,
            )

    def require_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                               project_id: uuid.UUID, operation: str,
                               resource_id: uuid.UUID | None = None) -> AuthorizedProjectAction:
        policy = POLICIES.get(operation) if type(operation) is str else None
        if (policy is None or type(user_id) is not uuid.UUID or user_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0
                or (policy.target is None and resource_id is not None)
                or (policy.target is not None and
                    (type(resource_id) is not uuid.UUID or resource_id.int == 0))):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        facts = self._repository.actor_facts(
            transaction, user_id=user_id, project_id=project_id, lock=policy.write or policy.lock_reads,
        )
        if (type(facts) is not ProjectActorFacts
                or facts.project_role not in policy.roles
                or facts.project_state not in ("ACTIVE", "ARCHIVED")):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        if policy.target is not None:
            owner = self._repository.owner_project_id(
                transaction, target=policy.target, resource_id=resource_id,
            )
            if owner != project_id:
                raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        if policy.write and facts.project_state == "ARCHIVED":
            raise ProjectAuthorizationError("PROJECT_ARCHIVED")
        return AuthorizedProjectAction(user_id, project_id, operation, facts.project_role)

    def require_archive_replay_in_transaction(self, transaction: object, *, user_id: uuid.UUID,
                                               project_id: uuid.UUID) -> None:
        """Lock current manager facts while allowing the already archived replay state."""
        if (type(user_id) is not uuid.UUID or user_id.int == 0
                or type(project_id) is not uuid.UUID or project_id.int == 0):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
        facts = self._repository.actor_facts(
            transaction, user_id=user_id, project_id=project_id, lock=True,
        )
        if (type(facts) is not ProjectActorFacts or facts.project_role != "PROJECT_MANAGER"
                or facts.project_state not in ("ACTIVE", "ARCHIVED")):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")

    def require_member_state_replay_in_transaction(self, transaction: object, *,
                                                   user_id: uuid.UUID, project_id: uuid.UUID,
                                                   member_id: uuid.UUID) -> None:
        """Check current manager and member ownership without repeating a completed write."""
        self.require_archive_replay_in_transaction(
            transaction, user_id=user_id, project_id=project_id,
        )
        if (type(member_id) is not uuid.UUID or member_id.int == 0
                or self._repository.owner_project_id(
                    transaction, target="MEMBER", resource_id=member_id,
                ) != project_id):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")

    def require_department_deactivate_replay_in_transaction(self, transaction: object, *,
                                                            user_id: uuid.UUID, project_id: uuid.UUID,
                                                            department_id: uuid.UUID) -> None:
        """Check current manager and Department ownership for a completed command."""
        self.require_archive_replay_in_transaction(
            transaction, user_id=user_id, project_id=project_id,
        )
        if (type(department_id) is not uuid.UUID or department_id.int == 0
                or self._repository.owner_project_id(
                    transaction, target="DEPARTMENT", resource_id=department_id,
                ) != project_id):
            raise ProjectAuthorizationError("RESOURCE_NOT_FOUND")
