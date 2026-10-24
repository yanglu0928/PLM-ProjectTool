"""Internal scoped ProjectMember role/department mutation."""

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


class ProjectMemberPatchError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchProjectMember:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    member_id: uuid.UUID
    expected_version: int
    role: str | None = None
    department_id: uuid.UUID | None = None


class ProjectMemberPatchAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...
    def display_name(self, transaction: object, user_id: uuid.UUID) -> str | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectMemberPatchRepositoryPort(Protocol):
    def patch(self, transaction: object, *, project_id: uuid.UUID, member_id: uuid.UUID,
              expected_version: int, role: str | None, department_id: uuid.UUID | None,
              actor_user_id: uuid.UUID, trace_id: uuid.UUID) -> tuple[MemberFacts, bool]: ...


class ProjectMemberPatchService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectMemberPatchAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectMemberPatchRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("ProjectMember patch dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchProjectMember) -> ProjectMemberView:
        if (type(command) is not PatchProjectMember
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.member_id) is not uuid.UUID or command.member_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0
                or (command.role is None and command.department_id is None)
                or (command.department_id is not None and (
                    type(command.department_id) is not uuid.UUID or command.department_id.int == 0))):
            raise ProjectMemberPatchError("VALIDATION_FAILED")
        if command.role is not None and (type(command.role) is not str or command.role not in ALL_MEMBERS):
            raise ProjectMemberPatchError("PROJECT_ROLE_INVALID")
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectMemberPatchError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectMemberPatchError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PROJECT_MEMBER_PATCH", resource_id=command.member_id,
                )
            except ProjectAuthorizationError as exc:
                raise ProjectMemberPatchError(exc.code) from None
            facts, changed = self._repository.patch(
                tx, project_id=command.project_id, member_id=command.member_id,
                expected_version=command.expected_version, role=command.role,
                department_id=command.department_id, actor_user_id=actor,
                trace_id=command.trace_id,
            )
            if (type(facts) is not MemberFacts or type(changed) is not bool
                    or facts.project_id != command.project_id
                    or facts.member_id != command.member_id):
                raise ProjectMemberPatchError("PROJECT_UNAVAILABLE")
            display_name = self._access.display_name(tx, facts.user_id)
            if type(display_name) is not str or not display_name:
                raise ProjectMemberPatchError("PROJECT_UNAVAILABLE")
            if changed:
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="PROJECT_MEMBER_PATCHED", outcome="SUCCESS",
                    target_owner_module="project", target_object_type="PRJ-02",
                    target_object_id=command.member_id,
                    before_state=facts.state, after_state=facts.state,
                ))
            tx.commit()
            return ProjectMemberView(
                facts.member_id, facts.user_id, display_name, facts.role,
                facts.department_id, facts.department_name, facts.state,
                facts.effective_at, facts.ended_at, f'"v{facts.lock_version}"',
            )
