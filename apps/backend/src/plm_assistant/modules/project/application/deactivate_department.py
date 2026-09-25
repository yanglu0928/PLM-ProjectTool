"""Internal one-way Department deactivation without member migration."""

from __future__ import annotations

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
    def save_deactivate_result(self, transaction: object, *, result_id: uuid.UUID,
                               project_id: uuid.UUID, view: DepartmentView,
                               version: int) -> None: ...
    def get_deactivate_result(self, transaction: object, *, result_id: uuid.UUID,
                              project_id: uuid.UUID,
                              department_id: uuid.UUID) -> DepartmentView | None: ...


class ProjectDepartmentDeactivateReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class ProjectDepartmentDeactivateService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: ProjectDepartmentDeactivateAccessPort,
                 license_guard: LicenseGuardPort, authorization: ProjectAuthorizationService,
                 repository: ProjectDepartmentDeactivateRepositoryPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None,
                 receipts: ProjectDepartmentDeactivateReceiptPort | None = None) -> None:
        if any(value is None for value in (unit_of_work, access, license_guard,
                                            authorization, repository, audit)):
            raise ValueError("Project Department deactivate dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository, self._audit = authorization, repository, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._receipts = receipts

    def deactivate_idempotent(self, command: DeactivateProjectDepartment, *,
                              idempotency_key: str) -> DepartmentView:
        if self._receipts is None:
            raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
        self._validate(command)
        try:
            validate_idempotency_key(idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "department_id": str(command.department_id),
                "expected_version": command.expected_version,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._authenticated_actor(tx, command)
                try:
                    self._authorization.require_department_deactivate_replay_in_transaction(
                        tx, user_id=actor, project_id=command.project_id,
                        department_id=command.department_id,
                    )
                except ProjectAuthorizationError as exc:
                    raise ProjectDepartmentDeactivateError(exc.code) from None
                ref_type = "V1_PROJECT_DEPARTMENT_DEACTIVATE"
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=ref_type, key=idempotency_key,
                )
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if replay is not None:
                    if replay.ref_type != ref_type or replay.status_code != 200:
                        raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
                    result = self._repository.get_deactivate_result(
                        tx, result_id=replay.ref_id, project_id=command.project_id,
                        department_id=command.department_id,
                    )
                    if (type(result) is not DepartmentView or result.state != "INACTIVE"
                            or result.etag != f'"v{command.expected_version + 1}"'):
                        raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
                    return result
                result = self._deactivate_locked(tx, command, actor)
                version = command.expected_version + 1
                if result.etag != f'"v{version}"':
                    raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
                result_id = uuid.uuid4()
                self._repository.save_deactivate_result(
                    tx, result_id=result_id, project_id=command.project_id,
                    view=result, version=version,
                )
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(ref_type, result_id, 200),
                )
                tx.commit()
                return result
        except IdempotencyError as exc:
            raise ProjectDepartmentDeactivateError(exc.code) from None

    def deactivate(self, command: DeactivateProjectDepartment) -> DepartmentView:
        self._validate(command)
        self._guard.require_valid(trace_id=command.trace_id)
        with self._uow() as tx:
            actor = self._authenticated_actor(tx, command)
            result = self._deactivate_locked(tx, command, actor)
            tx.commit()
            return result

    @staticmethod
    def _validate(command: DeactivateProjectDepartment) -> None:
        if (type(command) is not DeactivateProjectDepartment
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.department_id) is not uuid.UUID or command.department_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0):
            raise ProjectDepartmentDeactivateError("VALIDATION_FAILED")

    def _authenticated_actor(self, tx: object,
                             command: DeactivateProjectDepartment) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ProjectDepartmentDeactivateError("PROJECT_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ProjectDepartmentDeactivateError("AUTH_ACCESS_DENIED")
        return actor

    def _deactivate_locked(self, tx: object, command: DeactivateProjectDepartment,
                           actor: uuid.UUID) -> DepartmentView:
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
        return DepartmentView(
            facts.department_id, facts.code, facts.name, facts.state,
            facts.created_at, f'"v{facts.lock_version}"',
        )
