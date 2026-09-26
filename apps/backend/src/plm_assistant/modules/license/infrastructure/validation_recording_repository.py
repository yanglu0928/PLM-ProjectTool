"""Transactional PostgreSQL adapter for imported License validation evidence."""

from __future__ import annotations

import uuid

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.license.application.license_validation import VerifiedFullBundleLicense
from plm_assistant.modules.license.application.validation_recording import ImportedDocument
from plm_assistant.modules.license.infrastructure.installation_orm import (
    LicenseInstallationDocumentRow, LicenseInstallationRow,
)
from plm_assistant.modules.license.infrastructure.validation_orm import LicenseValidationEventRow


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("active license transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active license transaction is required")
    return session


class SqlAlchemyValidationRecordingRepository:
    def read_imported(self, transaction: object, installation_id: uuid.UUID) -> ImportedDocument | None:
        session = _session(transaction)
        row = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == installation_id,
            LicenseInstallationRow.installation_state == "IMPORTED",
        )).scalar_one_or_none()
        if row is None:
            return None
        document = session.execute(select(LicenseInstallationDocumentRow).where(
            LicenseInstallationDocumentRow.license_installation_id == installation_id,
        )).scalar_one_or_none()
        return ImportedDocument(row.license_installation_id, row.public_key_ref, row.lock_version,
                                document.signed_document if document else None,
                                document.document_sha256 if document else None)

    def append_result(self, transaction: object, *, installation_id: uuid.UUID, code: str,
                      document_sha256: bytes | None, verified: VerifiedFullBundleLicense | None,
                      trace_id: uuid.UUID) -> uuid.UUID:
        snapshot = None
        if verified is not None:
            snapshot = {
                "product_code": verified.product_code,
                "grant_scope": verified.grant_scope,
                "valid_from": verified.valid_from.isoformat(),
                "valid_to": verified.valid_to.isoformat(),
            }
        values = dict(
            installation_id=installation_id, validation_code=code,
            machine_fingerprint_hash=verified.machine_fingerprint_hash if verified else None,
            document_sha256=document_sha256,
            trace_id=trace_id,
        )
        if verified is not None:
            values["validated_at"] = verified.validated_at
            values["entitlement_snapshot"] = snapshot
        return _session(transaction).execute(insert(LicenseValidationEventRow).values(
            **values,
        ).returning(LicenseValidationEventRow.validation_event_id)).scalar_one()

    def attach_result(self, transaction: object, *, installation_id: uuid.UUID,
                      expected_version: int, event_id: uuid.UUID) -> bool:
        result = _session(transaction).execute(update(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == installation_id,
            LicenseInstallationRow.installation_state == "IMPORTED",
            LicenseInstallationRow.lock_version == expected_version,
        ).values(validation_result_ref=event_id, lock_version=expected_version + 1))
        return result.rowcount == 1
