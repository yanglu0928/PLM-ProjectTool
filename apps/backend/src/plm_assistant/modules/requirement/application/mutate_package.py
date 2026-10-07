"""Authorized, idempotent Requirement Package mutations."""

from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.audit_service import AuditService
from plm_assistant.modules.audit.domain.audit_event import AuditEventDraft
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope,
    canonical_payload_fingerprint, validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError, ProjectAuthorizationService,
)

_OPERATIONS = {
    "PATCH": ("V1_REQ_PACKAGE_PATCH", "REQ_PACKAGE_PATCH", "REQUIREMENT_PACKAGE_PATCHED"),
    "ADD": ("V1_REQ_PACKAGE_ADD", "REQ_PACKAGE_ADD", "REQUIREMENT_PACKAGE_REQUIREMENTS_ADDED"),
    "REMOVE": ("V1_REQ_PACKAGE_REMOVE", "REQ_PACKAGE_REMOVE", "REQUIREMENT_PACKAGE_REQUIREMENTS_REMOVED"),
}
_STATES = frozenset({"ACTIVE", "ARCHIVED", "RESTRICTED"})


class RequirementPackageMutationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchRequirementPackage:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_package_id: uuid.UUID
    expected_version: int
    idempotency_key: str = field(repr=False)
    name: str | None = None
    package_state: str | None = None


@dataclass(frozen=True, slots=True)
class ChangeRequirementPackageMembers:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_package_id: uuid.UUID
    expected_version: int
    requirement_ids: tuple[uuid.UUID, ...]
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RequirementPackageView:
    requirement_package_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    package_state: str
    member_refs: tuple[uuid.UUID, ...]
    etag: str

    def __post_init__(self) -> None:
        valid_etag = (type(self.etag) is str and self.etag.startswith('"v')
                      and self.etag.endswith('"') and self.etag[2:-1].isdigit())
        if (type(self.requirement_package_id) is not uuid.UUID
                or self.requirement_package_id.int == 0
                or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
                or type(self.name) is not str or not self.name
                or self.package_state not in _STATES
                or type(self.member_refs) is not tuple
                or any(type(item) is not uuid.UUID or item.int == 0 for item in self.member_refs)
                or tuple(sorted(self.member_refs, key=str)) != self.member_refs
                or len(set(self.member_refs)) != len(self.member_refs) or not valid_etag):
            raise ValueError("invalid RequirementPackage view")


class RequirementPackageMutationAccessPort(Protocol):
    def authenticated_user(self, transaction: object, *, session_token: bytes,
                           csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class RequirementPackageMutationLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RequirementPackageMutationRepositoryPort(Protocol):
    def mutate(self, transaction: object, *, result_id: uuid.UUID, operation: str,
               project_id: uuid.UUID, requirement_package_id: uuid.UUID,
               expected_version: int, actor_id: uuid.UUID, name: str | None,
               package_state: str | None,
               requirement_ids: tuple[uuid.UUID, ...]) -> RequirementPackageView: ...
    def result(self, transaction: object, *, result_id: uuid.UUID,
               project_id: uuid.UUID, requirement_package_id: uuid.UUID,
               operation: str) -> RequirementPackageView | None: ...


class RequirementPackageMutationReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class RequirementPackageMutationService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: RequirementPackageMutationAccessPort,
                 license_guard: RequirementPackageMutationLicensePort,
                 authorization: ProjectAuthorizationService,
                 repository: RequirementPackageMutationRepositoryPort,
                 receipts: RequirementPackageMutationReceiptPort,
                 audit: AuditService, clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard,
                                         authorization, repository, receipts, audit)):
            raise ValueError("Requirement Package mutation dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchRequirementPackage) -> RequirementPackageView:
        self._validate_common(command, PatchRequirementPackage)
        if command.name is None and command.package_state is None:
            raise RequirementPackageMutationError("VALIDATION_FAILED")
        name = None if command.name is None else self._name(command.name)
        state = command.package_state
        if state is not None and (type(state) is not str or state not in _STATES):
            raise RequirementPackageMutationError("VALIDATION_FAILED")
        return self._execute(command, "PATCH", name, state, ())

    def add_members(self, command: ChangeRequirementPackageMembers) -> RequirementPackageView:
        return self._execute(command, "ADD", None, None, self._members(command))

    def remove_members(self, command: ChangeRequirementPackageMembers) -> RequirementPackageView:
        return self._execute(command, "REMOVE", None, None, self._members(command))

    def _execute(self, command: PatchRequirementPackage | ChangeRequirementPackageMembers,
                 operation: str, name: str | None, state: str | None,
                 members: tuple[uuid.UUID, ...]) -> RequirementPackageView:
        self._validate_common(command, type(command))
        receipt_operation, auth_operation, action = _OPERATIONS[operation]
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "requirement_package_id": str(command.requirement_package_id),
                "expected_version": command.expected_version, "name": name,
                "package_state": state,
                "requirement_ids": [str(item) for item in members],
            })
            self._guard.require_valid(trace_id=command.trace_id)
            result_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation=auth_operation,
                )
                if authorized.user_id != actor or authorized.project_id != command.project_id:
                    raise RequirementPackageMutationError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=receipt_operation, key=command.idempotency_key,
                )
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint
                )
                if previous is not None:
                    if previous.ref_type != receipt_operation or previous.status_code != 200:
                        raise RequirementPackageMutationError("REQUIREMENT_UNAVAILABLE")
                    replay = self._repository.result(
                        tx, result_id=previous.ref_id, project_id=command.project_id,
                        requirement_package_id=command.requirement_package_id,
                        operation=operation,
                    )
                    if replay is None:
                        raise RequirementPackageMutationError("REQUIREMENT_UNAVAILABLE")
                    return replay
                result = self._repository.mutate(
                    tx, result_id=result_id, operation=operation,
                    project_id=command.project_id,
                    requirement_package_id=command.requirement_package_id,
                    expected_version=command.expected_version, actor_id=actor,
                    name=name, package_state=state, requirement_ids=members,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None, action=action,
                    outcome="SUCCESS", target_owner_module="requirement",
                    target_object_type="REQ-01",
                    target_object_id=command.requirement_package_id,
                    before_state=None, after_state=result.package_state,
                ))
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult(receipt_operation, result_id, 200),
                )
                tx.commit()
                return result
        except RequirementPackageMutationError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementPackageMutationError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementPackageMutationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise RequirementPackageMutationError(error.code) from None
        except Exception:
            raise RequirementPackageMutationError("REQUIREMENT_UNAVAILABLE") from None

    @staticmethod
    def _validate_common(command: object, expected_type: type) -> None:
        if (type(command) is not expected_type
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
                or type(command.requirement_package_id) is not uuid.UUID
                or command.requirement_package_id.int == 0
                or type(command.expected_version) is not int or command.expected_version < 0):
            raise RequirementPackageMutationError("VALIDATION_FAILED")

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise RequirementPackageMutationError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if not 1 <= len(result) <= 255 or any(
                unicodedata.category(char)[0] == "C" for char in result):
            raise RequirementPackageMutationError("VALIDATION_FAILED")
        return result

    def _members(self, command: ChangeRequirementPackageMembers) -> tuple[uuid.UUID, ...]:
        self._validate_common(command, ChangeRequirementPackageMembers)
        values = command.requirement_ids
        if (type(values) is not tuple or not 1 <= len(values) <= 200
                or any(type(item) is not uuid.UUID or item.int == 0 for item in values)
                or len(set(values)) != len(values)):
            raise RequirementPackageMutationError("VALIDATION_FAILED")
        return tuple(sorted(values, key=str))

    def _actor(self, tx: object,
               command: PatchRequirementPackage | ChangeRequirementPackageMembers) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise RequirementPackageMutationError("REQUIREMENT_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise RequirementPackageMutationError("AUTH_ACCESS_DENIED")
        return actor
