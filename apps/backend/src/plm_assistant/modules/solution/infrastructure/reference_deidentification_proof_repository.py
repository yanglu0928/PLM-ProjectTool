"""Locked safe-column read of the latest GLOBAL human confirmation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from plm_assistant.modules.solution.application.prove_reference_deidentification import (
    LockedReferenceDeidentification,
)

from .orm import ReferenceDeidentificationConfirmationRow
from .reference_deidentification_repository import _session


class SqlAlchemyReferenceDeidentificationProofRepository:
    def latest(self, transaction: object, *, source_fingerprint: bytes,
               now: datetime) -> LockedReferenceDeidentification | None:
        if (type(source_fingerprint) is not bytes or len(source_fingerprint) != 32
                or type(now) is not datetime or now.tzinfo is None
                or now.utcoffset() is None):
            return None
        row = _session(transaction).execute(select(
            ReferenceDeidentificationConfirmationRow.confirmation_id,
            ReferenceDeidentificationConfirmationRow.source_fingerprint,
            ReferenceDeidentificationConfirmationRow.source_project_class,
            ReferenceDeidentificationConfirmationRow.deidentification_class,
            ReferenceDeidentificationConfirmationRow.applicability,
            ReferenceDeidentificationConfirmationRow.attestation_statement,
            ReferenceDeidentificationConfirmationRow.confirmed_by,
            ReferenceDeidentificationConfirmationRow.confirmed_at,
            ReferenceDeidentificationConfirmationRow.expires_at,
            ReferenceDeidentificationConfirmationRow.revoked_at,
        ).where(
            ReferenceDeidentificationConfirmationRow.source_fingerprint == source_fingerprint,
        ).order_by(
            ReferenceDeidentificationConfirmationRow.confirmed_at.desc(),
            ReferenceDeidentificationConfirmationRow.confirmation_id.desc(),
        ).limit(1).with_for_update(read=True, of=ReferenceDeidentificationConfirmationRow)
        ).one_or_none()
        return LockedReferenceDeidentification(*row) if row is not None else None
