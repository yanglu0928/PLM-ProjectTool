"""Administrator-only, write-only Secret creation and rotation orchestration."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.secret_access import (
    EncryptedSecretDraft, SecretConsumer, SecretPurpose, SecretRef,
)
from plm_assistant.modules.platform.application.secret_metadata import LicenseGuardPort
from plm_assistant.modules.platform.application.trace_context import new_uuid7


class SecretWriteError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateSecret:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    purpose: SecretPurpose
    consumer: SecretConsumer
    secret_value: bytearray = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RotateSecret:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    secret_ref: SecretRef
    expected_version_no: int
    secret_value: bytearray = field(repr=False)
    trace_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class DisableSecret:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    secret_ref: SecretRef
    expected_lock_version: int
    trace_id: uuid.UUID


class SecretWriteAccessPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class SecretCipherPort(Protocol):
    def encrypt(self, *, secret_ref: SecretRef, purpose: SecretPurpose,
                consumer: SecretConsumer, version_no: int,
                plaintext: bytearray) -> EncryptedSecretDraft: ...


class SecretWriteRepositoryPort(Protocol):
    def create(self, transaction: object, *, secret_ref: SecretRef,
               purpose: SecretPurpose, consumer: SecretConsumer,
               encrypted: EncryptedSecretDraft, actor: uuid.UUID) -> uuid.UUID: ...

    def lock_current(self, transaction: object, *, secret_ref: SecretRef,
                     expected_version_no: int) -> tuple[SecretPurpose, SecretConsumer] | None: ...

    def rotate(self, transaction: object, *, secret_ref: SecretRef,
               expected_version_no: int, encrypted: EncryptedSecretDraft,
               actor: uuid.UUID) -> uuid.UUID: ...

    def disable(self, transaction: object, *, secret_ref: SecretRef,
                expected_lock_version: int) -> uuid.UUID | None: ...


_CONSUMER = {
    SecretPurpose.DATABASE_PASSWORD: SecretConsumer.DATABASE_ADAPTER,
    SecretPurpose.AI_PROVIDER_KEY: SecretConsumer.AI_PROVIDER_ADAPTER,
    SecretPurpose.RERANKER_KEY: SecretConsumer.RERANKER_ADAPTER,
    SecretPurpose.INTEGRATION_CREDENTIAL: SecretConsumer.INTEGRATION_ADAPTER,
}


class SecretWriteService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: SecretWriteAccessPort,
                 license_guard: LicenseGuardPort, repository: SecretWriteRepositoryPort,
                 cipher: SecretCipherPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard,
                                         repository, cipher, audit)):
            raise ValueError("secret write dependencies are required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._cipher, self._audit = repository, cipher, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def create(self, command: CreateSecret) -> SecretRef:
        value = getattr(command, "secret_value", None)
        try:
            self._validate_common(command)
            if (type(command.purpose) is not SecretPurpose
                    or type(command.consumer) is not SecretConsumer
                    or _CONSUMER.get(command.purpose) is not command.consumer):
                raise SecretWriteError("PLATFORM_SECRET_PURPOSE_INVALID")
            self._precheck(command)
            secret_ref = SecretRef(uuid.UUID(new_uuid7()))
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                encrypted = self._cipher.encrypt(
                    secret_ref=secret_ref, purpose=command.purpose,
                    consumer=command.consumer, version_no=1,
                    plaintext=command.secret_value,
                )
                version_id = self._repo.create(tx, secret_ref=secret_ref,
                                               purpose=command.purpose, consumer=command.consumer,
                                               encrypted=encrypted, actor=actor)
                self._audit.append(tx, self._event(command.trace_id, actor, secret_ref,
                                                   version_id, "PLATFORM_SECRET_CREATE"))
                tx.commit()
                return secret_ref
        except SecretWriteError:
            raise
        except Exception:
            raise SecretWriteError("PLATFORM_SECRET_UNAVAILABLE") from None
        finally:
            if type(value) is bytearray:
                value[:] = b"\x00" * len(value)

    def rotate(self, command: RotateSecret) -> int:
        value = getattr(command, "secret_value", None)
        try:
            self._validate_common(command)
            if (type(command.secret_ref) is not SecretRef
                    or type(command.expected_version_no) is not int
                    or command.expected_version_no < 1
                    or command.expected_version_no >= 2_147_483_647):
                raise SecretWriteError("VALIDATION_FAILED")
            self._precheck(command)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                current = self._repo.lock_current(
                    tx, secret_ref=command.secret_ref,
                    expected_version_no=command.expected_version_no,
                )
                if current is None:
                    raise SecretWriteError("CONFLICT_VERSION")
                purpose, consumer = current
                version_no = command.expected_version_no + 1
                encrypted = self._cipher.encrypt(
                    secret_ref=command.secret_ref, purpose=purpose,
                    consumer=consumer, version_no=version_no,
                    plaintext=command.secret_value,
                )
                version_id = self._repo.rotate(
                    tx, secret_ref=command.secret_ref,
                    expected_version_no=command.expected_version_no,
                    encrypted=encrypted, actor=actor,
                )
                self._audit.append(tx, self._event(command.trace_id, actor,
                                                   command.secret_ref, version_id,
                                                   "PLATFORM_SECRET_ROTATE"))
                tx.commit()
                return version_no
        except SecretWriteError:
            raise
        except Exception:
            raise SecretWriteError("PLATFORM_SECRET_UNAVAILABLE") from None
        finally:
            if type(value) is bytearray:
                value[:] = b"\x00" * len(value)

    def disable(self, command: DisableSecret) -> None:
        if (type(command) is not DisableSecret
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.secret_ref) is not SecretRef
                or type(command.expected_lock_version) is not int
                or not 1 <= command.expected_lock_version < 9_223_372_036_854_775_807
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0):
            raise SecretWriteError("VALIDATION_FAILED")
        try:
            self._precheck(command)
            with self._uow() as tx:
                actor = self._require_admin(tx, command)
                version_id = self._repo.disable(
                    tx, secret_ref=command.secret_ref,
                    expected_lock_version=command.expected_lock_version,
                )
                if version_id is None:
                    raise SecretWriteError("CONFLICT_VERSION")
                self._audit.append(tx, self._event(
                    command.trace_id, actor, command.secret_ref,
                    version_id, "PLATFORM_SECRET_DISABLE",
                ))
                tx.commit()
        except SecretWriteError:
            raise
        except Exception:
            raise SecretWriteError("PLATFORM_SECRET_UNAVAILABLE") from None

    @staticmethod
    def _validate_common(command: object) -> None:
        if (type(command) not in (CreateSecret, RotateSecret)
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.secret_value) is not bytearray
                or not 1 <= len(command.secret_value) <= 65520):
            raise SecretWriteError("VALIDATION_FAILED")

    def _precheck(self, command: CreateSecret | RotateSecret | DisableSecret) -> None:
        with self._uow() as tx:
            self._require_admin(tx, command)
        self._guard.require_valid(trace_id=command.trace_id)

    def _require_admin(self, tx: object, command: CreateSecret | RotateSecret | DisableSecret) -> uuid.UUID:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise SecretWriteError("PLATFORM_SECRET_UNAVAILABLE")
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token,
            csrf_token=command.csrf_token, now=now.astimezone(timezone.utc),
        )
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise SecretWriteError("AUTH_ACCESS_DENIED")
        return actor

    @staticmethod
    def _event(trace_id: uuid.UUID, actor: uuid.UUID, ref: SecretRef,
               version_id: uuid.UUID, action: str) -> AuditEventDraft:
        return AuditEventDraft(
            trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
            actor_type="USER", actor_id=actor, original_actor_id=None,
            actor_hint_digest=None, action=action, outcome="SUCCESS",
            target_owner_module="platform", target_object_type="PLT-02",
            target_object_id=ref.secret_id, target_version_id=version_id,
        )
