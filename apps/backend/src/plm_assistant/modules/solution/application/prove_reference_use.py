"""Opaque, transaction-bound eligibility contract for OutlineVersion input.

This does not authorize a caller or expose GLOBAL source content. The future
OutlineVersion Owner must authorize the actor before invoking this service and
must keep the same transaction open through its referencing write.
"""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


class ReferenceUseProofError(RuntimeError):
    def __init__(self, code: str = "REFERENCE_UNAVAILABLE") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ReferenceUseQuery:
    trace_id: uuid.UUID
    target_project_id: uuid.UUID
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str


@dataclass(frozen=True, slots=True)
class CurrentReferenceUseSnapshot:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    source_project_id: uuid.UUID | None
    eligibility_state: str
    eligibility_event_id: uuid.UUID
    eligibility_event_version_id: uuid.UUID
    eligibility_event_result_state: str
    document_version_ids: tuple[uuid.UUID, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    source_fingerprint: bytes = field(repr=False)
    deidentification_confirmation_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class CurrentReferenceSourceProof:
    scope: str
    source_project_id: uuid.UUID | None
    document_version_ids: tuple[uuid.UUID, ...]
    evidence_ids: tuple[uuid.UUID, ...]
    source_fingerprint: bytes = field(repr=False)


@dataclass(frozen=True, slots=True)
class CurrentGlobalConfirmationProof:
    confirmation_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    attestation_statement: str
    confirmed_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class EligibleReferenceUseProof:
    reference_solution_id: uuid.UUID
    reference_version_id: uuid.UUID
    scope: str
    target_project_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    eligibility_event_id: uuid.UUID
    deidentification_confirmation_id: uuid.UUID | None


class CurrentReferencePort(Protocol):
    def current(self, transaction: object, *, query: ReferenceUseQuery,
                now: datetime) -> CurrentReferenceUseSnapshot | None: ...


class CurrentSourcePort(Protocol):
    def prove(self, transaction: object, *, query: ReferenceUseQuery,
              current: CurrentReferenceUseSnapshot) -> CurrentReferenceSourceProof | None: ...


class CurrentConfirmationPort(Protocol):
    def current(self, transaction: object, *,
                current: CurrentReferenceUseSnapshot,
                now: datetime) -> CurrentGlobalConfirmationProof | None: ...


def _id(value: object) -> bool:
    return type(value) is uuid.UUID and value.int != 0


def _ids(value: object, *, minimum: int, maximum: int) -> bool:
    return (type(value) is tuple and minimum <= len(value) <= maximum
            and all(_id(item) for item in value)
            and len(set(value)) == len(value))


class ReferenceUseProofService:
    """Fail-closed validator over Owner-only current-state proof ports."""

    def __init__(self, *, references: CurrentReferencePort,
                 sources: CurrentSourcePort,
                 confirmations: CurrentConfirmationPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if any(port is None for port in (references, sources, confirmations)):
            raise ValueError("current Reference use proof ports required")
        self._references = references
        self._sources = sources
        self._confirmations = confirmations
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, query: ReferenceUseQuery) -> EligibleReferenceUseProof:
        if (transaction is None or type(query) is not ReferenceUseQuery
                or not all(_id(value) for value in (
                    query.trace_id, query.target_project_id,
                    query.reference_solution_id, query.reference_version_id))
                or query.scope not in ("PROJECT", "GLOBAL")):
            raise ReferenceUseProofError("VALIDATION_FAILED")
        try:
            now = self._clock()
            if (type(now) is not datetime or now.tzinfo is None
                    or now.utcoffset() is None):
                raise ReferenceUseProofError()
            now = now.astimezone(timezone.utc)
            current = self._references.current(transaction, query=query, now=now)
            if (type(current) is not CurrentReferenceUseSnapshot
                    or current.reference_solution_id != query.reference_solution_id
                    or current.reference_version_id != query.reference_version_id
                    or current.scope != query.scope
                    or current.source_project_id != (
                        query.target_project_id if query.scope == "PROJECT" else None)
                    or current.eligibility_state != "ELIGIBLE"
                    or not _id(current.eligibility_event_id)
                    or current.eligibility_event_version_id != query.reference_version_id
                    or current.eligibility_event_result_state != "ELIGIBLE"
                    or not _ids(current.document_version_ids, minimum=1, maximum=100)
                    or not _ids(current.evidence_ids, minimum=0, maximum=500)
                    or type(current.source_fingerprint) is not bytes
                    or len(current.source_fingerprint) != 32
                    or (query.scope == "PROJECT"
                        and current.deidentification_confirmation_id is not None)
                    or (query.scope == "GLOBAL"
                        and not _id(current.deidentification_confirmation_id))):
                raise ReferenceUseProofError()
            source = self._sources.prove(transaction, query=query, current=current)
            if (type(source) is not CurrentReferenceSourceProof
                    or source.scope != current.scope
                    or source.source_project_id != current.source_project_id
                    or source.document_version_ids != current.document_version_ids
                    or source.evidence_ids != current.evidence_ids
                    or type(source.source_fingerprint) is not bytes
                    or len(source.source_fingerprint) != 32
                    or not hmac.compare_digest(
                        source.source_fingerprint, current.source_fingerprint)):
                raise ReferenceUseProofError()
            if query.scope == "GLOBAL":
                confirmation = self._confirmations.current(
                    transaction, current=current, now=now)
                if (type(confirmation) is not CurrentGlobalConfirmationProof
                        or confirmation.confirmation_id
                        != current.deidentification_confirmation_id
                        or type(confirmation.source_fingerprint) is not bytes
                        or not hmac.compare_digest(
                            confirmation.source_fingerprint,
                            current.source_fingerprint)
                        or confirmation.attestation_statement
                        != "I_VERIFIED_DEIDENTIFICATION"
                        or type(confirmation.confirmed_at) is not datetime
                        or confirmation.confirmed_at.tzinfo is None
                        or type(confirmation.expires_at) is not datetime
                        or confirmation.expires_at.tzinfo is None
                        or not confirmation.confirmed_at <= now < confirmation.expires_at
                        or confirmation.revoked_at is not None):
                    raise ReferenceUseProofError()
            return EligibleReferenceUseProof(
                current.reference_solution_id, current.reference_version_id,
                current.scope, query.target_project_id, current.source_fingerprint,
                current.eligibility_event_id,
                current.deidentification_confirmation_id,
            )
        except ReferenceUseProofError:
            raise
        except Exception:
            raise ReferenceUseProofError() from None
