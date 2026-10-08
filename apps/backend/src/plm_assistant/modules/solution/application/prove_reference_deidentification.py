"""Current admin-only GLOBAL human-deidentification proof for Reference admission."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .reference_source_qualification import VerifiedReferenceDeidentification


@dataclass(frozen=True, slots=True)
class LockedReferenceDeidentification:
    confirmation_id: uuid.UUID
    source_fingerprint: bytes = field(repr=False)
    source_project_class: str
    deidentification_class: str
    applicability: dict[str, object] = field(repr=False)
    attestation_statement: str
    confirmed_by: uuid.UUID
    confirmed_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class AdminPort(Protocol):
    def authorized_admin(self, transaction: object, *, session_token: bytes,
                         now: datetime) -> uuid.UUID | None: ...


class ConfirmationPort(Protocol):
    def latest(self, transaction: object, *, source_fingerprint: bytes,
               now: datetime) -> LockedReferenceDeidentification | None: ...


class ReferenceDeidentificationProofService:
    def __init__(self, *, admins: AdminPort, confirmations: ConfirmationPort,
                 clock: Callable[[], datetime] | None = None) -> None:
        if admins is None or confirmations is None:
            raise ValueError("GLOBAL confirmation proof dependencies required")
        self._admins, self._confirmations = admins, confirmations
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def prove(self, transaction: object, *, session_token: bytes,
              trace_id: uuid.UUID, source_fingerprint: bytes,
              source_project_class: str, deidentification_class: str,
              applicability: dict[str, object],
              ) -> VerifiedReferenceDeidentification | None:
        if (transaction is None or type(session_token) is not bytes
                or len(session_token) != 32 or type(trace_id) is not uuid.UUID
                or trace_id.int == 0 or type(source_fingerprint) is not bytes
                or len(source_fingerprint) != 32
                or type(source_project_class) is not str
                or type(deidentification_class) is not str
                or type(applicability) is not dict):
            return None
        now = self._clock()
        if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
            return None
        now = now.astimezone(timezone.utc)
        actor = self._admins.authorized_admin(
            transaction, session_token=session_token, now=now)
        if type(actor) is not uuid.UUID or actor.int == 0:
            return None
        proof = self._confirmations.latest(
            transaction, source_fingerprint=source_fingerprint, now=now)
        if (type(proof) is not LockedReferenceDeidentification
                or type(proof.confirmation_id) is not uuid.UUID
                or proof.confirmation_id.int == 0
                or proof.source_fingerprint != source_fingerprint
                or proof.source_project_class != source_project_class
                or proof.deidentification_class != deidentification_class
                or proof.applicability != applicability
                or proof.attestation_statement != "I_VERIFIED_DEIDENTIFICATION"
                or type(proof.confirmed_by) is not uuid.UUID
                or proof.confirmed_by.int == 0
                or type(proof.confirmed_at) is not datetime
                or proof.confirmed_at.tzinfo is None
                or proof.confirmed_at.utcoffset() is None
                or type(proof.expires_at) is not datetime
                or proof.expires_at.tzinfo is None
                or proof.expires_at.utcoffset() is None
                or not proof.confirmed_at <= now < proof.expires_at
                or proof.revoked_at is not None):
            return None
        return VerifiedReferenceDeidentification(
            proof.confirmation_id, actor, proof.source_fingerprint,
            proof.confirmed_at, proof.expires_at,
        )
