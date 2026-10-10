"""Atomic insertion of immutable License candidate and safe rejection evidence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert
from sqlalchemy.orm import Session

from plm_assistant.modules.license.infrastructure.installation_orm import (
    LicenseInstallationDocumentRow, LicenseInstallationRow,
)
from plm_assistant.modules.license.infrastructure.validation_orm import LicenseValidationEventRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("active license import transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active license import transaction is required")
    return session


class SqlAlchemyLicenseImportRepository:
    def add_imported(self, transaction: object, *, public_key_ref: str,
                     actor_id: uuid.UUID, trace_id: uuid.UUID,
                     signed_document: bytes, document_sha256: bytes) -> uuid.UUID:
        session = _session(transaction)
        installation_id = session.execute(insert(LicenseInstallationRow).values(
            public_key_ref=public_key_ref, imported_by=actor_id,
            import_trace_id=trace_id, installation_state="IMPORTED",
        ).returning(LicenseInstallationRow.license_installation_id)).scalar_one()
        session.execute(insert(LicenseInstallationDocumentRow).values(
            license_installation_id=installation_id, signed_document=signed_document,
            document_sha256=document_sha256,
        ))
        return installation_id

    def append_rejection(self, transaction: object, *, code: str,
                         trace_id: uuid.UUID, document_sha256: bytes) -> uuid.UUID:
        return _session(transaction).execute(insert(LicenseValidationEventRow).values(
            validation_code=code, document_sha256=document_sha256,
            trace_id=trace_id,
        ).returning(LicenseValidationEventRow.validation_event_id)).scalar_one()
