"""Internal scoped Project Department creation command."""

from __future__ import annotations

import unicodedata
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


class ProjectDepartmentCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateProjectDepartment:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    code: str
    name: str


class ProjectDepartmentCreateAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectDepartmentCreateRepositoryPort(Protocol):
    def create(self, transaction: object, *, project_id: uuid.UUID,
               code: str, normalized_code: str, name: str) -> DepartmentFacts | None: ...


def _text(value: object, limit: int) -> str:
    if type(value) is not str:
        raise ProjectDepartmentCreateError("VALIDATION_FAILED")
    result = unicodedata.normalize("NFKC", value).strip()
    if (not 1 <= len(result) <= limit
            or any(unicodedata.category(char)[0] == "C" for char in result)):
        raise ProjectDepartmentCreateError("VALIDATION_FAILED")
    return result


class ProjectDepartmentCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectDepartmentCreateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectDepartmentCreateRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("Project Department create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateProjectDepartment) -> DepartmentView:
        if (type(command) is not CreateProjectDepartment
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0):
            raise ProjectDepartmentCreateError("VALIDATION_FAILED")
        code = _text(command.code, 64)
        normalized_code = code.casefold()
        if not 1 <= len(normalized_code) <= 64:
            raise ProjectDepartmentCreateError("VALIDATION_FAILED")
        name = _text(command.name, 255)
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectDepartmentCreateError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectDepartmentCreateError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PROJECT_DEPARTMENT_CREATE",
                )
            except ProjectAuthorizationError as exc:
                raise ProjectDepartmentCreateError(exc.code) from None
            facts = self._repository.create(
                tx, project_id=command.project_id,
                code=code, normalized_code=normalized_code, name=name,
            )
            if facts is None:
                raise ProjectDepartmentCreateError("CONFLICT_DUPLICATE")
            if type(facts) is not DepartmentFacts or facts.project_id != command.project_id:
                raise ProjectDepartmentCreateError("PROJECT_UNAVAILABLE")
            self._audit.append(tx, AuditEventDraft(
                trace_id=command.trace_id, event_scope="PROJECT",
                target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                original_actor_id=None, actor_hint_digest=None,
                action="PROJECT_DEPARTMENT_CREATED", outcome="SUCCESS",
                target_owner_module="project", target_object_type="PRJ-03",
                target_object_id=facts.department_id, after_state="ACTIVE",
            ))
            tx.commit()
            return DepartmentView(
                facts.department_id, facts.code, facts.name, facts.state,
                facts.created_at, f'"v{facts.lock_version}"',
            )
