"""Authorized, atomic Requirement package and identity creation."""

from __future__ import annotations

import re
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
    IdempotencyError,
    IdempotencyResult,
    IdempotencyScope,
    canonical_payload_fingerprint,
    validate_idempotency_key,
)
from plm_assistant.modules.platform.application.trace_context import new_uuid7
from plm_assistant.modules.project.application.authorization import (
    ProjectAuthorizationError,
    ProjectAuthorizationService,
)


_PACKAGE_OPERATION = "V1_REQ_PACKAGE_CREATE"
_REQUIREMENT_OPERATION = "V1_REQ_CREATE"
_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")


class RequirementIdentityCreateError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateRequirementPackage:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class CreateRequirementIdentity:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    project_id: uuid.UUID
    requirement_code: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RequirementPackageInitialView:
    requirement_package_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    created_at: datetime
    package_state: str = "ACTIVE"
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (
            type(self.requirement_package_id) is not uuid.UUID
            or self.requirement_package_id.int == 0
            or type(self.project_id) is not uuid.UUID
            or self.project_id.int == 0
            or type(self.name) is not str
            or not self.name
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
            or self.package_state != "ACTIVE"
            or self.etag != '"v0"'
        ):
            raise ValueError("invalid initial RequirementPackage view")


@dataclass(frozen=True, slots=True)
class RequirementInitialView:
    requirement_id: uuid.UUID
    project_id: uuid.UUID
    requirement_code: str
    created_at: datetime
    requirement_state: str = "ACTIVE"
    current_approved_version_ref: None = None
    etag: str = '"v0"'

    def __post_init__(self) -> None:
        if (
            type(self.requirement_id) is not uuid.UUID
            or self.requirement_id.int == 0
            or type(self.project_id) is not uuid.UUID
            or self.project_id.int == 0
            or type(self.requirement_code) is not str
            or _CODE.fullmatch(self.requirement_code) is None
            or type(self.created_at) is not datetime
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
            or self.requirement_state != "ACTIVE"
            or self.current_approved_version_ref is not None
            or self.etag != '"v0"'
        ):
            raise ValueError("invalid initial Requirement view")


class RequirementIdentityCreateAccessPort(Protocol):
    def authenticated_user(
        self,
        transaction: object,
        *,
        session_token: bytes,
        csrf_token: bytes,
        now: datetime,
    ) -> uuid.UUID | None: ...


class RequirementIdentityCreateLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RequirementIdentityCreateRepositoryPort(Protocol):
    def create_package(
        self,
        transaction: object,
        *,
        requirement_package_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        actor_id: uuid.UUID,
    ) -> RequirementPackageInitialView: ...

    def package_result(
        self,
        transaction: object,
        *,
        requirement_package_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> RequirementPackageInitialView | None: ...

    def create_requirement(
        self,
        transaction: object,
        *,
        requirement_id: uuid.UUID,
        project_id: uuid.UUID,
        requirement_code: str,
        requirement_code_normalized: str,
        actor_id: uuid.UUID,
    ) -> RequirementInitialView: ...

    def requirement_result(
        self,
        transaction: object,
        *,
        requirement_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> RequirementInitialView | None: ...


class RequirementIdentityCreateReceiptPort(Protocol):
    def reserve(
        self,
        transaction: object,
        *,
        scope: IdempotencyScope,
        request_fingerprint: bytes,
    ) -> IdempotencyResult | None: ...

    def complete(
        self,
        transaction: object,
        *,
        scope: IdempotencyScope,
        result: IdempotencyResult,
    ) -> None: ...


class RequirementIdentityCreateService:
    def __init__(
        self,
        *,
        unit_of_work: Callable[[], object],
        access: RequirementIdentityCreateAccessPort,
        license_guard: RequirementIdentityCreateLicensePort,
        authorization: ProjectAuthorizationService,
        repository: RequirementIdentityCreateRepositoryPort,
        receipts: RequirementIdentityCreateReceiptPort,
        audit: AuditService,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if any(
            item is None
            for item in (
                unit_of_work,
                access,
                license_guard,
                authorization,
                repository,
                receipts,
                audit,
            )
        ):
            raise ValueError("Requirement identity create dependencies are required")
        self._uow = unit_of_work
        self._access = access
        self._guard = license_guard
        self._authorization = authorization
        self._repository = repository
        self._receipts = receipts
        self._audit = audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create_package(
        self, command: CreateRequirementPackage
    ) -> RequirementPackageInitialView:
        self._validate_common(command)
        name = self._name(command.name)
        return self._execute(
            command=command,
            operation=_PACKAGE_OPERATION,
            authorization_operation="REQ_PACKAGE_CREATE",
            fingerprint=canonical_payload_fingerprint(
                {"project_id": str(command.project_id), "name": name}
            ),
            create=lambda tx, root_id, actor: self._repository.create_package(
                tx,
                requirement_package_id=root_id,
                project_id=command.project_id,
                name=name,
                actor_id=actor,
            ),
            replay=lambda tx, root_id: self._repository.package_result(
                tx,
                requirement_package_id=root_id,
                project_id=command.project_id,
            ),
            action="REQUIREMENT_PACKAGE_CREATED",
            object_type="REQ-01",
            status_code=201,
        )

    def create_requirement(
        self, command: CreateRequirementIdentity
    ) -> RequirementInitialView:
        self._validate_common(command)
        code = self._code(command.requirement_code)
        return self._execute(
            command=command,
            operation=_REQUIREMENT_OPERATION,
            authorization_operation="REQ_CREATE",
            fingerprint=canonical_payload_fingerprint(
                {"project_id": str(command.project_id), "requirement_code": code}
            ),
            create=lambda tx, root_id, actor: self._repository.create_requirement(
                tx,
                requirement_id=root_id,
                project_id=command.project_id,
                requirement_code=code,
                requirement_code_normalized=code.upper(),
                actor_id=actor,
            ),
            replay=lambda tx, root_id: self._repository.requirement_result(
                tx,
                requirement_id=root_id,
                project_id=command.project_id,
            ),
            action="REQUIREMENT_CREATED",
            object_type="REQ-02",
            status_code=201,
        )

    def _execute(
        self,
        *,
        command: CreateRequirementPackage | CreateRequirementIdentity,
        operation: str,
        authorization_operation: str,
        fingerprint: bytes,
        create,
        replay,
        action: str,
        object_type: str,
        status_code: int,
    ):
        try:
            validate_idempotency_key(command.idempotency_key)
            root_id = uuid.UUID(new_uuid7())
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                actor = self._actor(tx, command)
                authorized = self._authorization.require_in_transaction(
                    tx,
                    user_id=actor,
                    project_id=command.project_id,
                    operation=authorization_operation,
                )
                if (
                    authorized.user_id != actor
                    or authorized.project_id != command.project_id
                    or authorized.operation != authorization_operation
                ):
                    raise RequirementIdentityCreateError("RESOURCE_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor,
                    project_id=command.project_id,
                    operation=operation,
                    key=command.idempotency_key,
                )
                previous = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint
                )
                if previous is not None:
                    if (
                        previous.ref_type != operation
                        or previous.status_code != status_code
                    ):
                        raise RequirementIdentityCreateError(
                            "REQUIREMENT_UNAVAILABLE"
                        )
                    result = replay(tx, previous.ref_id)
                    if result is None:
                        raise RequirementIdentityCreateError(
                            "REQUIREMENT_UNAVAILABLE"
                        )
                    return result
                result = create(tx, root_id, actor)
                self._audit.append(
                    tx,
                    AuditEventDraft(
                        trace_id=command.trace_id,
                        event_scope="PROJECT",
                        target_project_id=command.project_id,
                        actor_type="USER",
                        actor_id=actor,
                        original_actor_id=None,
                        actor_hint_digest=None,
                        action=action,
                        outcome="SUCCESS",
                        target_owner_module="requirement",
                        target_object_type=object_type,
                        target_object_id=root_id,
                        after_state="ACTIVE",
                    ),
                )
                self._receipts.complete(
                    tx,
                    scope=scope,
                    result=IdempotencyResult(operation, root_id, status_code),
                )
                tx.commit()
                return result
        except RequirementIdentityCreateError:
            raise
        except ProjectAuthorizationError as error:
            raise RequirementIdentityCreateError(error.code) from None
        except RuntimeLicenseError:
            raise RequirementIdentityCreateError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise RequirementIdentityCreateError(error.code) from None
        except Exception:
            raise RequirementIdentityCreateError("REQUIREMENT_UNAVAILABLE") from None

    @staticmethod
    def _validate_common(
        command: CreateRequirementPackage | CreateRequirementIdentity,
    ) -> None:
        if (
            type(command) not in (CreateRequirementPackage, CreateRequirementIdentity)
            or type(command.session_token) is not bytes
            or len(command.session_token) != 32
            or type(command.csrf_token) is not bytes
            or len(command.csrf_token) != 32
            or type(command.trace_id) is not uuid.UUID
            or command.trace_id.int == 0
            or type(command.project_id) is not uuid.UUID
            or command.project_id.int == 0
        ):
            raise RequirementIdentityCreateError("VALIDATION_FAILED")

    @staticmethod
    def _name(value: object) -> str:
        if type(value) is not str:
            raise RequirementIdentityCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if (
            not 1 <= len(result) <= 255
            or any(unicodedata.category(char)[0] == "C" for char in result)
        ):
            raise RequirementIdentityCreateError("VALIDATION_FAILED")
        return result

    @staticmethod
    def _code(value: object) -> str:
        if type(value) is not str:
            raise RequirementIdentityCreateError("VALIDATION_FAILED")
        result = unicodedata.normalize("NFKC", value).strip()
        if _CODE.fullmatch(result) is None:
            raise RequirementIdentityCreateError("VALIDATION_FAILED")
        return result

    def _actor(
        self,
        tx: object,
        command: CreateRequirementPackage | CreateRequirementIdentity,
    ) -> uuid.UUID:
        now = self._clock()
        if (
            type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset() is None
        ):
            raise RequirementIdentityCreateError("REQUIREMENT_UNAVAILABLE")
        actor = self._access.authenticated_user(
            tx,
            session_token=command.session_token,
            csrf_token=command.csrf_token,
            now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise RequirementIdentityCreateError("AUTH_ACCESS_DENIED")
        return actor
