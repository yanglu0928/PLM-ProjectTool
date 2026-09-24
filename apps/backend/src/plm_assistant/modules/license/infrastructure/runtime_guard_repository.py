"""PostgreSQL License runtime projection with append-only check evidence."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime

from sqlalchemy import insert, null, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.license.application.license_validation import VerifiedFullBundleLicense
from plm_assistant.modules.license.application.runtime_guard import RuntimeLicenseSnapshot
from plm_assistant.modules.license.infrastructure.installation_orm import (
    LicenseInstallationDocumentRow, LicenseInstallationRow,
)
from plm_assistant.modules.license.infrastructure.validation_orm import (
    LicenseValidationEventRow, LicenseValidationStateRow,
)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("active runtime license transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active runtime license transaction is required")
    return session


class SqlAlchemyRuntimeLicenseRepository:
    def read_current(self, transaction: object) -> RuntimeLicenseSnapshot:
        session = _session(transaction)
        state = session.execute(select(LicenseValidationStateRow).where(
            LicenseValidationStateRow.singleton_key == 1,
        ).with_for_update()).scalar_one_or_none()
        active = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.installation_state == "ACTIVE",
        )).scalar_one_or_none()
        if state is None and active is None:
            return RuntimeLicenseSnapshot("NOT_INSTALLED")
        if (state is None or active is None
                or state.active_license_ref != active.license_installation_id):
            return RuntimeLicenseSnapshot("TRUST_STATE_INVALID")
        if state.validation_code != "VALID":
            return RuntimeLicenseSnapshot(state.validation_code)
        document = session.execute(select(LicenseInstallationDocumentRow).where(
            LicenseInstallationDocumentRow.license_installation_id == active.license_installation_id,
        )).scalar_one_or_none()
        event = session.execute(select(LicenseValidationEventRow).where(
            LicenseValidationEventRow.validation_event_id == state.current_event_ref,
        )).scalar_one_or_none()
        if (document is None or event is None
                or event.installation_id != active.license_installation_id
                or event.validation_code != "VALID"
                or type(document.document_sha256) is not bytes
                or type(event.document_sha256) is not bytes
                or type(state.machine_fingerprint_hash) is not bytes
                or type(event.machine_fingerprint_hash) is not bytes
                or type(state.entitlement_snapshot) is not dict
                or state.validated_at != event.validated_at
                or state.entitlement_snapshot != event.entitlement_snapshot
                or not hmac.compare_digest(state.machine_fingerprint_hash,
                                           event.machine_fingerprint_hash)
                or not hmac.compare_digest(document.document_sha256,
                                           event.document_sha256)
                or not hmac.compare_digest(hashlib.sha256(document.signed_document).digest(),
                                           document.document_sha256)):
            return RuntimeLicenseSnapshot("TRUST_STATE_INVALID")
        return RuntimeLicenseSnapshot(
            "VALID", state.license_validation_state_id, state.state_version,
            active.license_installation_id, state.current_event_ref, active.public_key_ref,
            document.signed_document, document.document_sha256,
            state.machine_fingerprint_hash, state.entitlement_snapshot,
        )

    def record_check(self, transaction: object, *, snapshot: RuntimeLicenseSnapshot,
                     code: str, verified: VerifiedFullBundleLicense | None,
                     now: datetime, trace_id: uuid.UUID) -> bool:
        session = _session(transaction)
        state = session.execute(select(LicenseValidationStateRow).where(
            LicenseValidationStateRow.license_validation_state_id == snapshot.state_id,
            LicenseValidationStateRow.singleton_key == 1,
        ).with_for_update()).scalar_one_or_none()
        active = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == snapshot.installation_id,
            LicenseInstallationRow.installation_state == "ACTIVE",
        )).scalar_one_or_none()
        if (state is None or active is None or state.validation_code != "VALID"
                or state.state_version != snapshot.state_version
                or state.current_event_ref != snapshot.current_event_id
                or state.active_license_ref != snapshot.installation_id):
            return False
        document = session.execute(select(LicenseInstallationDocumentRow).where(
            LicenseInstallationDocumentRow.license_installation_id == snapshot.installation_id,
        )).scalar_one_or_none()
        if (document is None or type(snapshot.document_sha256) is not bytes
                or not hmac.compare_digest(hashlib.sha256(document.signed_document).digest(),
                                           snapshot.document_sha256)
                or not hmac.compare_digest(document.document_sha256,
                                           snapshot.document_sha256)):
            return False
        entitlement = None
        if verified is not None:
            entitlement = {
                "product_code": verified.product_code,
                "grant_scope": verified.grant_scope,
                "valid_from": verified.valid_from.isoformat(),
                "valid_to": verified.valid_to.isoformat(),
            }
        event_values = dict(
            installation_id=snapshot.installation_id, validation_code=code,
            machine_fingerprint_hash=verified.machine_fingerprint_hash if verified else None,
            document_sha256=snapshot.document_sha256,
            validated_at=verified.validated_at if verified else now, trace_id=trace_id,
        )
        if entitlement is not None:
            event_values["entitlement_snapshot"] = entitlement
        event_id = session.execute(insert(LicenseValidationEventRow).values(
            **event_values,
        ).returning(LicenseValidationEventRow.validation_event_id)).scalar_one()
        previous_version = state.state_version
        updated_at = max(now, state.updated_at, event_values["validated_at"])
        result = session.execute(update(LicenseValidationStateRow).where(
            LicenseValidationStateRow.license_validation_state_id == snapshot.state_id,
            LicenseValidationStateRow.state_version == previous_version,
            LicenseValidationStateRow.current_event_ref == snapshot.current_event_id,
        ).values(
            validation_code=code,
            machine_fingerprint_hash=verified.machine_fingerprint_hash if verified else None,
            entitlement_snapshot=entitlement if entitlement is not None else null(),
            validated_at=event_values["validated_at"], current_event_ref=event_id,
            updated_at=updated_at, state_version=previous_version + 1,
        ))
        return result.rowcount == 1
