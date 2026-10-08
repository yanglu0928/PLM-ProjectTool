"""Minimal current-state projection for an actor-owned attestation receipt."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select

from .orm import ReferenceDeidentificationConfirmationRow as Row
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceDeidentificationOperationState:
    def current_state(self, transaction: object, *, confirmation_id: uuid.UUID,
                      actor_id: uuid.UUID, now: datetime) -> str | None:
        if (type(confirmation_id) is not uuid.UUID or confirmation_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            return None
        session = _session(transaction)
        row = session.execute(select(
            Row.source_fingerprint, Row.expires_at, Row.revoked_at,
        ).where(Row.confirmation_id == confirmation_id,
                Row.confirmed_by == actor_id).execution_options(autoflush=False)).one_or_none()
        if row is None:
            return None
        fingerprint, expires_at, revoked_at = row
        if revoked_at is not None:
            return "REVOKED"
        if expires_at <= now:
            return "EXPIRED"
        latest = session.execute(select(Row.confirmation_id).where(
            Row.source_fingerprint == fingerprint,
        ).order_by(Row.confirmed_at.desc(), Row.confirmation_id.desc())
            .limit(1).execution_options(autoflush=False)).scalar_one_or_none()
        return "CONFIRMED" if latest == confirmation_id else "SUPERSEDED"
