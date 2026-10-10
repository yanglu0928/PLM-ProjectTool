"""Internal server-session lifecycle; no HTTP or login wiring."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from plm_assistant.modules.audit.application.public import AuditEventDraft, AuditService
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyResult, IdempotencyScope, canonical_payload_fingerprint,
    validate_idempotency_key,
)


class SessionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(slots=True)
class PasswordIssueProof:
    """Caller-owned short-lived password bytes; never persist or log this object."""

    password: bytearray = field(repr=False)

    def erase(self) -> None:
        if type(self.password) is bytearray:
            self.password[:] = b"\x00" * len(self.password)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    absolute_lifetime: timedelta = timedelta(hours=8)
    idle_lifetime: timedelta = timedelta(minutes=30)

    def __post_init__(self) -> None:
        if not timedelta(0) < self.idle_lifetime <= self.absolute_lifetime <= timedelta(hours=24):
            raise ValueError("invalid session lifetime")


@dataclass(frozen=True, slots=True)
class IssuedSession:
    session_id: uuid.UUID
    user_id: uuid.UUID
    token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    absolute_expires_at: datetime
    idle_expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionPrincipal:
    session_id: uuid.UUID
    user_id: uuid.UUID
    credential_version: int
    absolute_expires_at: datetime
    idle_expires_at: datetime


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: uuid.UUID
    user_id: uuid.UUID
    credential_version: int
    csrf_digest: bytes = field(repr=False)
    absolute_expires_at: datetime
    idle_expires_at: datetime
    revoked_at: datetime | None
    user_state: str
    current_credential_version: int
    revoke_reason: str | None = None


class SessionRepositoryPort(Protocol):
    def current_credential_version(self, transaction: object, user_id: uuid.UUID) -> int | None: ...
    def create(self, transaction: object, *, user_id: uuid.UUID, credential_version: int,
               token_digest: bytes, csrf_digest: bytes, now: datetime,
               absolute_expires_at: datetime, idle_expires_at: datetime) -> uuid.UUID: ...
    def find_by_token_digest(self, transaction: object, digest: bytes) -> SessionRecord | None: ...
    def revoke(self, transaction: object, session_id: uuid.UUID, now: datetime, reason: str) -> bool: ...
    def lock_user(self, transaction: object, user_id: uuid.UUID) -> bool: ...
    def revoke_user_sessions(self, transaction: object, user_id: uuid.UUID, now: datetime, reason: str) -> int: ...


class SessionIssueAccessPort(Protocol):
    def can_issue(self, transaction: object, user_id: uuid.UUID, credential_version: int, proof: object) -> bool:
        """Validate fresh authentication proof and applicable login policy; deny by default."""


class SessionAdminAccessPort(Protocol):
    def can_revoke_user_sessions(self, transaction: object, actor_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Verify actor Session, License and DeploymentAdmin in this transaction."""


class SessionIdempotencyPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class SessionService:
    def __init__(self, *, unit_of_work: Callable[[], object], repository: SessionRepositoryPort,
                 issue_access: SessionIssueAccessPort, audit: AuditService,
                 admin_access: SessionAdminAccessPort | None = None,
                 idempotency: SessionIdempotencyPort | None = None,
                 policy: SessionPolicy | None = None,
                 clock: Callable[[], datetime] | None = None,
                 random_bytes: Callable[[int], bytes] | None = None) -> None:
        if any(item is None for item in (unit_of_work, repository, issue_access, audit)):
            raise ValueError("session dependencies are required")
        self._unit_of_work = unit_of_work
        self._repository = repository
        self._issue_access = issue_access
        self._audit = audit
        self._admin_access = admin_access
        self._idempotency = idempotency
        self._policy = policy or SessionPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._random_bytes = random_bytes or secrets.token_bytes

    def issue(self, *, user_id: uuid.UUID, trace_id: uuid.UUID, proof: object) -> IssuedSession:
        try:
            return self._issue(user_id=user_id, trace_id=trace_id, proof=proof)
        finally:
            if isinstance(proof, PasswordIssueProof):
                proof.erase()

    def _issue(self, *, user_id: uuid.UUID, trace_id: uuid.UUID, proof: object) -> IssuedSession:
        self._ids(user_id, trace_id)
        if proof is None:
            raise SessionError("AUTH_ACCESS_DENIED")
        now = self._now()
        with self._unit_of_work() as transaction:  # type: ignore[attr-defined]
            version = self._repository.current_credential_version(transaction, user_id)
            if version is None or self._issue_access.can_issue(transaction, user_id, version, proof) is not True:
                raise SessionError("AUTH_ACCESS_DENIED")
            token, csrf = self._random_bytes(32), self._random_bytes(32)
            if type(token) is not bytes or type(csrf) is not bytes or len(token) != 32 or len(csrf) != 32 or token == csrf:
                raise SessionError("AUTH_ENTROPY_UNAVAILABLE")
            absolute = now + self._policy.absolute_lifetime
            idle = now + self._policy.idle_lifetime
            session_id = self._repository.create(
                transaction, user_id=user_id, credential_version=version,
                token_digest=hashlib.sha256(token).digest(), csrf_digest=hashlib.sha256(csrf).digest(),
                now=now, absolute_expires_at=absolute, idle_expires_at=idle,
            )
            self._audit.append(transaction, self._event(trace_id, user_id, session_id, "SESSION_ISSUED"))
            transaction.commit()
        return IssuedSession(session_id, user_id, token, csrf, absolute, idle)

    def validate(self, token: bytes, *, csrf_token: bytes | None = None,
                 require_csrf: bool = False) -> SessionPrincipal:
        self._token(token)
        if require_csrf:
            self._token(csrf_token)
        now = self._now()
        with self._unit_of_work() as transaction:  # type: ignore[attr-defined]
            record = self._repository.find_by_token_digest(transaction, hashlib.sha256(token).digest())
            self._check_active(record, now)
            assert record is not None
            if require_csrf and not hmac.compare_digest(hashlib.sha256(csrf_token).digest(), record.csrf_digest):
                raise SessionError("AUTH_ACCESS_DENIED")
            return SessionPrincipal(record.session_id, record.user_id, record.credential_version,
                                    record.absolute_expires_at, record.idle_expires_at)

    def revoke(self, *, token: bytes, csrf_token: bytes, trace_id: uuid.UUID) -> bool:
        self._ids(trace_id)
        self._token(token)
        self._token(csrf_token)
        now = self._now()
        with self._unit_of_work() as transaction:  # type: ignore[attr-defined]
            record = self._repository.find_by_token_digest(transaction, hashlib.sha256(token).digest())
            self._check_active(record, now)
            assert record is not None
            if not hmac.compare_digest(hashlib.sha256(csrf_token).digest(), record.csrf_digest):
                raise SessionError("AUTH_ACCESS_DENIED")
            if not self._repository.revoke(transaction, record.session_id, now, "LOGOUT"):
                raise SessionError("AUTH_SESSION_EXPIRED")
            self._audit.append(transaction, self._event(trace_id, record.user_id, record.session_id, "SESSION_REVOKED"))
            transaction.commit()
            return True

    def logout(self, *, token: bytes, csrf_token: bytes, idempotency_key: str,
               trace_id: uuid.UUID) -> bool:
        """Atomic first logout; exact completed replay grants no new authority."""

        self._ids(trace_id)
        self._token(token)
        self._token(csrf_token)
        validate_idempotency_key(idempotency_key)
        if self._idempotency is None:
            raise SessionError("SYSTEM_UNAVAILABLE")
        now = self._now()
        with self._unit_of_work() as transaction:  # type: ignore[attr-defined]
            record = self._repository.find_by_token_digest(
                transaction, hashlib.sha256(token).digest()
            )
            if record is None:
                raise SessionError("AUTH_SESSION_EXPIRED")
            if not hmac.compare_digest(hashlib.sha256(csrf_token).digest(), record.csrf_digest):
                raise SessionError("AUTH_ACCESS_DENIED")
            scope = IdempotencyScope.from_key(
                actor_id=record.user_id, project_id=None,
                operation="V1_AUTH_LOGOUT", key=idempotency_key,
            )
            fingerprint = canonical_payload_fingerprint({"session_id": str(record.session_id)})
            replay = self._idempotency.reserve(
                transaction, scope=scope, request_fingerprint=fingerprint,
            )
            if replay is not None:
                # READ COMMITTED: the initial Session read may predate a
                # concurrent winner's commit; refresh after unique-key wait.
                current = self._repository.find_by_token_digest(
                    transaction, hashlib.sha256(token).digest()
                )
                if (current is None or current.revoked_at is None
                        or current.revoke_reason != "LOGOUT"
                        or replay != IdempotencyResult("V1_AUTH_SESSION", record.session_id, 200)):
                    raise SessionError("SYSTEM_UNAVAILABLE")
                return True
            self._check_active(record, now)
            if not self._repository.revoke(transaction, record.session_id, now, "LOGOUT"):
                raise SessionError("AUTH_SESSION_EXPIRED")
            self._audit.append(
                transaction,
                self._event(trace_id, record.user_id, record.session_id, "SESSION_REVOKED"),
            )
            self._idempotency.complete(
                transaction, scope=scope,
                result=IdempotencyResult("V1_AUTH_SESSION", record.session_id, 200),
            )
            transaction.commit()
            return True

    def renew(self, *, token: bytes, csrf_token: bytes, trace_id: uuid.UUID) -> IssuedSession:
        """Atomically retire the old bearer/CSRF pair and issue a fresh pair."""
        self._ids(trace_id)
        self._token(token)
        self._token(csrf_token)
        now = self._now()
        with self._unit_of_work() as transaction:  # type: ignore[attr-defined]
            record = self._repository.find_by_token_digest(transaction, hashlib.sha256(token).digest())
            self._check_active(record, now)
            assert record is not None
            if not hmac.compare_digest(hashlib.sha256(csrf_token).digest(), record.csrf_digest):
                raise SessionError("AUTH_ACCESS_DENIED")
            new_token, new_csrf = self._random_bytes(32), self._random_bytes(32)
            if (type(new_token) is not bytes or type(new_csrf) is not bytes
                    or len(new_token) != 32 or len(new_csrf) != 32
                    or hmac.compare_digest(new_token, new_csrf)
                    or hmac.compare_digest(new_token, token)
                    or hmac.compare_digest(new_csrf, csrf_token)):
                raise SessionError("AUTH_ENTROPY_UNAVAILABLE")
            if not self._repository.revoke(transaction, record.session_id, now, "RENEWED"):
                raise SessionError("AUTH_SESSION_EXPIRED")
            absolute = record.absolute_expires_at
            idle = min(now + self._policy.idle_lifetime, absolute)
            new_id = self._repository.create(
                transaction, user_id=record.user_id, credential_version=record.credential_version,
                token_digest=hashlib.sha256(new_token).digest(), csrf_digest=hashlib.sha256(new_csrf).digest(),
                now=now, absolute_expires_at=absolute, idle_expires_at=idle,
            )
            self._audit.append(transaction, self._event(trace_id, record.user_id, new_id, "SESSION_RENEWED"))
            transaction.commit()
        return IssuedSession(new_id, record.user_id, new_token, new_csrf, absolute, idle)

    def revoke_user_sessions(self, *, actor_id: uuid.UUID, user_id: uuid.UUID,
                             trace_id: uuid.UUID) -> int:
        """Admin-only internal command; unavailable without a real access adapter."""
        self._ids(actor_id, user_id, trace_id)
        if self._admin_access is None:
            raise SessionError("AUTH_ACCESS_DENIED")
        now = self._now()
        with self._unit_of_work() as transaction:  # type: ignore[attr-defined]
            if self._admin_access.can_revoke_user_sessions(transaction, actor_id, user_id) is not True:
                raise SessionError("AUTH_ACCESS_DENIED")
            if not self._repository.lock_user(transaction, user_id):
                raise SessionError("AUTH_ACCESS_DENIED")
            count = self._repository.revoke_user_sessions(transaction, user_id, now, "ADMIN_REVOKE")
            self._audit.append(transaction, AuditEventDraft(
                trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                actor_type="USER", actor_id=actor_id, original_actor_id=None,
                actor_hint_digest=None, action="USER_SESSIONS_REVOKED", outcome="SUCCESS",
                target_owner_module="auth", target_object_type="AUT-01",
                target_object_id=user_id,
            ))
            transaction.commit()
            return count

    @staticmethod
    def _check_active(record: SessionRecord | None, now: datetime) -> None:
        if (record is None or record.revoked_at is not None or record.user_state != "ENABLED"
                or record.credential_version != record.current_credential_version
                or now >= record.absolute_expires_at or now >= record.idle_expires_at):
            raise SessionError("AUTH_SESSION_EXPIRED")

    @staticmethod
    def _event(trace_id: uuid.UUID, user_id: uuid.UUID, session_id: uuid.UUID, action: str) -> AuditEventDraft:
        return AuditEventDraft(trace_id=trace_id, event_scope="DEPLOYMENT", target_project_id=None,
                               actor_type="USER", actor_id=user_id, original_actor_id=None,
                               actor_hint_digest=None, action=action, outcome="SUCCESS",
                               target_owner_module="auth", target_object_type="AUT-02",
                               target_object_id=session_id)

    def _now(self) -> datetime:
        value = self._clock()
        if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
            raise SessionError("AUTH_CLOCK_UNAVAILABLE")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _ids(*values: uuid.UUID) -> None:
        if any(type(value) is not uuid.UUID or value.int == 0 for value in values):
            raise SessionError("VALIDATION_FAILED")

    @staticmethod
    def _token(value: bytes | None) -> None:
        if type(value) is not bytes or len(value) != 32:
            raise SessionError("AUTH_SESSION_EXPIRED")
