"""Necessary current PROJECT reviewer facts, not Subject qualification or approval."""
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID
from .authorization import ALL_MEMBERS, ProjectActorFacts, ProjectAuthorizationRepositoryPort


class ReviewReviewerEligibilityError(RuntimeError):
    def __init__(self):
        super().__init__("REVIEW_REVIEWER_INELIGIBLE")
        self.code = "REVIEW_REVIEWER_INELIGIBLE"


class EnabledReviewUsersPort(Protocol):
    def lock_enabled_users(self, tx: object, user_ids: tuple[UUID, ...]) -> tuple[UUID, ...]: ...


@dataclass(frozen=True, slots=True)
class ProjectReviewerFacts:
    user_id: UUID
    project_id: UUID
    project_role: str


@dataclass(frozen=True, slots=True)
class LockedReviewUsers:
    """Internal same-tx observation, NOT permission/proof or serializable API data."""
    transaction: object = field(repr=False, compare=False)
    requested_ids: tuple[UUID, ...]
    enabled_ids: tuple[UUID, ...]


class ProjectReviewerQualificationService:
    """Trusted caller tx; call BEFORE Project/Review locks; server roles only.

    Caller authenticates and checks PM/License/Subject independently. This service
    never creates Assignment, grants global access or commits the transaction.
    """
    def __init__(self, *, users: EnabledReviewUsersPort, projects: ProjectAuthorizationRepositoryPort):
        if users is None or projects is None:
            raise ValueError("reviewer qualification dependencies required")
        self._users, self._projects = users, projects

    def qualify_in_transaction(self, tx, *, project_id, reviewer_ids, allowed_roles):
        if (type(project_id) is not UUID or not project_id.int or type(reviewer_ids) is not tuple or not reviewer_ids
                or any(type(v) is not UUID or not v.int for v in reviewer_ids) or len(set(reviewer_ids)) != len(reviewer_ids)
                or type(allowed_roles) is not frozenset or not allowed_roles or not allowed_roles <= ALL_MEMBERS):
            raise ReviewReviewerEligibilityError()
        locked = self.lock_users_in_transaction(tx, reviewer_ids=reviewer_ids)
        return self.qualify_locked_in_transaction(tx, project_id=project_id, locked=locked,
            allowed_roles=allowed_roles, reviewer_ids=reviewer_ids)

    def lock_users_in_transaction(self, tx, *, reviewer_ids):
        if (type(reviewer_ids) is not tuple or not reviewer_ids or any(type(v) is not UUID or not v.int for v in reviewer_ids)
                or len(set(reviewer_ids)) != len(reviewer_ids)):
            raise ReviewReviewerEligibilityError()
        ordered = tuple(sorted(reviewer_ids))
        enabled = self._users.lock_enabled_users(tx, ordered)
        if (type(enabled) is not tuple or any(type(v) is not UUID for v in enabled)
                or enabled != tuple(sorted(set(enabled))) or not set(enabled) <= set(ordered)):
            raise ReviewReviewerEligibilityError()
        return LockedReviewUsers(tx, ordered, enabled)

    def qualify_locked_in_transaction(self, tx, *, project_id, locked, allowed_roles, reviewer_ids):
        if (type(project_id) is not UUID or not project_id.int or type(locked) is not LockedReviewUsers
                or locked.transaction is not tx or type(allowed_roles) is not frozenset or not allowed_roles
                or not allowed_roles <= ALL_MEMBERS or type(reviewer_ids) is not tuple or not reviewer_ids
                or any(type(v) is not UUID or not v.int for v in reviewer_ids) or len(set(reviewer_ids)) != len(reviewer_ids)
                or locked.requested_ids != tuple(sorted(reviewer_ids)) or locked.enabled_ids != locked.requested_ids):
            raise ReviewReviewerEligibilityError()
        roles = {}
        for user in locked.requested_ids:
            facts = self._projects.actor_facts(tx, user_id=user, project_id=project_id, lock=True)
            if (type(facts) is not ProjectActorFacts or facts.project_state != "ACTIVE"
                    or facts.project_role not in allowed_roles):
                raise ReviewReviewerEligibilityError()
            roles[user] = facts.project_role
        return tuple(ProjectReviewerFacts(user, project_id, roles[user]) for user in reviewer_ids)
