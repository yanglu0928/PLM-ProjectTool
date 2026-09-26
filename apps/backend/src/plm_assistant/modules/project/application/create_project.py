"""Internal atomic Project bootstrap; public HTTP wiring is separate."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)


class ProjectCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DepartmentSeed:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class CreateProject:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    code: str
    name: str
    initial_manager_user_id: uuid.UUID
    department: DepartmentSeed | None = None


@dataclass(frozen=True, slots=True)
class CreatedProject:
    project_id: uuid.UUID
    department_id: uuid.UUID
    project_member_id: uuid.UUID
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class CreatedProjectView:
    project_id: uuid.UUID
    code: str
    name: str
    state: str
    created_at: datetime
    etag: str


class ProjectCreateAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...
    def lock_eligible_manager(self, transaction: object, user_id: uuid.UUID) -> bool: ...


class LicenseGuardPort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ProjectCreateRepositoryPort(Protocol):
    def create(self, transaction: object, *, code: str, normalized_code: str,
               name: str, department_code: str, department_normalized_code: str,
               department_name: str, manager_user_id: uuid.UUID,
               created_by: uuid.UUID) -> CreatedProject | None: ...

    def created_at(self, transaction: object, project_id: uuid.UUID) -> datetime | None: ...


class ProjectCreateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class ProjectWorkflowInitializationPort(Protocol):
    def initialize_in_transaction(self, transaction: object, *, project_id: uuid.UUID,
                                  actor_id: uuid.UUID, trace_id: uuid.UUID) -> uuid.UUID: ...


def _code(value: object) -> tuple[str, str]:
    if type(value) is not str:
        raise ProjectCreateError("VALIDATION_FAILED")
    display = unicodedata.normalize("NFKC", value).strip()
    normalized = display.casefold()
    if (not 1 <= len(display) <= 64 or not 1 <= len(normalized) <= 64
            or any(unicodedata.category(char)[0] == "C" for char in display)):
        raise ProjectCreateError("VALIDATION_FAILED")
    return display, normalized


def _name(value: object) -> str:
    if type(value) is not str:
        raise ProjectCreateError("VALIDATION_FAILED")
    result = unicodedata.normalize("NFKC", value).strip()
    if not 1 <= len(result) <= 255 or any(unicodedata.category(char)[0] == "C" for char in result):
        raise ProjectCreateError("VALIDATION_FAILED")
    return result


class ProjectCreateService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: ProjectCreateAccessPort,
                 license_guard: LicenseGuardPort, repository: ProjectCreateRepositoryPort,
                 audit: AuditService, clock: Callable[[], datetime] | None = None,
                 receipts: ProjectCreateReceiptPort | None = None,
                 workflow_initializer: ProjectWorkflowInitializationPort | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard, repository, audit)):
            raise ValueError("Project create dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repository, self._audit = repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._receipts = receipts
        # Kept optional for earlier isolated Project-only internal callers.
        # Production composition always supplies it; no user-controlled switch.
        self._workflow_initializer = workflow_initializer

    def create(self, command: CreateProject) -> CreatedProject:
        code, norm, name, dept_code, dept_norm, dept_name = self._prepare(command)
        with self._uow() as tx:
            self._require_admin(tx, command)
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            actor = self._require_admin(tx, command)
            created = self._create_locked(
                tx, command, actor, code, norm, name, dept_code, dept_norm, dept_name,
            )
            tx.commit()
            return created

    def create_idempotent(self, command: CreateProject, *, idempotency_key: str) -> CreatedProjectView:
        """Return the original ProjectView on retry without repeating bootstrap or Audit."""
        if self._receipts is None:
            raise ProjectCreateError("PROJECT_UNAVAILABLE")
        code, norm, name, dept_code, dept_norm, dept_name = self._prepare(command)
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "code": code, "name": name,
                "initial_manager_user_id": str(command.initial_manager_user_id),
                "department_code": dept_code, "department_name": dept_name,
            })
            with self._uow() as tx:
                self._require_admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None,
                    operation="V1_PROJECT_CREATE", key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != "V1_PROJECT" or replay.status_code != 201:
                        raise ProjectCreateError("PROJECT_UNAVAILABLE")
                    return self._created_view(tx, replay.ref_id, code, name)
                created = self._create_locked(
                    tx, command, actor, code, norm, name,
                    dept_code, dept_norm, dept_name,
                )
                result = self._created_view(tx, created.project_id, code, name)
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult("V1_PROJECT", created.project_id, 201),
                )
                tx.commit()
                return result
        except IdempotencyError as exc:
            raise ProjectCreateError(exc.code) from None

    @staticmethod
    def _prepare(command: CreateProject) -> tuple[str, str, str, str, str, str]:
        if (type(command) is not CreateProject
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.initial_manager_user_id) is not uuid.UUID
                or command.initial_manager_user_id.int == 0
                or (command.department is not None and type(command.department) is not DepartmentSeed)):
            raise ProjectCreateError("VALIDATION_FAILED")
        code, norm = _code(command.code)
        name = _name(command.name)
        department = command.department or DepartmentSeed("DEFAULT", "默认部门")
        dept_code, dept_norm = _code(department.code)
        dept_name = _name(department.name)
        return code, norm, name, dept_code, dept_norm, dept_name

    def _create_locked(self, tx: object, command: CreateProject, actor: uuid.UUID,
                       code: str, norm: str, name: str,
                       dept_code: str, dept_norm: str, dept_name: str) -> CreatedProject:
        if self._access.lock_eligible_manager(tx, command.initial_manager_user_id) is not True:
            raise ProjectCreateError("PROJECT_MANAGER_INVALID")
        created = self._repository.create(
            tx, code=code, normalized_code=norm, name=name,
            department_code=dept_code, department_normalized_code=dept_norm,
            department_name=dept_name, manager_user_id=command.initial_manager_user_id,
            created_by=actor,
        )
        if type(created) is not CreatedProject:
            raise ProjectCreateError("PROJECT_CODE_CONFLICT")
        if self._workflow_initializer is not None:
            workflow_id = self._workflow_initializer.initialize_in_transaction(
                tx, project_id=created.project_id, actor_id=actor, trace_id=command.trace_id,
            )
            if type(workflow_id) is not uuid.UUID or workflow_id.int == 0:
                raise ProjectCreateError("PROJECT_UNAVAILABLE")
        self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="PROJECT",
            target_project_id=created.project_id, actor_type="USER", actor_id=actor,
            original_actor_id=None, actor_hint_digest=None, action="PROJECT_CREATED",
            outcome="SUCCESS", target_owner_module="project",
            target_object_type="PRJ-01", target_object_id=created.project_id,
            after_state="ACTIVE",
        ))
        return created

    def _created_view(self, tx: object, project_id: uuid.UUID,
                      code: str, name: str) -> CreatedProjectView:
        created_at = self._repository.created_at(tx, project_id)
        if not isinstance(created_at, datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ProjectCreateError("PROJECT_UNAVAILABLE")
        return CreatedProjectView(project_id, code, name, "ACTIVE", created_at, '"v0"')

    def _require_admin(self, tx: object, command: CreateProject) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ProjectCreateError("PROJECT_UNAVAILABLE")
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ProjectCreateError("AUTH_ACCESS_DENIED")
        return actor
