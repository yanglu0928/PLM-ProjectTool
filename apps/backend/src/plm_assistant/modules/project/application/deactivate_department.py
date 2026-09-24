"""Internal one-way Department deactivation without member migration."""

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
from plm_assistant.modules.project.application.read_departments import DepartmentFacts, DepartmentView


class ProjectDepartmentDeactivateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DeactivateProjectDepartment:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    department_id: uuid.UUID
    expected_version: int


class ProjectDepartmentDeactivateAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectDepartmentDeactivateRepositoryPort(Protocol):
    def deactivate(self, transaction: object, *, project_id: uuid.UUID,
                   department_id: uuid.UUID, expected_version: int) -> DepartmentFacts: ...


class ProjectDepartmentDeactivateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: ProjectDepartmentDeactivateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectDepartmentDeactivateRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("Project Department deactivate dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def deactivate(self, command: DeactivateProjectDepartment) -> DepartmentView:
        if (type(command) is not DeactivateProjectDepartment
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.department_id) is not uuid.UUID or command.department_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0):
            raise ProjectDepartmentDeactivateError("VALIDATION_FAILED")
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectDepartmentDeactivateError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PROJECT_DEPARTMENT_DEACTIVATE",
                    resource_id=command.department_id,
                )
            except ProjectAuthorizationError as exc:
                raise ProjectDepartmentDeactivateError(exc.code) from None
            facts = self._repository.deactivate(
                tx, project_id=command.project_id,
                department_id=command.department_id,
                expected_version=command.expected_version,
            )
            if (type(facts) is not DepartmentFacts
                    or facts.project_id != command.project_id
                    or facts.department_id != command.department_id
                    or facts.state != "INACTIVE"):
                raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id, event_scope="PROJECT",
                target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                original_actor_id=None, actor_hint_digest=None,
                action="PROJECT_DEPARTMENT_DEACTIVATED", outcome="SUCCESS",
                target_owner_module="project", target_object_type="PRJ-03",
                target_object_id=command.department_id,
                before_state="ACTIVE", after_state="INACTIVE",
            ))
            tx.commit()
            return DepartmentView(
                facts.department_id, facts.code, facts.name, facts.state,
                facts.created_at, f'"v{facts.lock_version}"',
            )
