"""One-time, local-only initial DeploymentAdmin creation."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.auth.application.ports.password_hash import PasswordHashResult, PasswordHasherPort
from plm_assistant.modules.auth.domain.username import UsernameValidationError, normalize_username


class InitialAdminError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class InitializeAdmin:
    username: str
    password: bytearray = field(repr=False)
    trace_id: uuid.UUID


class InitialAdminRepositoryPort(Protocol):
    def claim_empty(self, transaction: object) -> bool: ...
    def create(self, transaction: object, *, username_display: str,
               username_normalized: str, hashed: PasswordHashResult) -> uuid.UUID: ...


class InitialAdminService:
    def __init__(self, *, unit_of_work: Callable[[], object], repository: InitialAdminRepositoryPort,
                 hasher: PasswordHasherPort, audit: AuditService) -> None:
        if any(value is None for value in (unit_of_work, repository, hasher, audit)):
            raise ValueError("initial admin dependencies are required")
        self._uow, self._repository, self._hasher, self._audit = unit_of_work, repository, hasher, audit

    def initialize(self, command: InitializeAdmin) -> uuid.UUID:
        password = getattr(command, "password", None)
        try:
            if (type(command) is not InitializeAdmin or type(command.trace_id) is not uuid.UUID
                    or command.trace_id.int == 0 or type(password) is not bytearray
                    or not 15 <= len(password) <= 1024 or b"\x00" in password):
                raise InitialAdminError("VALIDATION_FAILED")
            try:
                decoded = password.decode("utf-8", errors="strict")
                if len(decoded) < 15:
                    raise ValueError()
                del decoded
                username = normalize_username(command.username)
            except (UnicodeDecodeError, ValueError, UsernameValidationError):
                raise InitialAdminError("VALIDATION_FAILED") from None
            with self._uow() as tx:
                if self._repository.claim_empty(tx) is not True:
                    raise InitialAdminError("AUTH_INITIALIZATION_CLOSED")
                view = memoryview(password)
                try:
                    hashed = self._hasher.hash_password(view)
                except Exception:
                    raise InitialAdminError("SYSTEM_UNAVAILABLE") from None
                finally:
                    view.release()
                if (type(hashed) is not PasswordHashResult
                        or type(hashed.password_hash) is not str or not 1 <= len(hashed.password_hash) <= 1024
                        or hashed.algorithm_id != "SCRYPT" or type(hashed.parameter_set) is not dict):
                    raise InitialAdminError("SYSTEM_UNAVAILABLE")
                user_id = self._repository.create(
                    tx, username_display=username.display,
                    username_normalized=username.normalized, hashed=hashed,
                )
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                    actor_type="UNRESOLVED", actor_id=None, original_actor_id=None,
                    actor_hint_digest=None, action="AUTH_INITIAL_ADMIN_CREATED", outcome="SUCCESS",
                    target_owner_module="auth", target_object_type="AUT-01", target_object_id=user_id,
                    after_state="ENABLED", reason_code="LOCAL_BOOTSTRAP",
                ))
                tx.commit()
                return user_id
        finally:
            if type(password) is bytearray:
                password[:] = b"\x00" * len(password)
