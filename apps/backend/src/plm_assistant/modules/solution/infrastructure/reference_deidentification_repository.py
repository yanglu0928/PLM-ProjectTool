"""Solution-owned GLOBAL deidentification confirmation persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from plm_assistant.modules.solution.application.confirm_reference_deidentification import (
    ReferenceDeidentificationConfirmationView,
)
from plm_assistant.modules.solution.application.reference_source_qualification import (
    ProvenReferenceSources, ReferenceSourceRequest,
)

from .orm import ReferenceDeidentificationConfirmationRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as error:
        raise RuntimeError("active Solution transaction required") from error
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active Solution transaction required")
    return session


class SqlAlchemyReferenceDeidentificationRepository:
    def create(self, transaction: object, *, confirmation_id: uuid.UUID,
               proven: ProvenReferenceSources, request: ReferenceSourceRequest,
               actor_id: uuid.UUID, confirmed_at: datetime, expires_at: datetime) -> None:
        if (type(confirmation_id) is not uuid.UUID or confirmation_id.int == 0
                or type(proven) is not ProvenReferenceSources
                or proven.scope != "GLOBAL" or proven.project_id is not None
                or type(proven.content_fingerprint) is not bytes
                or len(proven.content_fingerprint) != 32
                or type(request) is not ReferenceSourceRequest
                or request.scope != "GLOBAL" or request.project_id is not None
                or type(actor_id) is not uuid.UUID or actor_id.int == 0
                or type(confirmed_at) is not datetime or confirmed_at.tzinfo is None
                or type(expires_at) is not datetime or expires_at.tzinfo is None):
            raise ValueError("validated GLOBAL confirmation required")
        _session(transaction).execute(insert(ReferenceDeidentificationConfirmationRow).values(
            confirmation_id=confirmation_id,
            source_fingerprint=proven.content_fingerprint,
            source_project_class=request.source_project_class,
            deidentification_class=request.deidentification_class,
            applicability=request.applicability,
            attestation_statement="I_VERIFIED_DEIDENTIFICATION",
            confirmed_by=actor_id,
            confirmed_at=confirmed_at,
            expires_at=expires_at,
            trace_id=request.trace_id,
        ))

    def view(self, transaction: object, *, confirmation_id: uuid.UUID,
             actor_id: uuid.UUID) -> ReferenceDeidentificationConfirmationView | None:
        if (type(confirmation_id) is not uuid.UUID or confirmation_id.int == 0
                or type(actor_id) is not uuid.UUID or actor_id.int == 0):
            return None
        row = _session(transaction).execute(select(
            ReferenceDeidentificationConfirmationRow.confirmation_id,
            ReferenceDeidentificationConfirmationRow.source_fingerprint,
            ReferenceDeidentificationConfirmationRow.confirmed_by,
            ReferenceDeidentificationConfirmationRow.confirmed_at,
            ReferenceDeidentificationConfirmationRow.expires_at,
            ReferenceDeidentificationConfirmationRow.trace_id,
        ).where(
            ReferenceDeidentificationConfirmationRow.confirmation_id == confirmation_id,
            ReferenceDeidentificationConfirmationRow.confirmed_by == actor_id,
            ReferenceDeidentificationConfirmationRow.revoked_at.is_(None),
        ).with_for_update(of=ReferenceDeidentificationConfirmationRow)).one_or_none()
        if row is None:
            return None
        return ReferenceDeidentificationConfirmationView(*row)
