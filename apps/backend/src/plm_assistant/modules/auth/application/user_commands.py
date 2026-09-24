"""Internal AUT-01 creation command; no login or public user route."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import TracebackType
from typing import Protocol, Self

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.auth.domain.username import normalize_username, UsernameValidationError


_ALGORITHM = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z", re.ASCII)
_PARAMETER = re.compile(r"[a-z][a-z0-9_]{0,63}\Z", re.ASCII)


class UserCommandError(RuntimeError):
    """Only fixed safe codes; never include usernames or passwords."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class CreateUser:
    actor_id: uuid.UUID
    trace_id: uuid.UUID
    username: str
    password: bytearray = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class PasswordHashResult:
    password_hash: str
    algorithm_id: str
    parameter_set: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class CreatedUser:
    user_id: uuid.UUID
    credential_version: int
    lock_version: int


class AuthTransaction(Protocol):
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: TracebackType | None) -> bool | None: ...
    def commit(self) -> None: ...


class UserRepositoryPort(Protocol):
    def add_user(self, transaction: AuthTransaction, *, username_display: str, username_normalized: str, actor_id: uuid.UUID) -> uuid.UUID | None: ...
    def add_credential(self, transaction: AuthTransaction, *, user_id: uuid.UUID, password_hash: PasswordHashResult, actor_id: uuid.UUID) -> uuid.UUID: ...
    def activate_initial_credential(self, transaction: AuthTransaction, *, user_id: uuid.UUID, credential_id: uuid.UUID, actor_id: uuid.UUID) -> bool: ...


class PasswordHasherPort(Protocol):
    def hash_password(self, password: memoryview) -> PasswordHashResult: ...


class UserCreateAccessPort(Protocol):
    def can_create_user(self, transaction: AuthTransaction, actor_id: uuid.UUID) -> bool:
        """Verify Session, License and DeploymentAdmin in this transaction."""


class UserCommandService:
    def __init__(
        self, *, unit_of_work: Callable[[], AuthTransaction], repository: UserRepositoryPort,
        access: UserCreateAccessPort, hasher: PasswordHasherPort,
        audit: AuditService, accepted_algorithms: frozenset[str],
    ) -> None:
        if any(item is None for item in (unit_of_work, repository, access, hasher, audit)):
            raise ValueError("auth command dependencies are required")
        if not accepted_algorithms or any(type(code) is not str or not _ALGORITHM.fullmatch(code) for code in accepted_algorithms):
            raise ValueError("approved password algorithms are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._access = access
        self._hasher = hasher
        self._audit = audit
        self._accepted_algorithms = accepted_algorithms

    def create_user(self, command: CreateUser) -> CreatedUser:
        if not isinstance(command, CreateUser):
            raise UserCommandError("VALIDATION_FAILED")
        password = command.password
        try:
            if type(password) is not bytearray or not 1 <= len(password) <= 4096 or b"\x00" in password:
                raise UserCommandError("VALIDATION_FAILED")
            try:
                password.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise UserCommandError("VALIDATION_FAILED") from None
            if any(type(value) is not uuid.UUID or value.int == 0 for value in (command.actor_id, command.trace_id)):
                raise UserCommandError("VALIDATION_FAILED")
            try:
                username = normalize_username(command.username)
            except UsernameValidationError:
                raise UserCommandError("VALIDATION_FAILED") from None
            with self._unit_of_work() as transaction:
                if self._access.can_create_user(transaction, command.actor_id) is not True:
                    raise UserCommandError("AUTH_ACCESS_DENIED")
                view = memoryview(password)
                try:
                    hashed = self._hasher.hash_password(view)
                finally:
                    view.release()
                self._validate_hash(hashed)
                user_id = self._repository.add_user(
                    transaction, username_display=username.display,
                    username_normalized=username.normalized, actor_id=command.actor_id,
                )
                if user_id is None:
                    raise UserCommandError("AUTH_USERNAME_CONFLICT")
                credential_id = self._repository.add_credential(
                    transaction, user_id=user_id, password_hash=hashed, actor_id=command.actor_id,
                )
                if not self._repository.activate_initial_credential(
                    transaction, user_id=user_id, credential_id=credential_id,
                    actor_id=command.actor_id,
                ):
                    raise UserCommandError("CONFLICT_STATE")
                self._audit.append(transaction, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                    actor_type="USER", actor_id=command.actor_id, original_actor_id=None,
                    actor_hint_digest=None, action="USER_CREATED", outcome="SUCCESS",
                    target_owner_module="auth", target_object_type="AUT-01",
                    target_object_id=user_id, after_state="ENABLED",
                ))
                transaction.commit()
                return CreatedUser(user_id, 1, 1)
        finally:
            if type(password) is bytearray:
                password[:] = b"\x00" * len(password)

    def _validate_hash(self, hashed: PasswordHashResult) -> None:
        if (
            not isinstance(hashed, PasswordHashResult)
            or type(hashed.password_hash) is not str
            or not 1 <= len(hashed.password_hash) <= 1024
            or type(hashed.algorithm_id) is not str
            or hashed.algorithm_id not in self._accepted_algorithms
            or type(hashed.parameter_set) is not dict
            or len(hashed.parameter_set) > 16
            or any(
                type(key) is not str or not _PARAMETER.fullmatch(key)
                or type(value) is not int or not 0 <= value <= 1_000_000_000
                for key, value in hashed.parameter_set.items()
            )
        ):
            raise UserCommandError("AUTH_HASH_UNAVAILABLE")
