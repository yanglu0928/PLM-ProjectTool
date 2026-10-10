"""Read-only, current-admin recovery of a GLOBAL attestation operation receipt."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope, validate_idempotency_key,
)


_OPERATIONS = {
    "CONFIRM": ("V1_SOL_REFERENCE_DEIDENTIFICATION_CONFIRM",
                "V1_SOL_REFERENCE_DEIDENTIFICATION", 201),
    "REVOKE": ("V1_SOL_REFERENCE_DEIDENTIFICATION_REVOKE",
               "V1_SOL_REFERENCE_DEIDENTIFICATION_REVOKED", 200),
}


class ReferenceDeidentificationLookupError(RuntimeError):
    def __init__(self, code: str = "SOLUTION_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LookupReferenceDeidentificationOperation:
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    operation_kind: str
    operation_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ReferenceDeidentificationOperationStatus:
    status: str
    confirmation_id: uuid.UUID | None = None
    first_status_code: int | None = None
    current_state: str | None = None


class AdminPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         csrf_token: bytes, now: datetime) -> uuid.UUID | None: ...


class LicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class ReceiptPort(Protocol):
    def lookup_result(self, transaction: object, *, scope: IdempotencyScope) -> IdempotencyResult | None: ...


class ConfirmationPort(Protocol):
    def current_state(self, transaction: object, *, confirmation_id: uuid.UUID,
                      actor_id: uuid.UUID, now: datetime) -> str | None: ...


class ReferenceDeidentificationOperationLookupService:
    def __init__(self, *, unit_of_work: Callable[[], object], access: AdminPort,
                 license_guard: LicensePort, receipts: ReceiptPort,
                 confirmations: ConfirmationPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(item is None for item in (unit_of_work, access, license_guard,
                                         receipts, confirmations)):
            raise ValueError("GLOBAL attestation lookup dependencies required")
        self._uow, self._access, self._guard = unit_of_work, access, license_guard
        self._receipts, self._confirmations = receipts, confirmations
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def lookup(self, query: LookupReferenceDeidentificationOperation,
               ) -> ReferenceDeidentificationOperationStatus:
        if (type(query) is not LookupReferenceDeidentificationOperation
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.csrf_token) is not bytes or len(query.csrf_token) != 32
                or type(query.trace_id) is not uuid.UUID or query.trace_id.int == 0
                or query.operation_kind not in _OPERATIONS):
            raise ReferenceDeidentificationLookupError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(query.operation_key)
            now = self._clock()
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise ReferenceDeidentificationLookupError()
            now = now.astimezone(timezone.utc)
            with self._uow() as tx:
                actor = self._access.authorized_admin(
                    tx, session_token=query.session_token,
                    csrf_token=query.csrf_token, now=now)
                if type(actor) is not uuid.UUID or actor.int == 0:
                    raise ReferenceDeidentificationLookupError("AUTH_ACCESS_DENIED")
                self._guard.require_valid(trace_id=query.trace_id)
                operation, ref_type, expected_status = _OPERATIONS[query.operation_kind]
                scope = IdempotencyScope.from_key(
                    actor_id=actor, project_id=None, operation=operation,
                    key=query.operation_key)
                receipt = self._receipts.lookup_result(tx, scope=scope)
                if receipt is None:
                    return ReferenceDeidentificationOperationStatus("UNCONFIRMED")
                if (type(receipt) is not IdempotencyResult
                        or receipt.ref_type != ref_type
                        or type(receipt.ref_id) is not uuid.UUID
                        or receipt.ref_id.int == 0
                        or receipt.status_code != expected_status):
                    raise ReferenceDeidentificationLookupError("CONFLICT_IDEMPOTENCY")
                state = self._confirmations.current_state(
                    tx, confirmation_id=receipt.ref_id, actor_id=actor, now=now)
                if state not in ("CONFIRMED", "REVOKED", "EXPIRED", "SUPERSEDED"):
                    raise ReferenceDeidentificationLookupError()
                return ReferenceDeidentificationOperationStatus(
                    "COMPLETED", receipt.ref_id, expected_status, state)
        except ReferenceDeidentificationLookupError:
            raise
        except RuntimeLicenseError:
            raise ReferenceDeidentificationLookupError("LICENSE_OPERATION_DENIED") from None
        except IdempotencyError as error:
            raise ReferenceDeidentificationLookupError(
                "VALIDATION_FAILED" if error.code == "VALIDATION_FAILED" else error.code) from None
        except Exception:
            raise ReferenceDeidentificationLookupError() from None
