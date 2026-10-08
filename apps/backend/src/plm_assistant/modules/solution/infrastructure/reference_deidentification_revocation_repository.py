"""Solution-owned, row-locked one-time confirmation revocation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update

from plm_assistant.modules.solution.application.revoke_reference_deidentification import (
    LockedRevocationTarget,
)

from .orm import ReferenceDeidentificationConfirmationRow as Row
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceDeidentificationRevocationRepository:
    def lock(self, transaction: object, *, confirmation_id: uuid.UUID
             ) -> LockedRevocationTarget | None:
        if type(confirmation_id) is not uuid.UUID or confirmation_id.int == 0:
            return None
        row = _session(transaction).execute(select(
            Row.confirmation_id, Row.source_fingerprint, Row.confirmed_at, Row.revoked_at,
        ).where(Row.confirmation_id == confirmation_id).with_for_update(of=Row)).one_or_none()
        return LockedRevocationTarget(*row) if row is not None else None

    def latest_id(self, transaction: object, *, source_fingerprint: bytes
                  ) -> uuid.UUID | None:
        if type(source_fingerprint) is not bytes or len(source_fingerprint) != 32:
            return None
        return _session(transaction).execute(select(Row.confirmation_id).where(
            Row.source_fingerprint == source_fingerprint,
        ).order_by(Row.confirmed_at.desc(), Row.confirmation_id.desc()).limit(1)).scalar_one_or_none()

    def mark_revoked(self, transaction: object, *, confirmation_id: uuid.UUID,
                     revoked_at: datetime) -> bool:
        if (type(confirmation_id) is not uuid.UUID or confirmation_id.int == 0
                or type(revoked_at) is not datetime or revoked_at.tzinfo is None
                or revoked_at.utcoffset() is None):
            return False
        result = _session(transaction).execute(update(Row).where(
            Row.confirmation_id == confirmation_id,
            Row.revoked_at.is_(None),
            Row.confirmed_at <= revoked_at,
        ).values(revoked_at=revoked_at).returning(Row.confirmation_id)).scalar_one_or_none()
        return result == confirmation_id
