"""Authorized, atomic Prototype package and identity creation."""

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


class PrototypeIdentityCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreatePrototypePackage:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CreatePrototypeIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class PrototypePackageInitialView:
    prototype_package_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    package_state: str = "ACTIVE"
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        _validate_view(self.prototype_package_id, self.project_id, self.name, self.created_at)
        if self.package_state != "ACTIVE" or self.etag != '"v0"':
            raise ValueError("invalid initial PrototypePackage view")


@dataclass(frozen=True, slots=True)
class PrototypeInitialView:
    prototype_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    prototype_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        _validate_view(self.prototype_id, self.project_id, self.name, self.created_at)
        if (
            self.prototype_state != "ACTIVE"
            or self.current_approved_version_ref is not None
            or self.etag != '"v0"'
        ):
            raise ValueError("invalid initial Prototype view")


def _validate_view(root_id: uuid.UUID, project_id: uuid.UUID, name: str, created_at: datetime) -> None:
    if (
        type(root_id) is not uuid.UUID or root_id.int == 0
        or type(project_id) is not uuid.UUID or project_id.int == 0
        or type(name) is not str or not name
        or type(created_at) is not datetime or created_at.tzinfo is None
        or created_at.utcoffset() is None
    ):
        raise ValueError("invalid initial Prototype identity view")


class AccessPort(Protocol):
    def authenticated_user(
        self, transaction: object, *, session_token: bytes, csrf_token: bytes,
        now: datetime,
    ) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RepositoryPort(Protocol):
    def create_package(
        self, transaction: object, *, prototype_package_id: uuid.UUID,
        project_id: uuid.UUID, name: str, actor_id: uuid.UUID,
    ) -> PrototypePackageInitialView: ...

    def package_result(
        self, transaction: object, *, prototype_package_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PrototypePackageInitialView | None: ...

    def create_prototype(
        self, transaction: object, *, prototype_id: uuid.UUID,
        project_id: uuid.UUID, name: str, actor_id: uuid.UUID,
    ) -> PrototypeInitialView: ...

    def prototype_result(
        self, transaction: object, *, prototype_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PrototypeInitialView | None: ...


class ReceiptPort(Protocol):
    def reserve(
        self, transaction: object, *, scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self, transaction: object, *, scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class PrototypeIdentityCreateService:
    def __init__(
        self, *, unit_of_work: Callable[[], object], access: AccessPort,
        license_guard: LicensePort, authorization: ProjectAuthorizationService,
        repository: RepositoryPort, receipts: ReceiptPort, audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(value is None for value in (
            unit_of_work, access, license_guard, authorization, repository, receipts, audit,
        )):
            raise ValueError("Prototype identity create dependencies are required")
        self._uow = unit_of_work
        self._access = access
        self._guard = license_guard
        self._authorization = authorization
        self._repository = repository
        self._receipts = receipts
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create_package(self, command: CreatePrototypePackage) -> PrototypePackageInitialView:
        return self._execute(
            command, operation="V1_PRT_PACKAGE_CREATE",
            authorization_operation="PRT_PACKAGE_CREATE", object_type="PRT-01",
            action="PROTOTYPE_PACKAGE_CREATED",
            create=lambda tx, root, actor, name: self._repository.create_package(
                tx, prototype_package_id=root, project_id=command.project_id,
                name=name, actor_id=actor,
            ),
            replay=lambda tx, root: self._repository.package_result(
                tx, prototype_package_id=root, project_id=command.project_id,
            ),
        )

    def create_prototype(self, command: CreatePrototypeIdentity) -> PrototypeInitialView:
        return self._execute(
            command, operation="V1_PRT_CREATE", authorization_operation="PRT_CREATE",
            object_type="PRT-02", action="PROTOTYPE_CREATED",
            create=lambda tx, root, actor, name: self._repository.create_prototype(
                tx, prototype_id=root, project_id=command.project_id,
                name=name, actor_id=actor,
            ),
            replay=lambda tx, root: self._repository.prototype_result(
                tx, prototype_id=root, project_id=command.project_id,
            ),
        )

    def _execute(
        self, command: CreatePrototypePackage | CreatePrototypeIdentity, *,
        operation: str, authorization_operation: str, object_type: str,
        action: str, create, replay,
    ):
        self._validate(command)
        name = self._name(command.name)
        fingerprint = canonical_payload_fingerprint({
            "project_id": str(command.project_id), "name": name,
        })
        try:
            validate_idempotency_key(command.idempotency_key)
            root_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx, user_id=actor, project_id=command.project_id,
                    operation=authorization_operation,
                )
                if (
                    authorized.user_id != actor
                    or authorized.project_id != command.project_id
                    or authorized.operation != authorization_operation
                ):
                    raise PrototypeIdentityCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=command.project_id,
                    operation=operation, key=command.idempotency_key,
                )
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint,
                )
                if previous is not None:
                    if previous.ref_type != operation or previous.status_code != 201:
                        raise PrototypeIdentityCreateError("PROTOTYPE_UNAVAILABLE")
                    result = replay(tx, previous.ref_id)
                    if result is None:
                        raise PrototypeIdentityCreateError("PROTOTYPE_UNAVAILABLE")
                    return result
                result = create(tx, root_id, actor, name)
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="PROJECT",
                    target_project_id=command.project_id, actor_type="USER",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action=action, outcome="SUCCESS", target_owner_module="prototype",
                    target_object_type=object_type, target_object_id=root_id,
                    after_state="ACTIVE",
                ))
                self._receipts.complete(
                    tx, scope=scope, result=IdempotencyResult(operation, root_id, 201),
                )
                tx.commit()
                return result
        except PrototypeIdentityCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise PrototypeIdentityCreateError(error.code) from None
        except RuntimeLicenseError:
            raise PrototypeIdentityCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise PrototypeIdentityCreateError(error.code) from None
        except Exception:
            raise PrototypeIdentityCreateError("PROTOTYPE_UNAVAILABLE") from None

    @staticmethod
    def _validate(command: object) -> None:
        if (
            type(command) not in (CreatePrototypePackage, CreatePrototypeIdentity)
            or type(command.session_token) is not bytes or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
            or type(command.project_id) is not uuid.UUID or command.project_id.int == 0
        ):
            raise PrototypeIdentityCreateError("VALIDATION_FAILED")

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise PrototypeIdentityCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (
            not 1 <= len(result) <= 255
            or any(unicodedata.category(char)[0] == "C" for char in result)
        ):
            raise PrototypeIdentityCreateError("VALIDATION_FAILED")
        return result

    def _actor(
        self, tx: object, command: CreatePrototypePackage | CreatePrototypeIdentity,
    ) -> uuid.UUID:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise PrototypeIdentityCreateError("PROTOTYPE_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx, session_token=command.session_token, csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise PrototypeIdentityCreateError("AUTH_ACCESS_DENIED")
        return actor
