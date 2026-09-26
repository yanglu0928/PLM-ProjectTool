"""Necessary current PROJECT reviewer facts, not Subject qualification or approval."""
from dataclasses import dataclass
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
        ordered = tuple(sorted(reviewer_ids))
        enabled = self._users.lock_enabled_users(tx, ordered)
        if type(enabled) is not tuple or enabled != ordered:
            raise ReviewReviewerEligibilityError()
        roles = {}
        for user in ordered:
            facts = self._projects.actor_facts(tx, user_id=user, project_id=project_id, lock=True)
            if (type(facts) is not ProjectActorFacts or facts.project_state != "ACTIVE"
                    or facts.project_role not in allowed_roles):
                raise ReviewReviewerEligibilityError()
            roles[user] = facts.project_role
        return tuple(ProjectReviewerFacts(user, project_id, roles[user]) for user in reviewer_ids)
