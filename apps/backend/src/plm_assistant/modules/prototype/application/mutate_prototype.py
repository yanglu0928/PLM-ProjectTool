"""Authorized Prototype identity PATCH and one-way ARCHIVE."""

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


class PrototypeMutationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class PatchPrototypeIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    expected_version: int
    name: str


@dataclass(frozen=True, slots=True)
class ArchivePrototypeIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    prototype_id: uuid.UUID
    expected_version: int
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrototypeIdentityView:
    prototype_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prototype_state: str
    current_approved_version_ref: uuid.UUID | None
    etag: str

    def __post_init__(self) -> None:
        valid_etag = (
            type(self.etag) is str and self.etag.startswith('"v')
            and self.etag.endswith('"') and self.etag[2:-1].isdigit()
        )
        if (
            type(self.prototype_id) is not uuid.UUID or self.prototype_id.int == 0
            or type(self.project_id) is not uuid.UUID or self.project_id.int == 0
            or type(self.name) is not str or not self.name
            or self.prototype_state not in {"ACTIVE", "ARCHIVED"}
            or self.current_approved_version_ref is not None and (
                type(self.current_approved_version_ref) is not uuid.UUID
                or self.current_approved_version_ref.int == 0
            )
            or not valid_etag
        ):
            raise ValueError("invalid Prototype identity view")


class AccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes, csrf_token: bytes,
        now: datetime,
    ) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def mutate(
        self, transaction: object, *, result_id: uuid.UUID, operation: str,
        project_id: uuid.UUID, prototype_id: uuid.UUID, expected_version: int,
        actor_id: uuid.UUID, name: str | None,
    ) -> PrototypeIdentityView: ...

    def result(
        self, transaction: object, *, result_id: uuid.UUID,
        project_id: uuid.UUID, prototype_id: uuid.UUID, operation: str,
    ) -> PrototypeIdentityView | None: ...


class ReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class PrototypeMutationService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: AccessPort,
        license_guard: LicensePort, authorization: ProjectAuthorizationService,
        repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository, receipts, audit,
        )):
            raise ValueError("Prototype mutation dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._authorization, self._repository = authorization, repository
        self._receipts, self._audit = receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def patch(self, command: PatchPrototypeIdentity) -> PrototypeIdentityView:
        self._validate(command, PatchPrototypeIdentity)
        name = self._name(command.name)
        return self._execute_patch(command, name)

    def archive(self, command: ArchivePrototypeIdentity) -> PrototypeIdentityView:
        self._validate(command, ArchivePrototypeIdentity)
        try:
            validate_idempotency_key(command.idempotency_key)
            fingerprint = canonical_payload_fingerprint({
                "project_id": str(command.project_id),
                "prototype_id": str(command.prototype_id),
                "expected_version": command.expected_version,
            })
            self._guard.require_valid(trace_id=command.trace_id)
            result_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._authorize(tx, command, "PRT_ARCHIVE")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation="V1_PRT_ARCHIVE", key=command.idempotency_key,
                )
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if previous is not None:
                    if previous.ref_type != "V1_PRT_ARCHIVE" or previous.status_code != 200:
                        raise PrototypeMutationError("PROTOTYPE_UNAVAILABLE")
                    replay = self._repository.result(
                        tx, result_id=previous.ref_id, project_id=command.project_id,
                        prototype_id=command.prototype_id, operation="ARCHIVE",
                    )
                    if replay is None:
                        raise PrototypeMutationError("PROTOTYPE_UNAVAILABLE")
                    return replay
                result = self._repository.mutate(
                    tx, result_id=result_id, operation="ARCHIVE",
                    project_id=command.project_id, prototype_id=command.prototype_id,
                    expected_version=command.expected_version, actor_id=actor, name=None,
                )
                self._audit_result(tx, command, actor, result, "PROTOTYPE_ARCHIVED")
                self._receipts.complete(
                    tx, scope=scope,
                    result=IdempotencyResult("V1_PRT_ARCHIVE", result_id, 200),
                )
                tx.commit()
                return result
        except PrototypeMutationError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeMutationError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeMutationError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise PrototypeMutationError(error.code) from None
        except Exception:
            raise PrototypeMutationError("PROTOTYPE_UNAVAILABLE") from None

    def _execute_patch(
        self, command: PatchPrototypeIdentity, name: str,
    ) -> PrototypeIdentityView:
        try:
            self._guard.require_valid(trace_id=command.trace_id)
            result_id = uuid.UUID(new_uuid7())
            with self._uow() as tx:
                actor = self._authorize(tx, command, "PRT_PATCH")
                result = self._repository.mutate(
                    tx, result_id=result_id, operation="PATCH",
                    project_id=command.project_id, prototype_id=command.prototype_id,
                    expected_version=command.expected_version, actor_id=actor, name=name,
                )
                self._audit_result(tx, command, actor, result, "PROTOTYPE_PATCHED")
                tx.commit()
                return result
        except PrototypeMutationError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeMutationError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeMutationError("LICENSE_OPERATION_DENIED") from None
        except Exception:
            raise PrototypeMutationError("PROTOTYPE_UNAVAILABLE") from None

    def _authorize(self, tx: object, command, operation: str) -> uuid.UUID:
        actor = self._actor(tx, command)
        result = self._authorization.require_in_transaction(
            tx, user_id=actor, project_id=command.project_id, operation=operation,
        )
        if (
            result.user_id != actor or result.project_id != command.project_id
            or result.operation != operation
        ):
            raise PrototypeMutationError("RESOURCE_NOT_FOUND")
        return actor

    def _audit_result(self, tx, command, actor, result, action: str) -> None:
        self._audit.append(tx, AuditEventDraft(
            trace_id=command.trace_id, event_scope="PROJECT",
            target_project_id=command.project_id, actor_type="USER", actor_id=actor,
            original_actor_id=None, actor_hint_digest=None, action=action,
            outcome="SUCCESS", target_owner_module="prototype",
            target_object_type="PRT-02", target_object_id=command.prototype_id,
            before_state=None, after_state=result.prototype_state,
        ))

    @staticmethod
    def _validate(command: object, expected: type) -> None:
        if (
            type(command) is not expected
            or type(command.session_token) is not bytes or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
            or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
            or type(command.prototype_id) is not uuid.UUID or command.prototype_id.int == 0
            or type(command.expected_version) is not int or command.expected_version < 0
        ):
            raise PrototypeMutationError("VALIDATION_FAILED")

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise PrototypeMutationError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if not 1 <= len(result) <= 255 or any(
            unicodedata.category(char)[0] == "C" for char in result
        ):
            raise PrototypeMutationError("VALIDATION_FAILED")
        return result

    def _actor(self, tx: object, command) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeMutationError("PROTOTYPE_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeMutationError("AUTH_ACCESS_DENIED")
        return actor
