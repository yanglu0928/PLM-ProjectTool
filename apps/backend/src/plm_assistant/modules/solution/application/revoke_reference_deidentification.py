"""One-time administrator revocation of a GLOBAL source attestation."""

from __future__ import annotations

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


_OPERATION = "V1_SOL_REFERENCE_DEIDENTIFICATION_REVOKE"
_RESULT = "V1_SOL_REFERENCE_DEIDENTIFICATION_REVOKED"
_REASONS = frozenset({"SOURCE_EXPOSED", "SCOPE_CHANGED", "ADMIN_REVIEW"})


class ReferenceDeidentificationRevokeError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RevokeReferenceDeidentification:
    confirmation_id: uuid.UUID
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    reason_code: str
    idempotency_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class RevocationView:
    confirmation_id: uuid.UUID
    revoked_at: datetime


@dataclass(frozen=True, slots=True)
class LockedRevocationTarget:
    confirmation_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    confirmed_at: datetime
    revoked_at: datetime | None


class AdminPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class RevocationRepositoryPort(Protocol):
    def lock(self, transaction: object, *, confirmation_id: uuid.UUID) -> LockedRevocationTarget | None: ...
    def latest_id(self, transaction: object, *, source_fingerprint: bytes) -> uuid.UUID | None: ...
    def mark_revoked(self, transaction: object, *, confirmation_id: uuid.UUID,
                     revoked_at: datetime) -> bool: ...


class ReceiptPort(Protocol):
    def reserve(self, transaction: object, *, scope: IdempotencyScope,
                request_fingerprint: bytes) -> IdempotencyResult | None: ...
    def complete(self, transaction: object, *, scope: IdempotencyScope,
                 result: IdempotencyResult) -> None: ...


class ReferenceDeidentificationRevokeService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AdminPort,
                 license_guard: LicensePort, repository: RevocationRepositoryPort,
                 receipts: ReceiptPort, audit: AuditService,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(part is None for part in (
                unit_of_work, access, license_guard, repository, receipts, audit)):
            raise ValueError("revocation dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._repo, self._receipts, self._audit = repository, receipts, audit
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def revoke(self, command: RevokeReferenceDeidentification) -> RevocationView:
        if (type(command) is not RevokeReferenceDeidentification
                or type(command.confirmation_id) is not uuid.UUID
                or command.confirmation_id.int == 0
                or type(command.trace_id) is not uuid.UUID or command.trace_id.int == 0
                or type(command.session_token) is not bytes or len(command.session_token) != 32
                or type(command.csrf_token) is not bytes or len(command.csrf_token) != 32
                or type(command.reason_code) is not str
                or command.reason_code not in _REASONS):
            raise ReferenceDeidentificationRevokeError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(command.idempotency_key)
            with self._uow() as tx:
                self._admin(tx, command)
            self._guard.require_valid(trace_id=command.trace_id)
            with self._uow() as tx:
                now, actor = self._admin(tx, command)
                target = self._repo.lock(tx, confirmation_id=command.confirmation_id)
                if type(target) is not LockedRevocationTarget:
                    raise ReferenceDeidentificationRevokeError("SOLUTION_NOT_FOUND")
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation=_OPERATION,
                    key=command.idempotency_key)
                fingerprint = canonical_payload_fingerprint({
                    "confirmation_id": str(command.confirmation_id),
                    "reason_code": command.reason_code,
                })
                replay = self._receipts.reserve(
                    tx, scope=scope, request_fingerprint=fingerprint)
                if replay is not None:
                    if (replay.ref_type != _RESULT or replay.ref_id != command.confirmation_id
                            or replay.status_code != 200 or target.revoked_at is None):
                        raise ReferenceDeidentificationRevokeError()
                    return RevocationView(command.confirmation_id, target.revoked_at)
                if (target.revoked_at is not None
                        or type(target.source_fingerprint) is not bytes
                        or len(target.source_fingerprint) != 32
                        or type(target.confirmed_at) is not datetime
                        or target.confirmed_at.tzinfo is None
                        or now < target.confirmed_at
                        or self._repo.latest_id(tx, source_fingerprint=target.source_fingerprint)
                        != command.confirmation_id):
                    raise ReferenceDeidentificationRevokeError("SOLUTION_CONFLICT")
                if not self._repo.mark_revoked(
                        tx, confirmation_id=command.confirmation_id, revoked_at=now):
                    raise ReferenceDeidentificationRevokeError("SOLUTION_CONFLICT")
                self._audit.append(tx, AuditEventDraft(
                    trace_id=command.trace_id, event_scope="DEPLOYMENT",
                    target_project_id=None, actor_type="USER", actor_id=actor,
                    original_actor_id=None, actor_hint_digest=None,
                    action="SOL_REFERENCE_DEIDENTIFICATION_REVOKED", outcome="SUCCESS",
                    target_owner_module="solution", target_object_type="SOL-01",
                    target_object_id=command.confirmation_id,
                    reason_code=command.reason_code,
                    before_state="CONFIRMED", after_state="REVOKED",
                ))
                self._receipts.complete(tx, scope=scope, result=IdempotencyResult(
                    _RESULT, command.confirmation_id, 200))
                tx.commit()
                return RevocationView(command.confirmation_id, now)
        except ReferenceDeidentificationRevokeError:
            raise
        except RuntimeLicenseError:
            raise ReferenceDeidentificationRevokeError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise ReferenceDeidentificationRevokeError(error.code) from None
        except Exception:
            raise ReferenceDeidentificationRevokeError() from None

    def _admin(self, tx: object, command: RevokeReferenceDeidentification,
               ) -> tuple[datetime, uuid.UUID]:
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            raise ReferenceDeidentificationRevokeError()
        now = now.astimezone(timezone.utc)
        actor = self._access.authorized_admin(
            tx, session_token=command.session_token, csrf_token=command.csrf_token, now=now)
        if type(actor) is not uuid.UUID or actor.int == 0:
            raise ReferenceDeidentificationRevokeError("AUTH_ACCESS_DENIED")
        return now, actor
