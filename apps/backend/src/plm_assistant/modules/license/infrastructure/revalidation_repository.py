"""Locked active-installation recovery and atomic validation projection."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime

from sqlalchemy import insert, null, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.license.application.license_validation import VerifiedFullBundleLicense
from plm_assistant.modules.license.application.revalidation import (
    RecoverySource, RevalidationResult,
)
from plm_assistant.modules.license.infrastructure.installation_orm import (
    LicenseInstallationDocumentRow, LicenseInstallationRow,
)
from plm_assistant.modules.license.infrastructure.validation_orm import (
    LicenseValidationEventRow, LicenseValidationStateRow,
)


def _session(transaction: object) -> Session:
    session = transaction.session  # type: ignore[attr-defined]
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active license recovery transaction is required")
    return session


class SqlAlchemyLicenseRecoveryRepository:
    def read_active(self, transaction: object) -> RecoverySource | None:
        session = _session(transaction)
        state = session.execute(select(LicenseValidationStateRow).where(
            LicenseValidationStateRow.singleton_key == 1,
        ).with_for_update()).scalar_one_or_none()
        active = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.installation_state == "ACTIVE",
        ).with_for_update()).scalar_one_or_none()
        if state is None or active is None:
            if state is None and active is None:
                return None
            raise RuntimeError("inconsistent license state")
        if state.active_license_ref != active.license_installation_id:
            raise RuntimeError("inconsistent active reference")
        document = session.execute(select(LicenseInstallationDocumentRow).where(
            LicenseInstallationDocumentRow.license_installation_id == active.license_installation_id,
        )).scalar_one_or_none()
        event = session.execute(select(LicenseValidationEventRow).where(
            LicenseValidationEventRow.validation_event_id == state.current_event_ref,
        )).scalar_one_or_none()
        if (document is None or event is None
                or event.installation_id != active.license_installation_id
                or event.validation_code != state.validation_code
                or event.validated_at != state.validated_at
                or state.entitlement_snapshot != event.entitlement_snapshot
                or state.machine_fingerprint_hash != event.machine_fingerprint_hash
                or type(event.document_sha256) is not bytes
                or type(document.document_sha256) is not bytes
                or not hmac.compare_digest(event.document_sha256, document.document_sha256)
                or not hmac.compare_digest(hashlib.sha256(document.signed_document).digest(),
                                           document.document_sha256)):
            raise RuntimeError("inconsistent license evidence")
        if state.validation_code == "VALID" and (
                type(state.machine_fingerprint_hash) is not bytes
                or type(event.machine_fingerprint_hash) is not bytes
                or type(state.entitlement_snapshot) is not dict):
            raise RuntimeError("inconsistent valid projection")
        return RecoverySource(
            active.license_installation_id, active.public_key_ref,
            document.signed_document, document.document_sha256,
            state.state_version, active.lock_version, state.current_event_ref,
        )

    def record(self, transaction: object, *, source: RecoverySource, code: str,
               verified: VerifiedFullBundleLicense | None, now: datetime,
               trace_id: uuid.UUID) -> RevalidationResult | None:
        session = _session(transaction)
        state = session.execute(select(LicenseValidationStateRow).where(
            LicenseValidationStateRow.singleton_key == 1,
        ).with_for_update()).scalar_one_or_none()
        active = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == source.installation_id,
            LicenseInstallationRow.installation_state == "ACTIVE",
        ).with_for_update()).scalar_one_or_none()
        if (state is None or active is None or state.active_license_ref != source.installation_id
                or state.state_version != source.state_version
                or state.current_event_ref != source.current_event_id
                or active.lock_version != source.installation_lock_version
                or active.public_key_ref != source.public_key_ref):
            return None
        document = session.execute(select(LicenseInstallationDocumentRow).where(
            LicenseInstallationDocumentRow.license_installation_id == source.installation_id,
        )).scalar_one_or_none()
        if (document is None or document.signed_document != source.signed_document
                or not hmac.compare_digest(document.document_sha256, source.document_sha256)):
            return None
        entitlement = None
        if verified is not None:
            if code != "VALID" or not hmac.compare_digest(verified.document_sha256,
                                                           source.document_sha256):
                return None
            entitlement = {
                "product_code": verified.product_code, "grant_scope": verified.grant_scope,
                "valid_from": verified.valid_from.isoformat(),
                "valid_to": verified.valid_to.isoformat(),
            }
        elif code == "VALID":
            return None
        validated_at = verified.validated_at if verified else now
        event_values = dict(
            installation_id=source.installation_id, validation_code=code,
            machine_fingerprint_hash=verified.machine_fingerprint_hash if verified else None,
            document_sha256=source.document_sha256,
            validated_at=validated_at, trace_id=trace_id,
        )
        if entitlement is not None:
            event_values["entitlement_snapshot"] = entitlement
        event_id = session.execute(insert(LicenseValidationEventRow).values(
            **event_values,
        ).returning(LicenseValidationEventRow.validation_event_id)).scalar_one()
        installed = session.execute(update(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == source.installation_id,
            LicenseInstallationRow.installation_state == "ACTIVE",
            LicenseInstallationRow.lock_version == source.installation_lock_version,
        ).values(validation_result_ref=event_id,
                 lock_version=source.installation_lock_version + 1))
        if installed.rowcount != 1:
            return None
        projected = session.execute(update(LicenseValidationStateRow).where(
            LicenseValidationStateRow.license_validation_state_id == state.license_validation_state_id,
            LicenseValidationStateRow.state_version == source.state_version,
            LicenseValidationStateRow.current_event_ref == source.current_event_id,
        ).values(
            validation_code=code,
            machine_fingerprint_hash=verified.machine_fingerprint_hash if verified else None,
            entitlement_snapshot=entitlement if entitlement is not None else null(),
            validated_at=validated_at, current_event_ref=event_id,
            updated_at=max(now, state.updated_at, validated_at),
            state_version=source.state_version + 1,
        ))
        if projected.rowcount != 1:
            return None
        return RevalidationResult(source.installation_id, event_id, code,
                                  source.state_version + 1)
