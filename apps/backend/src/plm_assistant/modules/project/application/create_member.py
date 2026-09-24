"""Internal ProjectMember creation with current ProjectManager authorization."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.project.application.authorization import (
    ALL_MEMBERS, ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.read_members import MemberFacts, ProjectMemberView


class ProjectMemberCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateProjectMember:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    department_id: uuid.UUID
    effective_at: datetime | None = None


class ProjectMemberCreateAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...
    def lock_eligible_member(self, transaction: object, user_id: uuid.UUID) -> str | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectMemberCreateRepositoryPort(Protocol):
    def create(self, transaction: object, *, project_id: uuid.UUID,
               user_id: uuid.UUID, role: str, department_id: uuid.UUID,
               effective_at: datetime | None) -> MemberFacts: ...


class ProjectMemberCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectMemberCreateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectMemberCreateRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("ProjectMember create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateProjectMember) -> ProjectMemberView:
        if (type(command) is not CreateProjectMember
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    command.project_id, command.user_id, command.department_id))
                or (command.effective_at is not None and (
                    not isinstance(command.effective_at, datetime)
                    or command.effective_at.tzinfo is None
                    or command.effective_at.utcoffset() is None))):
            raise ProjectMemberCreateError("VALIDATION_FAILED")
        if type(command.role) is not str or command.role not in ALL_MEMBERS:
            raise ProjectMemberCreateError("PROJECT_ROLE_INVALID")
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectMemberCreateError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectMemberCreateError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PROJECT_MEMBER_CREATE",
                )
            except ProjectAuthorizationError as exc:
                raise ProjectMemberCreateError(exc.code) from None
            display_name = self._access.lock_eligible_member(tx, command.user_id)
            if type(display_name) is not str or not display_name:
                raise ProjectMemberCreateError("PROJECT_ROLE_INVALID")
            facts = self._repository.create(
                tx, project_id=command.project_id, user_id=command.user_id,
                role=command.role, department_id=command.department_id,
                effective_at=(command.effective_at.astimezone(timezone.utc)
                              if command.effective_at is not None else None),
            )
            if type(facts) is not MemberFacts or facts.project_id != command.project_id:
                raise ProjectMemberCreateError("PROJECT_UNAVAILABLE")
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id, event_scope="PROJECT",
                target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                original_actor_id=None, actor_hint_digest=None,
                action="PROJECT_MEMBER_CREATED", outcome="SUCCESS",
                target_owner_module="project", target_object_type="PRJ-02",
                target_object_id=facts.member_id, after_state="ACTIVE",
            ))
            tx.commit()
            return ProjectMemberView(
                facts.member_id, facts.user_id, display_name, facts.role,
                facts.department_id, facts.department_name, facts.state,
                facts.effective_at, facts.ended_at, f'"v{facts.lock_version}"',
            )
