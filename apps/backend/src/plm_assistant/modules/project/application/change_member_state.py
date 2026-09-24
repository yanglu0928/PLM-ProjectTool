"""Internal ProjectMember suspend, resume and permanent remove commands."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)
from plm_assistant.modules.project.application.read_members import MemberFacts, ProjectMemberView


class ProjectMemberStateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ChangeProjectMemberState:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    member_id: uuid.UUID
    expected_version: int


class ProjectMemberStateAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...
    def display_name(self, transaction: object, user_id: uuid.UUID) -> str | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectMemberStateRepositoryPort(Protocol):
    def change(self, transaction: object, *, project_id: uuid.UUID, member_id: uuid.UUID,
               expected_version: int, operation: str) -> tuple[MemberFacts, str]: ...


_OPERATIONS = {
    "SUSPEND": ("PROJECT_MEMBER_SUSPEND", "PROJECT_MEMBER_SUSPENDED"),
    "RESUME": ("PROJECT_MEMBER_RESUME", "PROJECT_MEMBER_RESUMED"),
    "REMOVE": ("PROJECT_MEMBER_REMOVE", "PROJECT_MEMBER_REMOVED"),
}


class ProjectMemberStateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectMemberStateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectMemberStateRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("ProjectMember state dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def suspend(self, command: ChangeProjectMemberState) -> ProjectMemberView:
        return self._execute(command, "SUSPEND")

    def resume(self, command: ChangeProjectMemberState) -> ProjectMemberView:
        return self._execute(command, "RESUME")

    def remove(self, command: ChangeProjectMemberState) -> ProjectMemberView:
        return self._execute(command, "REMOVE")

    def _execute(self, command: ChangeProjectMemberState, operation: str) -> ProjectMemberView:
        if (type(command) is not ChangeProjectMemberState
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.member_id) is not uuid.UUID or command.member_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0):
            raise ProjectMemberStateError("VALIDATION_FAILED")
        policy, action = _OPERATIONS[operation]
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectMemberStateError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectMemberStateError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation=policy, resource_id=command.member_id,
                )
            except ProjectAuthorizationError as exc:
                raise ProjectMemberStateError(exc.code) from None
            facts, previous_state = self._repository.change(
                tx, project_id=command.project_id, member_id=command.member_id,
                expected_version=command.expected_version, operation=operation,
            )
            if (type(facts) is not MemberFacts or type(previous_state) is not str
                    or facts.project_id != command.project_id
                    or facts.member_id != command.member_id):
                raise ProjectMemberStateError("PROJECT_UNAVAILABLE")
            display_name = self._access.display_name(tx, facts.user_id)
            if type(display_name) is not str or not display_name:
                raise ProjectMemberStateError("PROJECT_UNAVAILABLE")
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id, event_scope="PROJECT",
                target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                original_actor_id=None, actor_hint_digest=None,
                action=action, outcome="SUCCESS",
                target_owner_module="project", target_object_type="PRJ-02",
                target_object_id=command.member_id,
                before_state=previous_state, after_state=facts.state,
            ))
            tx.commit()
            return ProjectMemberView(
                facts.member_id, facts.user_id, display_name, facts.role,
                facts.department_id, facts.department_name, facts.state,
                facts.effective_at, facts.ended_at, f'"v{facts.lock_version}"',
            )
