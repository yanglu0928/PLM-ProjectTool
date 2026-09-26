"""Internal scoped Department code/name mutation with strong versioning."""

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


class ProjectDepartmentPatchError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchProjectDepartment:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    department_id: uuid.UUID
    expected_version: int
    code: str | None = None
    name: str | None = None


class ProjectDepartmentPatchAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectDepartmentPatchRepositoryPort(Protocol):
    def patch(self, transaction: object, *, project_id: uuid.UUID,
              department_id: uuid.UUID, expected_version: int,
              code: str | None, normalized_code: str | None,
              name: str | None) -> tuple[DepartmentFacts, bool]: ...


def _text(value: object, limit: int) -> str:
    if type(value) is not str:
        raise ProjectDepartmentPatchError("VALIDATION_FAILED")
    result = unicodedata.normalize("NFKC", value).strip()
    if (not 1 <= len(result) <= limit
            or any(unicodedata.category(char)[0] == "C" for char in result)):
        raise ProjectDepartmentPatchError("VALIDATION_FAILED")
    return result


class ProjectDepartmentPatchService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectDepartmentPatchAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectDepartmentPatchRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("Project Department patch dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchProjectDepartment) -> DepartmentView:
        if (type(command) is not PatchProjectDepartment
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.department_id) is not uuid.UUID or command.department_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0
                or (command.code is None and command.name is None)):
            raise ProjectDepartmentPatchError("VALIDATION_FAILED")
        code = _text(command.code, 64) if command.code is not None else None
        normalized_code = code.casefold() if code is not None else None
        if normalized_code is not None and not 1 <= len(normalized_code) <= 64:
            raise ProjectDepartmentPatchError("VALIDATION_FAILED")
        name = _text(command.name, 255) if command.name is not None else None
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            now = self._clock()
            if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                raise ProjectDepartmentPatchError("PROJECT_UNAVAILABLE")
            actor = self._access.authenticated_user(
                tx, session_token=command.session_token, csrf_token=command.csrf_token,
                now=now.astimezone(timezone.utc),
            )
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise ProjectDepartmentPatchError("AUTH_ACCESS_DENIED")
            try:
                self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation="PROJECT_DEPARTMENT_PATCH", resource_id=command.department_id,
                )
            except ProjectAuthorizationError as exc:
                raise ProjectDepartmentPatchError(exc.code) from None
            facts, changed = self._repository.patch(
                tx, project_id=command.project_id,
                department_id=command.department_id,
                expected_version=command.expected_version,
                code=code, normalized_code=normalized_code, name=name,
            )
            if (type(facts) is not DepartmentFacts or type(changed) is not bool
                    or facts.project_id != command.project_id
                    or facts.department_id != command.department_id):
                raise ProjectDepartmentPatchError("PROJECT_UNAVAILABLE")
            if changed:
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="PROJECT_DEPARTMENT_PATCHED", outcome="SUCCESS",
                    target_owner_module="project", target_object_type="PRJ-03",
                    target_object_id=command.department_id,
                    before_state=facts.state, after_state=facts.state,
                ))
            tx.commit()
            return DepartmentView(
                facts.department_id, facts.code, facts.name, facts.state,
                facts.created_at, f'"v{facts.lock_version}"',
            )
