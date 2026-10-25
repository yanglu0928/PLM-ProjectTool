"""Atomic replacement of the active installation and validation projection."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from plm_assistant.modules.license.application.installation_activation import ActivatedLicense
from plm_assistant.modules.license.infrastructure.installation_orm import (
    LicenseInstallationDocumentRow, LicenseInstallationRow,
)
from plm_assistant.modules.license.infrastructure.validation_orm import (
    LicenseValidationEventRow, LicenseValidationStateRow,
)


MAX_ACTIVATION_DELAY = timedelta(seconds=60)


def _session(transaction: object) -> Session:
    try:
        session = transaction.session  # type: ignore[attr-defined]
    except (AttributeError, RuntimeError) as exc:
        raise RuntimeError("active license activation transaction is required") from exc
    if not isinstance(session, Session) or not session.in_transaction():
        raise RuntimeError("active license activation transaction is required")
    return session


def _valid_event(event: LicenseValidationEventRow, *, installation_id: uuid.UUID,
                 event_id: uuid.UUID, trace_id: uuid.UUID, document_sha256: bytes,
                 now: datetime) -> bool:
    if (event.validation_event_id != event_id or event.installation_id != installation_id
            or event.trace_id != trace_id or event.validation_code != "VALID"
            or type(event.document_sha256) is not bytes
            or not hmac.compare_digest(event.document_sha256, document_sha256)
            or type(event.machine_fingerprint_hash) is not bytes
            or len(event.machine_fingerprint_hash) != 32
            or not isinstance(event.validated_at, datetime)
            or event.validated_at.tzinfo is None
            or not event.validated_at <= now <= event.validated_at + MAX_ACTIVATION_DELAY):
        return False
    snapshot = event.entitlement_snapshot
    if (type(snapshot) is not dict or set(snapshot) != {
        "product_code", "grant_scope", "valid_from", "valid_to",
    } or snapshot["product_code"] != "PLM_PROJECT_TOOL"
            or snapshot["grant_scope"] != "FULL_BUNDLE"):
        return False
    try:
        valid_from = datetime.fromisoformat(snapshot["valid_from"])
        valid_to = datetime.fromisoformat(snapshot["valid_to"])
        if valid_from.tzinfo is None or valid_to.tzinfo is None:
            return False
        return valid_from.astimezone(timezone.utc) <= now <= valid_to.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return False


class SqlAlchemyLicenseActivationRepository:
    def activate(self, transaction: object, *, installation_id: uuid.UUID,
                 expected_lock_version: int, event_id: uuid.UUID,
                 trace_id: uuid.UUID, now: datetime) -> ActivatedLicense | None:
        session = _session(transaction)
        state = session.execute(select(LicenseValidationStateRow).where(
            LicenseValidationStateRow.singleton_key == 1,
        ).with_for_update()).scalar_one_or_none()
        active = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.installation_state == "ACTIVE",
        ).with_for_update()).scalar_one_or_none()
        if (active is None and state is not None and state.active_license_ref is not None
                or active is not None and (state is None or state.active_license_ref != active.license_installation_id)):
            return None
        target = session.execute(select(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == installation_id,
            LicenseInstallationRow.installation_state == "IMPORTED",
            LicenseInstallationRow.lock_version == expected_lock_version,
            LicenseInstallationRow.validation_result_ref == event_id,
        ).with_for_update()).scalar_one_or_none()
        if target is None:
            return None
        document = session.execute(select(LicenseInstallationDocumentRow).where(
            LicenseInstallationDocumentRow.license_installation_id == installation_id,
        )).scalar_one_or_none()
        event = session.execute(select(LicenseValidationEventRow).where(
            LicenseValidationEventRow.validation_event_id == event_id,
        )).scalar_one_or_none()
        if (document is None or event is None
                or not hmac.compare_digest(hashlib.sha256(document.signed_document).digest(),
                                           document.document_sha256)
                or not _valid_event(event, installation_id=installation_id, event_id=event_id,
                                    trace_id=trace_id, document_sha256=document.document_sha256,
                                    now=now)):
            return None
        if state is not None and (state.updated_at > now
                                  or state.validation_code == "VALID" and active is None):
            return None
        previous_id = active.license_installation_id if active else None
        if active is not None:
            session.execute(update(LicenseInstallationRow).where(
                LicenseInstallationRow.license_installation_id == previous_id,
                LicenseInstallationRow.installation_state == "ACTIVE",
                LicenseInstallationRow.lock_version == active.lock_version,
            ).values(installation_state="SUPERSEDED", lock_version=active.lock_version + 1))
        result = session.execute(update(LicenseInstallationRow).where(
            LicenseInstallationRow.license_installation_id == installation_id,
            LicenseInstallationRow.installation_state == "IMPORTED",
            LicenseInstallationRow.lock_version == expected_lock_version,
            LicenseInstallationRow.validation_result_ref == event_id,
        ).values(installation_state="ACTIVE", lock_version=expected_lock_version + 1))
        if result.rowcount != 1:
            return None
        projection = dict(
            active_license_ref=installation_id, machine_fingerprint_hash=event.machine_fingerprint_hash,
            validation_code="VALID", entitlement_snapshot=event.entitlement_snapshot,
            validated_at=event.validated_at, current_event_ref=event_id, updated_at=now,
        )
        if state is None:
            session.execute(insert(LicenseValidationStateRow).values(
                singleton_key=1, state_version=0, **projection,
            ))
            version = 0
        else:
            previous_version = state.state_version
            result = session.execute(update(LicenseValidationStateRow).where(
                LicenseValidationStateRow.license_validation_state_id == state.license_validation_state_id,
                LicenseValidationStateRow.state_version == previous_version,
            ).values(state_version=previous_version + 1, **projection))
            if result.rowcount != 1:
                return None
            version = previous_version + 1
        return ActivatedLicense(installation_id, previous_id, event_id, version)
