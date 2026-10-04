"""Internal login orchestration; HTTP transport and cookie remain separate."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.auth.application.login_rate_limit import LoginRateLimitError
from plm_assistant.modules.auth.application.session_service import (
    IssuedSession, PasswordIssueProof, SessionError, SessionService,
)
from plm_assistant.modules.auth.domain.username import UsernameValidationError, normalize_username


class LoginError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LoginAttempt:
    username: str = field(repr=False)
    password: bytearray = field(repr=False)
    client_ip: str = field(repr=False)
    trace_id: uuid.UUID


class LoginRatePort(Protocol):
    def require_slot(self, *, client_ip: str, username: str) -> None: ...


class LoginIdentityPort(Protocol):
    def find_active(self, transaction: object, normalized_username: str) -> uuid.UUID | None: ...


class MissingIdentityVerifierPort(Protocol):
    def consume(self, password: bytearray) -> None: ...


class LoginService:
    def __init__(self, *, unit_of_work: Callable[[], object], rate: LoginRatePort,
                 identity: LoginIdentityPort, missing_verifier: MissingIdentityVerifierPort,
                 sessions: SessionService, audit: AuditService) -> None:
        if any(item is None for item in (unit_of_work, rate, identity,
                                         missing_verifier, sessions, audit)):
            raise ValueError("login dependencies are required")
        self._uow, self._rate, self._identity = unit_of_work, rate, identity
        self._missing, self._sessions, self._audit = missing_verifier, sessions, audit

    def login(self, attempt: LoginAttempt) -> IssuedSession:
        password = getattr(attempt, "password", None)
        try:
            if (type(attempt) is not LoginAttempt
                    or type(attempt.username) is not str or len(attempt.username) > 1024
                    or type(attempt.client_ip) is not str
                    or type(attempt.trace_id) is not uuid.UUID or attempt.trace_id.int == 0
                    or type(password) is not bytearray or not 1 <= len(password) <= 1024):
                raise LoginError("AUTH_INVALID_CREDENTIALS")
            try:
                self._rate.require_slot(client_ip=attempt.client_ip, username=attempt.username)
            except LoginRateLimitError as exc:
                raise LoginError(exc.code) from None
            except Exception:
                raise LoginError("SYSTEM_UNAVAILABLE") from None
            try:
                normalized = normalize_username(attempt.username).normalized
            except UsernameValidationError:
                normalized = None
            try:
                with self._uow() as tx:
                    actor = self._identity.find_active(tx, normalized) if normalized is not None else None
            except Exception:
                raise LoginError("SYSTEM_UNAVAILABLE") from None
            if actor is None:
                try:
                    self._missing.consume(password)
                except Exception:
                    raise LoginError("SYSTEM_UNAVAILABLE") from None
                self._record_denial(attempt.trace_id, None)
                raise LoginError("AUTH_INVALID_CREDENTIALS")
            if type(actor) is not uuid.UUID or actor.int == 0:
                raise LoginError("SYSTEM_UNAVAILABLE")
            try:
                return self._sessions.issue(
                    user_id=actor, trace_id=attempt.trace_id,
                    proof=PasswordIssueProof(password),
                )
            except SessionError as exc:
                if exc.code == "AUTH_ACCESS_DENIED":
                    self._record_denial(attempt.trace_id, actor)
                    raise LoginError("AUTH_INVALID_CREDENTIALS") from None
                raise LoginError("SYSTEM_UNAVAILABLE") from None
            except Exception:
                raise LoginError("SYSTEM_UNAVAILABLE") from None
        finally:
            if type(password) is bytearray:
                password[:] = b"\x00" * len(password)

    def _record_denial(self, trace_id: uuid.UUID, actor: uuid.UUID | None) -> None:
        try:
            with self._uow() as tx:
                self._audit.append(tx, AuditEventDraft(
                    trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                    actor_type="USER" if actor is not None else "UNRESOLVED",
                    actor_id=actor, original_actor_id=None, actor_hint_digest=None,
                    action="AUTH_LOGIN_DENIED", outcome="DENIED",
                    reason_code="INVALID_CREDENTIALS",
                ))
                tx.commit()
        except Exception:
            raise LoginError("SYSTEM_UNAVAILABLE") from None
