"""Read-only recovery of one actor-scoped Evidence eligibility receipt."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from plm_assistant.modules.evidence.application.eligibility_access import EvidenceEligibilityAccessError
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseError
from plm_assistant.modules.platform.application.idempotency import (
    IdempotencyError, IdempotencyResult, IdempotencyScope, validate_idempotency_key,
)


class EvidenceEligibilityLookupError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class LookupEvidenceEligibilityOperation:
    actor_id: uuid.UUID
    session_token: bytes = field(repr=False)
    csrf_token: bytes = field(repr=False)
    trace_id: uuid.UUID
    scope: str
    project_id: uuid.UUID | None
    evidence_id: uuid.UUID
    operation_key: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class EvidenceEligibilityOperationStatus:
    status: str
    evidence_id: uuid.UUID | None = None
    first_status_code: int | None = None


class EligibilityLookupAccessPort(Protocol):
    def require_in_transaction(self, transaction: object, *, actor_id: uuid.UUID,
                               scope: str, project_id: uuid.UUID | None,
                               operation: str, session_token: bytes,
                               csrf_token: bytes) -> None: ...


class EligibilityLookupEvidencePort(Protocol):
    def exists(self, transaction: object, *, scope: str,
               project_id: uuid.UUID | None, evidence_id: uuid.UUID) -> bool: ...


class EligibilityLookupReceiptsPort(Protocol):
    def lookup_result(self, transaction: object, *, scope: IdempotencyScope) -> IdempotencyResult | None: ...


class EligibilityLookupLicensePort(Protocol):
    def require_valid(self, *, trace_id: uuid.UUID) -> object: ...


class EvidenceEligibilityOperationLookupService:
    def __init__(self, *, unit_of_work: Callable[[], object],
                 access: EligibilityLookupAccessPort,
                 evidence: EligibilityLookupEvidencePort,
                 receipts: EligibilityLookupReceiptsPort,
                 license_guard: EligibilityLookupLicensePort) -> None:
        if any(item is None for item in (unit_of_work, access, evidence, receipts, license_guard)):
            raise ValueError("Evidence eligibility lookup dependencies required")
        self._uow, self._access, self._evidence = unit_of_work, access, evidence
        self._receipts, self._guard = receipts, license_guard

    def lookup(self, query: LookupEvidenceEligibilityOperation) -> EvidenceEligibilityOperationStatus:
        self._validate(query)
        try:
            self._guard.require_valid(trace_id=query.trace_id)
            scope = IdempotencyScope.from_key(
                actor_id=query.actor_id, project_id=query.project_id,
                operation="V1_EVIDENCE_SET_ELIGIBILITY", key=query.operation_key,
            )
            with self._uow() as transaction:
                self._access.require_in_transaction(
                    transaction, actor_id=query.actor_id, scope=query.scope,
                    project_id=query.project_id,
                    operation="V1_EVIDENCE_ELIGIBILITY_OPERATION_LOOKUP",
                    session_token=query.session_token, csrf_token=query.csrf_token,
                )
                exists = self._evidence.exists(
                    transaction, scope=query.scope, project_id=query.project_id,
                    evidence_id=query.evidence_id,
                )
                if type(exists) is not bool or not exists:
                    raise EvidenceEligibilityLookupError("RESOURCE_NOT_FOUND")
                receipt = self._receipts.lookup_result(transaction, scope=scope)
                if receipt is None:
                    return EvidenceEligibilityOperationStatus("UNCONFIRMED")
                if (type(receipt) is not IdempotencyResult
                        or receipt.ref_type != "V1_EVIDENCE_ELIGIBILITY"
                        or receipt.ref_id != query.evidence_id
                        or receipt.status_code != 200):
                    raise EvidenceEligibilityLookupError("CONFLICT_IDEMPOTENCY")
                return EvidenceEligibilityOperationStatus("COMPLETED", query.evidence_id, 200)
        except EvidenceEligibilityLookupError:
            raise
        except RuntimeLicenseError:
            raise EvidenceEligibilityLookupError("LICENSE_OPERATION_DENIED") from None
        except (EvidenceEligibilityAccessError, IdempotencyError) as error:
            code = getattr(error, "code", "SYSTEM_UNAVAILABLE")
            if code not in ("AUTH_ACCESS_DENIED", "RESOURCE_NOT_FOUND", "CONFLICT_IDEMPOTENCY",
                            "VALIDATION_FAILED"):
                code = "SYSTEM_UNAVAILABLE"
            raise EvidenceEligibilityLookupError(code) from None
        except Exception:
            raise EvidenceEligibilityLookupError("SYSTEM_UNAVAILABLE") from None

    @staticmethod
    def _validate(query: LookupEvidenceEligibilityOperation) -> None:
        if (type(query) is not LookupEvidenceEligibilityOperation
                or any(type(value) is not uuid.UUID or value.int == 0 for value in (
                    query.actor_id, query.trace_id, query.evidence_id))
                or type(query.session_token) is not bytes or len(query.session_token) != 32
                or type(query.csrf_token) is not bytes or len(query.csrf_token) != 32
                or query.scope not in ("PROJECT", "GLOBAL")
                or query.scope == "PROJECT" and (
                    type(query.project_id) is not uuid.UUID or query.project_id.int == 0)
                or query.scope == "GLOBAL" and query.project_id is not None):
            raise EvidenceEligibilityLookupError("VALIDATION_FAILED")
        try:
            validate_idempotency_key(query.operation_key)
        except IdempotencyError:
            raise EvidenceEligibilityLookupError("VALIDATION_FAILED") from None
